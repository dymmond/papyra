from __future__ import annotations

from sayer import Sayer

from papyra import __version__
from papyra.cli.inspect.app import inspect
from papyra.cli.metrics.app import metrics
from papyra.cli.persistence.app import persistence

help_text = """
Papyra command line tool allowing to run command line utils

How to run Papyra native: `papyra <NAME>`.

    Example: `papyra inspect`
"""

app = Sayer(
    name="Papyra",
    help=help_text,
    add_version_option=True,
    version=__version__,
)


@app.callback(invoke_without_command=True)
def callback() -> None: ...


app.add_command(inspect)
app.add_command(persistence)
app.add_command(metrics)
