"""
gotchi.hw.iface
===============

Low-level helpers for Wi-Fi interface manipulation.

All calls shell out to `ip` and `iw`, so they *require* root privileges
and a Linux kernel ≥ 2.6.31 with mac80211-compatible drivers.

Public functions
----------------
up(iface, channel=None, tx_power_dbm=None)   → str
down(iface)                                  → None
set_channel(iface, channel)                  → None
set_tx_power(iface, dbm)                     → None
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from shutil import which
from typing import Final, Iterable, List, Sequence

log = logging.getLogger(__name__)

################################################################################
# Preconditions
################################################################################

_IP: Final = which("ip") or "/sbin/ip"
_IW: Final = which("iw") or "/sbin/iw"

for _bin in (_IP, _IW):
    if not Path(_bin).exists():
        raise RuntimeError(f"Required binary not found: {_bin}")

################################################################################
# Helpers
################################################################################


def _run(cmd: Sequence[str]) -> None:
    """Run command, log it, raise on non-zero exit."""
    log.debug("$ %s", " ".join(cmd))
    subprocess.check_call(list(cmd), stderr=subprocess.STDOUT)


def _iface_is_mon(iface: str) -> bool:
    """Return *True* if iface is already of type ``monitor``."""
    out = subprocess.check_output([_IW, "dev", iface, "info"], text=True)
    m = re.search(r"type\s+(\w+)", out)
    return bool(m and m.group(1) == "monitor")


def _suffix_monitor(iface: str) -> str:
    """Return iface name with ``mon`` suffix (e.g. wlan0 → wlan0mon)."""
    return iface if iface.endswith("mon") else f"{iface}mon"


################################################################################
# Public API
################################################################################


def up(iface: str,
       channel: int | None = None,
       tx_power_dbm: int | None = None,
       preserve_name: bool = False) -> str:
    """
    Switch *iface* to monitor mode and bring it up.

    Parameters
    ----------
    iface
        The physical wireless interface (e.g. ``wlan0``).
    channel
        Optional initial channel number.
    tx_power_dbm
        Optional transmit-power limit in dBm.
    preserve_name
        If *True*, keep the original name (changes the *type* only).
        Otherwise append ``mon`` (default Pwnagotchi/Brucegotchi style).

    Returns
    -------
    str
        The name of the *monitor-mode* interface.
    """
    mon_iface = iface if preserve_name else _suffix_monitor(iface)

    # 1. Bring interface down
    _run([_IP, "link", "set", iface, "down"])

    # 2. Change type → monitor
    if preserve_name:
        _run([_IW, iface, "set", "type", "monitor"])
    else:
        # create separate "mon" interface if driver supports it
        if mon_iface != iface:
            # If it already exists, delete to avoid “Device busy”
            if Path(f"/sys/class/net/{mon_iface}").exists():
                _run([_IW, "dev", mon_iface, "del"])
            _run([_IW, "dev", iface, "interface", "add", mon_iface, "type", "monitor"])
        iface = mon_iface

    # 3. Bring monitor interface up
    _run([_IP, "link", "set", iface, "up"])

    # 4. Set channel / TX power if asked
    if channel is not None:
        set_channel(iface, channel)
    if tx_power_dbm is not None:
        set_tx_power(iface, tx_power_dbm)

    log.info("🛜 %s up (monitor mode%s)", iface,
             f", ch {channel}" if channel else "")
    return iface


def down(iface: str) -> None:
    """
    Return *iface* to managed mode and bring it back up.

    If *iface* ends with ``mon`` and the matching **parent** interface exists,
    we simply delete the monitor child.  Otherwise we reset the *type*.
    """
    if iface.endswith("mon"):
        parent = iface[:-3]
        if Path(f"/sys/class/net/{parent}").exists():
            log.info("↩️  deleting monitor iface %s", iface)
            _run([_IW, "dev", iface, "del"])
            _run([_IP, "link", "set", parent, "up"])
            return

    log.info("↩️  restoring %s to managed mode", iface)
    _run([_IP, "link", "set", iface, "down"])
    _run([_IW, iface, "set", "type", "managed"])
    _run([_IP, "link", "set", iface, "up"])


def set_channel(iface: str, channel: int) -> None:
    """Hard-lock *iface* to an 802.11 channel."""
    _run([_IW, iface, "set", "channel", str(channel)])
    log.debug("⇄ %s → ch %d", iface, channel)


def set_tx_power(iface: str, dbm: int) -> None:
    """
    Set transmit power of *iface*.

    Notes
    -----
    * Many regulatory domains cap this at 20 dBm (100 mW).
    * Driver/hardware support varies.
    """
    _run([_IW, iface, "set", "txpower", "fixed", str(dbm * 100)])
    log.debug("⚡ %s tx-power set to %d dBm", iface, dbm)
