"""
gotchi.capture.rotate
=====================

RotatingPcap
------------

* Consumes 802.11 packets (from `asyncio.Queue`)
* Writes to a .pcapng file via Scapy's PcapNgWriter
* Rotates by **max_size_mb** or **max_age_s** (whichever occurs first)
* Calls an async-aware `on_rotate(Path)` callback every time a file closes
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import os
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
    """
    Parameters
    ----------
    folder
        Destination folder (will be created).
    max_size_mb
        Maximum file size before rotation (MiB).
    max_age_s
        Maximum file age before rotation (seconds).
        Use 0 or ``None`` to disable time-based rotation.
    on_rotate
        Callable invoked **after** a file is closed.  Accepts `Path`.
        Can be async or sync.
    """

    FILE_FMT = "%Y-%m-%d_%H%M%S"  # e.g. 2025-07-21_142359.pcapng

    def __init__(
        self,
        *,
        folder: Path,
        max_size_mb: int = 10,
        max_age_s: int | float | None = 300,
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

        self._stop_evt = asyncio.Event()

    # ───────────────────────── public API ───────────────────────── #

    async def consume(self, queue: asyncio.Queue) -> None:
        """
        Coroutine: call inside `asyncio.create_task()`.

        Example
        -------
        >>> rot = RotatingPcap(folder=Path("captures"), max_size_mb=5)
        >>> asyncio.create_task(rot.consume(pkt_queue))
        """
        self._open_new_file()

        while not self._stop_evt.is_set():
            pkt = await queue.get()
            self._writer.write(pkt)
            self._bytes += len(bytes(pkt))

            if self._should_rotate():
                await self._rotate()

    async def stop(self) -> None:
        """Gracefully close the current file and stop `consume()`."""
        self._stop_evt.set()
        if self._writer:
            self._writer.close()
            await self._fire_callback(self._current_path)  # last file
            log.info("⏹️  RotatingPcap shut down")

    # ───────────────────────── internals ───────────────────────── #

    # rotation criteria -------------------------------------------------- #
    def _should_rotate(self) -> bool:
        if self._bytes >= self.max_bytes:
            return True
        if self.max_age_s and (time.time() - self._start_t) >= self.max_age_s:
            return True
        return False

    # file handling ------------------------------------------------------ #
    def _open_new_file(self) -> None:
        ts = _dt.datetime.now().strftime(self.FILE_FMT)
        path = self.folder / f"{ts}.pcapng"
        writer = PcapNgWriter(str(path), append=False, sync=True)

        self._writer = writer
        self._current_path = path
        self._start_t = time.time()
        self._bytes = 0

        log.info("💾 capturing → %s", path)

    async def _rotate(self) -> None:
        """Close current file, fire callback, open a fresh writer."""
        if self._writer:
            self._writer.close()
            await self._fire_callback(self._current_path)

        self._open_new_file()

    async def _fire_callback(self, path: Optional[Path]) -> None:
        """Invoke `on_rotate` (supports both sync & async)."""
        if path is None or self.on_rotate is None:
            return
        try:
            if asyncio.iscoroutinefunction(self.on_rotate):
                await self.on_rotate(path)
            else:
                self.on_rotate(path)
        except Exception:  # noqa: BLE001
            log.exception("on_rotate callback raised")

    # context-manager sugar (optional) ----------------------------------- #
    async def __aenter__(self):  # noqa: D401
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        await self.stop()
