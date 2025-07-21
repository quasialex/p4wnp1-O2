"""
gotchi.hw.hop
=============

Asynchronous channel-hopper.

* Keeps a Wi-Fi interface in monitor mode
  marching through a list of 802.11 channels.
* Emits an `on_hop(channel: int)` callback every time it lands
  on a new channel so other subsystems (de-auth engine, sniffer,
  Pwnagotchi/Brucegotchi plugins, etc.) can react.

Typical usage
-------------

>>> hopper = ChannelHopper(
...     iface="wlan0mon",
...     channels=[1, 6, 11],
...     interval_s=0.4,
...     jitter_s=0.05,
...     on_hop=lambda ch: print(f"Hopped to {ch}")
... )
>>> hopper.start()
>>> await asyncio.sleep(10)
>>> await hopper.stop()
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .iface import set_channel  # relative import: gotchi.hw.iface

log = logging.getLogger(__name__)


class ChannelHopper:
    """
    Cycle through a list of channels at a fixed cadence.

    Parameters
    ----------
    iface:
        *Monitor-mode* interface name (e.g. ``wlan0mon``).
    channels:
        Iterable of integer channel numbers (e.g. ``[1, 6, 11]``).
    interval_s:
        Base delay between hops, in **seconds** (float permitted).
    jitter_s:
        Optional random ±jitter added to every hop
        to discourage predictable timing.
    on_hop:
        Optional callback ``callable(channel: int)``.
        Executed *after* the interface is set to the new channel.
    loop:
        Event-loop to run on.  Defaults to ``asyncio.get_event_loop()``.
    """

    def __init__(
        self,
        *,
        iface: str,
        channels: Iterable[int],
        interval_s: float,
        jitter_s: float = 0.0,
        on_hop: Optional[Callable[[int], None]] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.iface: str = iface
        self.channels: List[int] = list(channels)
        if not self.channels:
            raise ValueError("Channel list cannot be empty")

        self.interval_s: float = interval_s
        self.jitter_s: float = max(0.0, jitter_s)
        self.on_hop = on_hop
        self.loop = loop or asyncio.get_event_loop()

        # Internal state
        self._task: Optional[asyncio.Task] = None
        self._stop_evt = asyncio.Event()
        self._pause_evt = asyncio.Event()     # set() == *paused*
        self._pause_evt.clear()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Launch the hop loop (non-blocking).  Safe to call twice."""
        if self._task and not self._task.done():
            return
        self._stop_evt.clear()
        self._task = self.loop.create_task(self._loop())

    async def stop(self) -> None:
        """Stop the hop loop and wait for the task to finish."""
        self._stop_evt.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        log.info("⏹️  channel-hopper stopped")

    def pause(self) -> None:
        """Pause hopping (stays on current channel)."""
        self._pause_evt.set()

    def resume(self) -> None:
        """Resume hopping if previously paused."""
        self._pause_evt.clear()

    def set_channels(self, channels: Iterable[int]) -> None:
        """Replace the hop list on the fly."""
        new_list = list(channels)
        if not new_list:
            raise ValueError("Channel list cannot be empty")
        self.channels[:] = new_list
        log.info("🔀 channel list updated → %s", self.channels)

    # ------------------------------------------------------------------ #
    # The hop loop
    # ------------------------------------------------------------------ #

    async def _loop(self) -> None:
        idx = 0
        hop_count = 0
        log.info("▶️  channel-hopper started (%s → %s)",
                 self.iface, self.channels)

        while not self._stop_evt.is_set():
            # honour pause
            if self._pause_evt.is_set():
                await asyncio.sleep(0.1)
                continue

            channel = self.channels[idx]
            try:
                set_channel(self.iface, channel)
            except Exception as exc:  # noqa: BLE001
                log.warning("⚠️  failed to set channel %d: %s", channel, exc)
            else:
                hop_count += 1
                if self.on_hop:
                    try:
                        self.on_hop(channel)
                    except Exception:  # noqa: BLE001
                        log.exception("on_hop callback raised")

            # advance index with wrap-around
            idx = (idx + 1) % len(self.channels)

            # adaptive sleep: base ± jitter
            sleep_for = self.interval_s
            if self.jitter_s:
                sleep_for += random.uniform(-self.jitter_s, self.jitter_s)
                sleep_for = max(0.01, sleep_for)  # clamp to sane min
            await asyncio.sleep(sleep_for)

        log.debug("channel-hopper exited after %d hops", hop_count)
