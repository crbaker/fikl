"""This module provides the fikl CLI."""
# lang/cli.py

import os.path
import os
import atexit
import readline
import json

import typer
from typing_extensions import Annotated
from rich import print as rprint, print_json

from lang import ql

app = typer.Typer(rich_markup_mode="rich")

QUERY_COMMAND_HELP = "The query to execute against the Firestore database."

@app.command(epilog="See https://github.com/crbaker/fikl for more details.")
def query(query_text: Annotated[(str), typer.Argument(help=QUERY_COMMAND_HELP)] = None):
    """
    Typer command handler to handle the query command.
    """
    try:
        if (env_var := 'GOOGLE_APPLICATION_CREDENTIALS') not in os.environ:
            rprint(f"""[italic yellow]Warning: ${env_var} is not set[/italic yellow]""")

        if query_text is None:
            start_repl()
        else:
            run_query_and_output(query_text)
    except ql.QueryError as exception:
        typer.echo(exception)


def run_query_and_output(query_text):
    """
    Runs the supplied query and outputs the results.
    """
    results = ql.run_query(query_text)
    print_json(json.dumps(results, indent=2))


def start_repl():
    """
    Sets up and start the FIKL REPL
    """
    go_again = True

    history_path = os.path.expanduser("~/.fikl_history")

    def save_history(history_path=history_path):
        readline.write_history_file(history_path)

    if os.path.exists(history_path):
        readline.set_history_length(100)
        readline.read_history_file(history_path)

    atexit.register(save_history)

    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind("set editing-mode vi")

    rprint("[italic pink]FIKL Repl[/italic pink] :fire:")

    current_query: str = None

    while go_again:

        if current_query is None or current_query.strip() == "":
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
            except ql.QueryError as exception:
                rprint("[italic red]Query Error[/italic red] :exploding_head:")
                rprint(exception)
            finally:
                current_query = None
