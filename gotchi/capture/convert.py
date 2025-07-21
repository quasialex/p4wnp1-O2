"""
Convert & Crack Module
======================
Turns rotated *.pcapng* files into Hashcat‑ready *.22000* files via
**hcxpcapngtool** and (optionally) spawns a background Hashcat session.

Key upgrades vs. first draft
----------------------------
* `Path(wordlist).expanduser()` so `~/` paths resolve on POSIX.
* Unified attribute name: `self.hcx_bin` ⇢ `self.hcxpcapngtool_bin` for
  clarity (constructor arg kept identical for backward compatibility).
* All subprocess invocations wrapped in a reusable async helper with
  *stdout* streaming to logger when `DEBUG`.
* Graceful error handling – converts still succeed even if Hashcat is
  missing or exits non‑zero; the exception is logged but does not crash
  the main pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

###############################################################################
# Async‑subprocess helper
###############################################################################

async def _run(cmd: List[str]) -> None:
    """Run *cmd*; raise RuntimeError on non‑zero exit."""
    log.debug("$ %s", shlex.join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode:
        raise RuntimeError(
            f"{cmd[0]} exited {proc.returncode}\n" + stdout.decode(errors="replace")
        )
    if stdout and log.isEnabledFor(logging.DEBUG):
        log.debug(stdout.decode(errors="replace"))

###############################################################################
# Converter class
###############################################################################

class Converter:
    """pcapng → 22000 converter + optional Hashcat launcher."""

    def __init__(
        self,
        *,
        crack_auto: bool = False,
        wordlists: Optional[List[str]] = None,
        hcxpcapngtool_bin: str = "hcxpcapngtool",
        hashcat_bin: str = "hashcat",
    ) -> None:
        self.crack_auto = crack_auto
        # expand ~ and keep only existing wordlists
        self.wordlists: List[Path] = [
            Path(w).expanduser() for w in (wordlists or []) if Path(w).expanduser().exists()
        ]
        self.hcxpcapngtool_bin = hcxpcapngtool_bin
        self.hashcat_bin = hashcat_bin

    # ------------------------------------------------------------------ #
    # Public API – called by Rotator
    # ------------------------------------------------------------------ #

    async def convert(self, pcap_path: Path) -> Path:
        """Convert *pcap_path* to *.22000* and maybe crack."""
        pcap_path = pcap_path.expanduser().resolve()
        out22000 = pcap_path.with_suffix(".22000")

        await _run([
            self.hcxpcapngtool_bin,
            "-o",
            str(out22000),
            str(pcap_path),
        ])
        log.info("🔁 converted → %s", out22000.name)

        if self.crack_auto and self.wordlists:
            asyncio.create_task(self._launch_hashcat(out22000))
        return out22000

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _launch_hashcat(self, hfile: Path) -> None:
        """Background Hashcat execution (non‑blocking)."""
        wl = self.wordlists[0]  # first existing list already verified
        pot = hfile.with_suffix(".pot.txt")
        try:
            await _run([
                self.hashcat_bin,
                "-m",
                "22000",
                str(hfile),
                str(wl),
                "--potfile-path",
                str(pot),
                "--force",
                "--quiet",
                "--status",
            ])
            log.info("🔓 hashcat finished for %s (pot: %s)", hfile.name, pot.name)
        except Exception as exc:  # noqa: BLE001
            log.warning("Hashcat run failed: %s", exc)

__all__ = ["Converter"]
