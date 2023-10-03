"""This module provides the fsql CLI."""
# lang/cli.py

import typer
from typing_extensions import Annotated, Optional
import json
import readline

from lang import (__app_name__, __version__, ql)

app = typer.Typer(rich_markup_mode="rich")


@app.command(epilog="See https://github.com/crbaker/fsql for more details.")
def query(query_text: Annotated[Optional[str], typer.Argument(help="The FSQL query to execute against the Firestore database.")] = None):
    try:
        if query_text is None:
            start_repl()
        else:
            run_query_and_output(query_text)
    except Exception as e:
        typer.echo(e)


def run_query_and_output(query_text):
    results = ql.run_query(query_text)
    typer.echo(json.dumps(results, indent=2))


def start_repl():
    go_again = True

    readline.parse_and_bind('tab: complete')
    readline.parse_and_bind('set editing-mode vi')

    while go_again:
        query_text = input('>: ')

        if (query_text.strip() == "exit"):
            go_again = False
            typer.echo("Bye!")
        else:
            try:
                run_query_and_output(query_text)
            except Exception as e:
                typer.echo(e)
