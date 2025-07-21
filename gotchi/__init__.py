"""
gotchi.__init__
===============

High-level façade and convenience helpers for the Gotchi Wi-Fi
harvesting pipeline.

Public API
----------

* :class:`Gotchi` – context-manager friendly orchestrator
* :func:`start` / :func:`stop` – singleton helpers for CLI
* :func:`set_channel` – force interface to a specific channel
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
    import tomllib  # Py ≥3.11
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # Py 3.8–3.10 fallback

###############################################################################
# Config loading
###############################################################################

_DEFAULT_CFG = Path(__file__).with_suffix(".toml").with_name("config.toml")


def _load_cfg(explicit: str | Path | None = None) -> dict[str, Any]:
    """Load TOML config.  Falls back to package default."""
    cfg_path = Path(explicit) if explicit else _DEFAULT_CFG
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with cfg_path.open("rb") as fh:
        return tomllib.load(fh)


###############################################################################
# Stubs for subsystems (real implementations live in sibling packages)
###############################################################################

class ChannelHopper:  # pragma: no cover
    def __init__(self, iface: str, channels: list[int], interval_s: float):
        self.iface, self.channels, self.interval_s = iface, channels, interval_s
        self._task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()

    async def _loop(self) -> None:
        while not self._stopped.is_set():
            for ch in self.channels:
                # iface.set_channel(ch)  # real call in hw.iface
                await asyncio.sleep(self.interval_s)
                if self._stopped.is_set():
                    break

    def start(self) -> None:
        self._stopped.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            await self._task


class DeauthEngine:  # pragma: no cover
    def __init__(self, iface: str, pps_limit: int):
        self.iface, self.pps_limit = iface, pps_limit

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def set_channel(self, ch: int) -> None: ...


class Sniffer:  # pragma: no cover
    def __init__(self, iface: str, queue: asyncio.Queue):
        self.iface, self.queue = iface, queue
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _run(self): ...  # capture packets

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


class Rotator:  # pragma: no cover
    def __init__(self, folder: Path, max_size_mb: int, max_age_s: int,
                 on_rotate):
        self.folder, self.on_rotate = folder, on_rotate

    async def consume(self, queue: asyncio.Queue): ...


class Converter:  # pragma: no cover
    def __init__(self, crack_auto: bool):
        self.crack_auto = crack_auto

    async def convert(self, path: Path): ...


###############################################################################
# Gotchi façade
###############################################################################

class Gotchi:
    """Orchestrates channel-hopping, de-auth, sniffing & post-processing."""

    def __init__(self,
                 cfg_path: str | Path | None = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        self.cfg = _load_cfg(cfg_path)
        # ------------------------------------------------------------------
        # helper: dotted-path lookup with default
        # ------------------------------------------------------------------
        def _cfg(path: str, default=None):
            cur = self.cfg
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return cur

        self.loop = loop or asyncio.get_event_loop()

        # ------------------------------------------------------------------
        # pull sections with fallback / defaults
        # ------------------------------------------------------------------
        hw_cfg   = _cfg("hw",           {})
        hop_cfg  = _cfg("hw.hop",       {})
        atk_cfg  = _cfg("attacks.deauth", {})
        cap_cfg  = _cfg("capture.rotate", {})

        # mandatory value: physical interface
        iface = hw_cfg.get("iface")
        if iface is None:
            raise ValueError("config.toml is missing [hw] -> iface")

        # defaults for optional values
        channels   = hop_cfg.get("channels", [1, 6, 11])
        intervalms = hop_cfg.get("interval_ms", 400)


        self.iface_mon = f'{hw_cfg["iface"]}mon'

        # Queues & events
        self._pkt_q: asyncio.Queue = asyncio.Queue()

        # Sub-systems (real classes imported later)
        self.hopper = ChannelHopper(
            iface=self.iface_mon,
            channels=hw_cfg["hop"]["channels"],
            interval_s=hw_cfg["hop"]["interval_ms"] / 1000,
        )
        self.deauth = DeauthEngine(
            iface=self.iface_mon,
            pps_limit=atk_cfg["pps_limit"],
        )
        self.sniffer = Sniffer(iface=self.iface_mon, queue=self._pkt_q)
        self.rotator = Rotator(
            folder=Path(self.cfg["capture"]["folder"]),
            max_size_mb=cap_cfg["max_size_mb"],
            max_age_s=cap_cfg["max_age_s"],
            on_rotate=self._on_pcap_closed,
        )
        self.converter = Converter(
            crack_auto=self.cfg["pipeline"]["crack"]["auto"],
        )

        self._tasks: list[asyncio.Task] = []
        self._started = False

        # Logging
        self.log = logging.getLogger("gotchi")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )

    # --------------------------------------------------------------------- #
    # Context-manager helpers
    # --------------------------------------------------------------------- #

    def __enter__(self) -> "Gotchi":
        self.start()
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc: Optional[BaseException],
                 tb: Optional[TracebackType]) -> Optional[bool]:
        self.loop.run_until_complete(self.stop())
        return False  # don’t suppress exceptions

    # --------------------------------------------------------------------- #
    # Public control methods
    # --------------------------------------------------------------------- #

    def start(self) -> None:
        """Spin up all sub-systems (non-blocking)."""
        if self._started:
            return
        self.log.info("🟢 starting Gotchi …")

        self.hopper.start()
        self.deauth.loop = self.loop
        self.sniffer.start()

        # consumer chains
        self._tasks.append(
            self.loop.create_task(self.rotator.consume(self._pkt_q)))

        # Allow Ctrl-C
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        self._started = True

    async def stop(self) -> None:
        """Gracefully shut down."""
        if not self._started:
            return
        self.log.info("🛑 stopping Gotchi …")
        await self.hopper.stop()
        await self.deauth.stop()
        await self.sniffer.stop()
        for t in self._tasks:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t
        self._started = False
        self.log.info("✅ all subsystems stopped")

    async def run(self, duration: float | int | None = None,
                  crack: bool = False) -> None:
        """Fire up, optional sleep, optional crack, then shut down."""
        self.start()
        if duration:
            await asyncio.sleep(duration)
        await self.stop()
        if crack:
            self._run_auto_crack()

    def set_channel(self, channel: int) -> None:
        """Force all subsystems onto a specific channel."""
        self.log.info("⇄ forcing channel %d", channel)
        self.hopper._stopped.set()  # pause hop loop
        self.deauth.set_channel(channel)
        # iface.set_channel(channel) — real HW helper

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _on_pcap_closed(self, path: Path) -> None:
        """Callback from Rotator when a capture file is sealed."""
        self.log.info("💾 pcap saved → %s", path)
        await self.converter.convert(path)

    def _run_auto_crack(self) -> None:
        # Placeholder synchronous wrapper; real cracker is async-friendly
        self.log.info("🔐 launching auto-crack …")
        # self.converter.crack_all()  # real implementation


###############################################################################
# Singleton helpers for CLI scripts
###############################################################################

_singleton: Optional[Gotchi] = None


def start(cfg_path: str | Path | None = None) -> None:
    """Start a singleton Gotchi instance (used by CLI)."""
    global _singleton
    if _singleton is None:
        _singleton = Gotchi(cfg_path)
        _singleton.start()


def stop() -> None:
    """Stop the singleton instance."""
    global _singleton
    if _singleton:
        asyncio.run(_singleton.stop())
        _singleton = None


def set_channel(ch: int) -> None:
    """Force channel on singleton instance."""
    if _singleton:
        _singleton.set_channel(ch)


__all__ = [
    "Gotchi",
    "start",
    "stop",
    "set_channel",
]
