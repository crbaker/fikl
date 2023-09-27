"""This module provides the fsql CLI."""
# lang/cli.py

import typer
import json

from lang import (__app_name__, __version__, ql)

app = typer.Typer()

@app.command()
def query(query_text: str):
    try:
        results = ql.run_query(query_text)
        typer.echo(json.dumps(results, indent=2))
    except ValueError as e:
        typer.echo(e)
