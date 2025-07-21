"""
RotatingPcap – robust queue‑aware implementation
==============================================
Consumes handshake packets from an ``asyncio.Queue`` and writes them to
rolling **.pcapng** files using Scapy’s ``PcapNgWriter``.  Rotation is
triggered by maximum size *or* age, and shutdown is graceful even when
no further packets arrive.

Enhancements vs. original stub
------------------------------
* **Non‑blocking queue reads** – `asyncio.wait_for(..., timeout)` prevents the
  coroutine from hanging forever once `stop()` is called.
* **Sentinel support** – producers may enqueue ``RotatingPcap.SENTINEL`` to
  force an immediate final flush/close.
* **Monotonic timers** – uses ``time.perf_counter()`` for age calculations,
  immune to system‑clock jumps.
* **Guaranteed writer flush** – every close/rotate path calls
  ``writer.flush()`` before ``close()``.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

try:
    from scapy.utils import PcapNgWriter  # noqa: WPS433
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Scapy is required for capture.rotate → `pip install scapy`"
    ) from exc

log = logging.getLogger(__name__)


class RotatingPcap:
    """Write packets to rolling *.pcapng* files."""

    FILE_FMT = "%Y-%m-%d_%H%M%S"  # e.g. 2025-07-21_142359.pcapng
    SENTINEL = object()            # queue marker → finish early

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        *,
        folder: Path,
        max_size_mb: int = 10,
        max_age_s: float | None = 300,
        on_rotate: Optional[Callable[[Path], Awaitable[None] | None]] = None,
    ) -> None:
        self.folder: Path = folder.expanduser().resolve()
        self.folder.mkdir(parents=True, exist_ok=True)

        self.max_bytes: int = max_size_mb * 1024 * 1024
        self.max_age_s: float = float(max_age_s) if max_age_s else 0.0
        self.on_rotate = on_rotate

        self._writer: Optional[PcapNgWriter] = None
        self._current_path: Optional[Path] = None
        self._start_t: float = 0.0
        self._bytes: int = 0
        self._pkt_count: int = 0

        self._stop_evt = asyncio.Event()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def consume(self, queue: asyncio.Queue):
        """Coroutine – create via ``asyncio.create_task(rot.consume(q))``."""
        self._open_new_file()

        while not self._stop_evt.is_set():
            try:
                pkt = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if pkt is self.SENTINEL:
                log.debug("RotatingPcap received sentinel – finishing …")
                queue.task_done()
                break

            self._writer.write(pkt)
            self._bytes += len(bytes(pkt))
            self._pkt_count += 1
            queue.task_done()

            if self._should_rotate():
                await self._rotate()

        await self.stop(final_flush=True)

    async def stop(self, *, final_flush: bool = False):
        """Close writer and invoke callback. Safe to call multiple times."""
        if self._stop_evt.is_set() and not final_flush:
            return
        self._stop_evt.set()

        if self._writer:
            self._writer.flush()
            self._writer.close()
            await self._fire_callback(self._current_path)
            log.info(
                "⏹️  pcap writer closed (%d pkts, %s)",
                self._pkt_count,
                self._current_path,
            )
            self._writer = None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _should_rotate(self) -> bool:
        if self._bytes >= self.max_bytes:
            return True
        if self.max_age_s and (time.perf_counter() - self._start_t) >= self.max_age_s:
            return True
        return False

    # file handling ------------------------------------------------------ #
    def _open_new_file(self):
        ts = _dt.datetime.now().strftime(self.FILE_FMT)
        path = self.folder / f"{ts}.pcapng"
        writer = PcapNgWriter(str(path), append=False, sync=True)

        self._writer = writer
        self._current_path = path
        self._start_t = time.perf_counter()
        self._bytes = 0
        self._pkt_count = 0

        log.info("💾 capturing → %s", path)

    async def _rotate(self):
        """Close current file, invoke callback, start a new one."""
        if self._writer:
            self._writer.flush()
            self._writer.close()
            await self._fire_callback(self._current_path)

        self._open_new_file()

    async def _fire_callback(self, path: Optional[Path]):
        if path is None or self.on_rotate is None:
            return
        try:
            if asyncio.iscoroutinefunction(self.on_rotate):
                await self.on_rotate(path)
            else:
                self.on_rotate(path)
        except Exception:  # noqa: BLE001
            log.exception("on_rotate callback raised")

    # async‑context helper ---------------------------------------------- #
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop(final_flush=True)
