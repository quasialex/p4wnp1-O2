"""
gotchi.capture.sniff
====================

Asynchronous packet sniffer focused on WPA-handshake harvesting.

Key features
------------
* Uses **Scapy’s AsyncSniffer** so sniffing runs in its own thread without
  blocking the event-loop.
* Passes only **EAPOL** or **PMKID-carrying association frames** into
  an `asyncio.Queue` (you can widen the filter if needed).
* Gracefully stops on request; no orphaned threads.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Callable, Optional

try:
    # scapy layers
    from scapy.all import (
        AsyncSniffer,
        Dot11,
        Dot11AssoResp,
        Dot11Auth,
        Dot11Beacon,
        Dot11ProbeResp,
        EAPOL,
    )  # noqa: WPS433
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Scapy is required for capture.sniff → `pip install scapy`"
    ) from exc


log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helper: default packet filter
# --------------------------------------------------------------------------- #
def _is_handshake(pkt) -> bool:  # noqa: ANN001
    """
    Return *True* if *pkt* looks like part of a WPA handshake.

    The heuristic:
    * any frame with an **EAPOL** layer
    * or an Association-Response / Probe-Response whose payload
      advertises an RSN IE with PMKID (scapy decodes it for us)
    """
    if pkt.haslayer(EAPOL):
        return True
    if pkt.haslayer(Dot11):
        if pkt.haslayer(Dot11AssoResp) or pkt.haslayer(Dot11ProbeResp):
            # RSN tags live under Dot11Elt → scapy decodes automatically
            rsn = pkt[Dot11].getfieldval("RSNinfo")
            if rsn:
                return True
    return False


# --------------------------------------------------------------------------- #
# The Sniffer class
# --------------------------------------------------------------------------- #
class Sniffer:
    """
    Background packet collector.

    Parameters
    ----------
    iface
        Monitor-mode interface (``wlan0mon``).
    queue
        Asyncio queue packets will be pushed into.
    lfilter
        Callable applied to each packet.  Defaults to `_is_handshake`.
    store
        If *True*, Scapy keeps an internal list copy (memory heavy).
        We set it *False* because we forward to our own queue.
    """

    def __init__(
        self,
        iface: str,
        queue: asyncio.Queue,
        *,
        lfilter: Optional[Callable] = None,
        store: bool = False,
    ):
        self.iface = iface
        self.queue = queue
        self.lfilter = lfilter or _is_handshake
        self.store = store

        self._sniffer: Optional[AsyncSniffer] = None
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Spin up the AsyncSniffer thread and companion watcher task."""
        if self._sniffer and self._sniffer.running:
            return

        # Scapy thread pumps packets → _enqueue()
        self._sniffer = AsyncSniffer(
            iface=self.iface,
            prn=self._enqueue,
            store=self.store,
            lfilter=self.lfilter,
        )
        self._sniffer.start()
        log.info("📡 Sniffer started on %s", self.iface)

        # watchdog that awaits sniffer.join() when we cancel it
        self._task = asyncio.create_task(self._watchdog())

    async def stop(self) -> None:
        """Stop sniffer & join its thread."""
        if not self._sniffer:
            return
        self._sniffer.stop()          # ask thread to exit
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._sniffer = None
        self._task = None
        log.info("⏹️  Sniffer stopped")

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _enqueue(self, pkt) -> None:  # noqa: ANN001
        """Callback Scapy calls for every captured frame."""
        try:
            self.queue.put_nowait(pkt)
        except asyncio.QueueFull:  # pragma: no cover
            log.warning("Packet queue full; dropping frame")

    async def _watchdog(self) -> None:
        """Join the sniffer thread; exits when AsyncSniffer finishes."""
        if not self._sniffer:
            return
        await asyncio.to_thread(self._sniffer.join)
