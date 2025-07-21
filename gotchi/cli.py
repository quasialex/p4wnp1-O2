"""
gotchi.cli
==========

Command-line entry-point for all Gotchi operations.

Usage examples
--------------

$ python -m gotchi harvest --iface wlan0 --duration 180s
$ python -m gotchi live --iface wlan0 --config ./labs.toml
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

from . import Gotchi, start, stop  # façade functions

###############################################################################
# Typer app
###############################################################################

app = typer.Typer(
    name="gotchi",
    help="Wi-Fi deauth + WPA-handshake harvesting toolkit",
    rich_markup_mode="rich",
)

###############################################################################
# Global options helpers
###############################################################################

def _duration_callback(value: str | None) -> Optional[float]:
    """Convert human-friendly duration strings to seconds."""
    if value is None:
        return None
    if value.endswith("s"):
        return float(value[:-1])
    if value.endswith("m"):
        return 60 * float(value[:-1])
    if value.endswith("h"):
        return 3600 * float(value[:-1])
    return float(value)  # assume bare seconds


def _setup_logging(quiet: bool):
    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

###############################################################################
# Commands
###############################################################################

@app.command(help="One-shot scan/deauth/capture for a fixed duration.")
def harvest(
    iface: str = typer.Option(..., help="Physical Wi-Fi interface (e.g. wlan0)"),
    duration: str = typer.Option(
        "180s",
        callback=_duration_callback,
        help="Run time (Ns / Nm / Nh, default: 180s)",
    ),
    wordlist: Optional[Path] = typer.Option(
        None,
        exists=True,
        dir_okay=False,
        help="Wordlist path → triggers auto-crack",
    ),
    config: Optional[Path] = typer.Option(
        None, exists=True, dir_okay=False, help="Alternate config.toml path"
    ),
    quiet: bool = typer.Option(False, "-q", help="Quiet mode (warnings only)"),
):
    _setup_logging(quiet)

    # override cfg path & wordlist on-the-fly
    g = Gotchi(cfg_path=config)
    # honour --iface flag
    g.cfg.setdefault("hw", {})["iface"] = iface
                     
    if wordlist:
        g.converter.wordlists = [str(wordlist.expanduser())]
        g.converter.crack_auto = True

    async def _run():
        with g:
            await g.run(duration=duration, crack=g.converter.crack_auto)

    typer.echo("[bold cyan]Starting harvest…[/bold cyan]")
    _run_with_spinner(_run)
    typer.echo("[green]Done.[/green]")


@app.command(help="Run Gotchi in [bold]live service[/bold] mode until ^C.")
def live(
    iface: str = typer.Option(..., help="Physical Wi-Fi interface"),
    config: Optional[Path] = typer.Option(
        None, exists=True, dir_okay=False, help="Alternate config.toml path"
    ),
    quiet: bool = typer.Option(False, "-q"),
):
    _setup_logging(quiet)
    g = Gotchi(cfg_path=config)
    g.cfg.setdefault("hw", {})["iface"] = iface

    async def _run_forever():
        with g:
            while True:
                await asyncio.sleep(3600)
                
    typer.echo("[bold cyan]Live mode – press Ctrl-C to stop.[/bold cyan]")
    try:
        _run_with_spinner(_run_forever)
    except KeyboardInterrupt:
        typer.echo("\n[red]User break – shutting down…[/red]")


###############################################################################
# Helper: run async task with a nice spinner
###############################################################################

def _run_with_spinner(coro):
    """Block the main thread, show spinner until coroutine finishes."""
    with Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        TimeElapsedColumn(),
        transient=True,
    ) as prog:
        task = prog.add_task("[cyan]Running…")
        try:
            asyncio.run(coro())
        finally:
            prog.update(task, description="[green]Finished")


###############################################################################
# Module entry-point
###############################################################################

if __name__ == "__main__":
    # Allow:  python -m gotchi harvest ...
    sys.argv[0] = "gotchi"
    app()
