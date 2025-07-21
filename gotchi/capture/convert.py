"""
gotchi.capture.convert
======================

* Convert .pcapng files from RotatingPcap into Hashcat's .22000 format
  via **hcxpcapngtool**.
* Optionally kick off `hashcat` right away (common for quick demos).

Public class
------------
Converter(crack_auto: bool = False, wordlists: list[str] = None)

Awaitable method
----------------
await convert(path: Path)     # returns Path to .22000 file
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)


class Converter:
    def __init__(
        self,
        *,
        crack_auto: bool = False,
        wordlists: Optional[List[str]] = None,
        hcxdumptool_bin: str = "hcxpcapngtool",
        hashcat_bin: str = "hashcat",
    ):
        self.crack_auto = crack_auto
        self.wordlists = wordlists or []
        self.hcx_bin = hcxdumptool_bin
        self.hashcat_bin = hashcat_bin

    # ------------------------------------------------------------------ #
    # Main entry point (called by RotatingPcap)
    # ------------------------------------------------------------------ #
    async def convert(self, pcap_path: Path) -> Path:
        """
        Convert *pcap_path* → *.22000* file and, if configured, launch
        Hashcat in a detached asyncio task.

        Returns
        -------
        Path
            The newly-created `.22000` path.
        """
        two22000 = pcap_path.with_suffix(".22000")
        cmd = [
            self.hcx_bin,
            "-o", str(two22000),
            str(pcap_path),
        ]
        await _run_subproc(cmd)
        log.info("🔁 converted → %s", two22000)

        if self.crack_auto and self.wordlists:
            asyncio.create_task(self._crack(two22000))

        return two22000

    # ------------------------------------------------------------------ #
    # Internal: Hashcat launcher
    # ------------------------------------------------------------------ #
    async def _crack(self, hfile: Path) -> None:
        """
        Fire-and-forget Hashcat run.  Uses mode *22000* and
        first word-list that exists.
        """
        wl = next((Path(w) for w in self.wordlists if Path(w).exists()), None)
        if wl is None:
            log.warning("⚠️  no wordlist found for auto-crack")
            return

        out_pot = hfile.with_suffix(".pot.txt")
        cmd = [
            self.hashcat_bin,
            "-m", "22000",
            str(hfile),
            str(wl),
            "--potfile-path", str(out_pot),
            "--force",                # assume user knows the risks
            "--quiet",
            "--status",
        ]
        log.info("🔓 launching hashcat → %s …", hfile.name)
        await _run_subproc(cmd)
        log.info("✅ hashcat finished for %s", hfile.name)


# ----------------------------------------------------------------------- #
# Helper: async wrapper around subprocess
# ----------------------------------------------------------------------- #
async def _run_subproc(cmd: List[str]) -> None:
    """Run *cmd* and raise if it exits non-zero."""
    log.debug("$ %s", shlex.join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"{cmd[0]} failed ({proc.returncode}):\n{stdout.decode()}")
