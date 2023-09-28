"""This module provides the fsql CLI."""
# lang/cli.py

import typer
from typing_extensions import Annotated
import json

from lang import (__app_name__, __version__, ql)

app = typer.Typer(rich_markup_mode="rich")

@app.command(epilog="See https://github.com/crbaker/fsql for more details.")
def query(query_text: Annotated[str, typer.Argument(help="The FSQL query to execute against the Firestore database.")]):
    try:
        results = ql.run_query(query_text)
        typer.echo(json.dumps(results, indent=2))
    except ValueError as e:
        typer.echo(e)
