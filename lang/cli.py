"""This module provides the fsql CLI."""
# lang/cli.py

import os.path
import atexit

import typer
import json
import readline
from typing_extensions import Annotated, Optional
from rich import print as rprint, print_json

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
    print_json(json.dumps(results, indent=2))


def start_repl():
    go_again = True

    history_path = os.path.expanduser("~/.fsql_history")

    def save_history(history_path=history_path):
        readline.write_history_file(history_path)

    if os.path.exists(history_path):
        readline.set_history_length(100)
        readline.read_history_file(history_path)

    atexit.register(save_history)

    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind("set editing-mode vi")

    rprint("[italic pink]FSQL Repl[/italic pink] :fire:")

    current_query: str = None

    while go_again:

        if current_query is None:
            current_query = input('> ').strip()
        else:
            current_query = f"{current_query} {input(': ')}".strip()

        if current_query == "exit":
            go_again = False
            rprint("Bye!:waving_hand:")
        if current_query == "cls":
            typer.clear()
            current_query = None
        elif current_query.endswith(';'):
            try:
                run_query_and_output(current_query[:-1])
            except Exception as e:
                rprint("[italic red]Query Error[/italic red] :exploding_head:")
                rprint(e)
            finally:
                current_query = None
