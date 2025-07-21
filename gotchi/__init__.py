"""
Gotchi
======
High‑level façade that wires together all Wi‑Fi harvesting
sub‑systems (channel‑hopper, de‑auth engine, sniffer, rotating capture,
converter & optional cracker).

Public API
----------
* :class:`Gotchi` – context‑manager‑friendly orchestrator
* :func:`start`, :func:`stop`     – singleton helpers (used by CLI)
* :func:`set_channel`             – manually lock to a specific channel
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from pathlib import Path
from types import TracebackType
from typing import Any, Optional, Type

try:
    import tomllib  # Python ≥ 3.11
except ModuleNotFoundError:  # pragma: no cover – Py 3.8‑3.10 fallback
    import tomli as tomllib  # type: ignore

###############################################################################
# Config helpers
###############################################################################

_PKG_DIR = Path(__file__).parent
_DEFAULT_CFG = _PKG_DIR / "config.toml"


def _load_cfg(explicit: str | Path | None = None) -> dict[str, Any]:
    """Load TOML config – falls back to the package default."""
    cfg_path = Path(explicit) if explicit else _DEFAULT_CFG
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with cfg_path.open("rb") as fh:
        return tomllib.load(fh)


###############################################################################
# Stub imports (real implementations live in sibling packages)
###############################################################################

# Imported lazily so gotchi/__init__.py has *zero* hard deps during unit tests.
ChannelHopper: Any
DeauthEngine: Any
Sniffer: Any
Rotator: Any
Converter: Any
up: Any
down: Any
set_channel_hw: Any  # avoid shadowing Gotchi.set_channel


###############################################################################
# Gotchi façade
###############################################################################

class Gotchi:
    """Spin‑up / manage the full harvesting pipeline."""

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        cfg_path: str | Path | None = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        # load config once; later patches (CLI --iface) can edit self.cfg
        self.cfg: dict[str, Any] = _load_cfg(cfg_path)

        # dotted‑lookup helper ------------------------------------------------
        def _cfg(path: str, default=None):
            cur = self.cfg
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return cur

        # Mandatory key ------------------------------------------------------
        self.iface_phys: str | None = _cfg("hw.iface")
        if not self.iface_phys:
            raise ValueError("config.toml is missing [hw] → iface")

        # Handy cached values -------------------------------------------------
        hop_cfg = _cfg("hw.hop", {})
        self._channels: list[int] = hop_cfg.get("channels", [1, 6, 11])
        self._hop_interval_ms: int = hop_cfg.get("interval_ms", 400)

        self._pps_limit: int = _cfg("attacks.deauth.pps_limit", 50)
        self._burst_cnt: int = _cfg("attacks.deauth.burst_count", 16)
        self._rot_cfg: dict[str, Any] = _cfg("capture.rotate", {})
        self._folder: Path = Path(_cfg("capture.folder", "captures")).expanduser()
        self._crack_auto: bool = _cfg("pipeline.crack.auto", False)

        # runtime attrs -------------------------------------------------------
        self.loop = loop or asyncio.get_event_loop()
        self.iface_mon: str | None = None
        self.hopper: Optional[ChannelHopper] = None
        self.deauth: Optional[DeauthEngine] = None
        self.sniffer: Optional[Sniffer] = None
        self.rotator: Optional[Rotator] = None
        self.converter: Optional[Converter] = None
        self._pkt_q: asyncio.Queue = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []
        self._started = False

        # logging ------------------------------------------------------------
        self.log = logging.getLogger("gotchi")
        if not logging.getLogger().handlers:  # respect app‑level logging cfg
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(message)s",
                datefmt="%H:%M:%S",
            )

    # ------------------------------------------------------------------
    # context‑manager sugar
    # ------------------------------------------------------------------

    def __enter__(self) -> "Gotchi":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        # ensure stop() even if user forgets await in sync context
        self.loop.run_until_complete(self.stop())
        return False  # never suppress exceptions

    # ------------------------------------------------------------------
    # public control
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return

        # -----------------------------  HW bring‑up  ----------------------
        global up, down, set_channel_hw  # pylint: disable=global‑statement
        if up is None:  # lazy import only now (avoids circulars in tests)
            from gotchi.hw.iface import up as up, down as down, set_channel as set_channel_hw  # type: ignore
        first_ch = self._channels[0]
        self.iface_mon = up(self.iface_phys, channel=first_ch)

        # -----------------------------  build subsystems  ------------------
        from gotchi.hw.hop import ChannelHopper  # noqa: WPS433 – runtime import
        from gotchi.attacks.deauth import DeauthEngine  # noqa: WPS433
        from gotchi.capture.sniff import Sniffer  # noqa: WPS433
        from gotchi.capture.rotate import RotatingPcap as Rotator  # noqa: WPS433
        from gotchi.capture.convert import Converter  # noqa: WPS433

        self.hopper = ChannelHopper(
            iface=self.iface_mon,
            channels=self._channels,
            interval_s=self._hop_interval_ms / 1000,
            on_hop=self.deauth.set_channel if self.deauth else None,
        )
        self.deauth = DeauthEngine(
            iface=self.iface_mon,
            pps_limit=self._pps_limit,
            burst_count=self._burst_cnt,
        )
        self.sniffer = Sniffer(iface=self.iface_mon, queue=self._pkt_q)
        self.rotator = Rotator(
            folder=self._folder,
            max_size_mb=self._rot_cfg.get("max_size_mb", 10),
            max_age_s=self._rot_cfg.get("max_age_s", 300),
            on_rotate=self._on_pcap_closed,
        )
        self.converter = Converter(
            crack_auto=self._crack_auto,
            wordlists=self.cfg.get("pipeline", {}).get("crack", {}).get("wordlists", []),
        )

        # -----------------------------  kick everything off  --------------
        self.hopper.start()
        self.loop.create_task(self.deauth.start())
        self.sniffer.start()
        self._tasks.append(self.loop.create_task(self.rotator.consume(self._pkt_q)))

        # allow Ctrl‑C to cancel nicely
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self.loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:  # Windows
                pass

        self._started = True
        self.log.info("🟢 Gotchi started (iface %s → %s)", self.iface_phys, self.iface_mon)

    async def stop(self) -> None:
        if not self._started:
            return
        self.log.info("🛑 stopping Gotchi …")

        # orderly shutdown (ignore missing parts if start() failed midway)
        with contextlib.suppress(Exception):
            await self.hopper.stop()         # type: ignore[arg-type]
        with contextlib.suppress(Exception):
            await self.deauth.stop()         # type: ignore[arg-type]
        with contextlib.suppress(Exception):
            await self.sniffer.stop()        # type: ignore[arg-type]
        with contextlib.suppress(Exception):
            await self.rotator.stop()        # type: ignore[arg-type]
        for t in self._tasks:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t

        # tear down monitor iface → managed
        if down and self.iface_mon:
            with contextlib.suppress(Exception):
                down(self.iface_mon)

        self._started = False
        self.log.info("✅ Gotchi fully stopped")

    async def run(self, duration: float | int | None = None, *, crack: bool = False) -> None:
        """Convenience wrapper: start → sleep(duration) → stop → crack."""
        self.start()
        if duration:
            await asyncio.sleep(float(duration))
        await self.stop()
        if crack and self.converter:
            self.log.info("🔐 launching auto‑crack on all captures …")
            # TODO: implement converter.crack_all()

    # ------------------------------------------------------------------
    # channel control
    # ------------------------------------------------------------------

    def set_channel(self, channel: int) -> None:
        """Temporarily lock to *channel* (pauses hopper)."""
        if not self._started:
            return
        self.log.info("⇄ Locking to channel %d", channel)
        self.hopper.pause()           # type: ignore[arg-type]
        set_channel_hw(self.iface_mon, channel)
        self.deauth.set_channel(channel)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # capture callback
    # ------------------------------------------------------------------

    async def _on_pcap_closed(self, path: Path) -> None:
        self.log.info("💾 pcap saved → %s", path)
        await self.converter.convert(path)  # type: ignore[arg-type]


###############################################################################
# Singleton helpers (used by CLI)
###############################################################################

_singleton: Optional[Gotchi] = None


def start(cfg_path: str | Path | None = None) -> None:  # noqa: D401
    global _singleton
    if _singleton is None:
        _singleton = Gotchi(cfg_path)
        _singleton.start()


def stop() -> None:  # noqa: D401
    global _singleton
    if _singleton is not None:
        asyncio.run(_singleton.stop())
        _singleton = None


def set_channel(ch: int) -> None:  # noqa: D401
    if _singleton is not None:
        _singleton.set_channel(ch)


__all__ = [
    "Gotchi",
    "start",
    "stop",
    "set_channel",
]
