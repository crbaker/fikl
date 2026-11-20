# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FIKL is a Python CLI + REPL that runs SQL-like queries (`select`, `update`, `insert`, `delete`, `show collections`) against a Firestore database. README.md documents the query language from a user's perspective.

## Commands

Run everything from the repo root: the grammar file `fikl.lark` is loaded relative to the current working directory (see `resource_path` in `lang/transformer.py`), so tests and the CLI fail if run elsewhere.

```sh
pip install -r requirements.txt          # deps (a .venv exists locally)
pylint $(git ls-files '*.py')            # lint, as run in CI (config: .pylintrc)
python -m unittest                       # all tests, as run in CI (Python 3.11)
python -m unittest tests.test_grammar.TestTransformer.test_should_parse_valid_select_query   # single test
python -m coverage run -m unittest && coverage report && coverage html   # coverage
python -m lang 'select * from MyCollection limit 5'   # run a query without building
python -m lang                                         # start the REPL
pyinstaller --clean -y -n fikl --add-data "fikl.lark:." ./lang/__main__.py   # build ./dist/fikl/fikl
```

Running real queries needs `GOOGLE_APPLICATION_CREDENTIALS` pointing to a service-account JSON; `firebase_admin.initialize_app()` uses default credentials.

## Architecture

The pipeline is: query string → Lark grammar → transformer → `FIKLQuery` dict → executor → formatted output.

- **`fikl.lark`**: the Lark grammar (basic lexer). Each `instruction` alternative carries an alias (`-> select_collection`, `-> update_document`, etc.) that must match a method name on `FIKLTree`. `from` = collection, `within` = collection group, `at` = single document path. A `^` after a property in `where`/`order by` marks it for local (client-side) evaluation.
- **`lang/transformer.py`**: `FIKLTree` (a Lark `Transformer`) turns the parse tree into `TypedDict`s (`FIKLSelectQuery`, `FIKLUpdateQuery`, `FIKLInsertQuery`, …) with enums for query type, subject type, output type and format. `parse()` wraps any failure in `QuerySyntaxError`. Literal values are converted with `ast.literal_eval`. Adding a language feature usually means editing both the grammar and the matching transformer method.
- **`lang/ql.py`**: execution. `run_query()` parses, then `execute_query()` dispatches on `query_type`. `execute_select_query` builds the Firestore query from the non-local `where`/`order` clauses, fetches results (using `limit`, or cursor-based batches with `start_after` + `Retry` for `page N`), then applies `filter_locally` and `sort_locally` for the `^` clauses. Update and delete reuse `execute_select_query` and then mutate each doc's reference. After fetching, `run_query` converts snapshots to dicts (adds `_path`, trims to the requested fields with dot-notation support), applies `group by`, then `count`/`distinct`, and outputs JSON or CSV (pandas, flattened keys) to stdout, a file (`output "path"`) or the clipboard (`copy`). Any non-`QueryError` exception is wrapped in `QueryError`.
- **`lang/cli.py`**: Typer app with one command. Given a query argument it runs it once; otherwise it starts a readline REPL (vi mode, history in `~/.fikl_history`, statements end with `;`, `exit`/`cls` are special).

Notes:
- The grammar accepts `sum`/`avg`/`min`/`max`, but `function_for_query` only implements `count` and `distinct`. The others are silent no-ops.
- `like` only works on local (`^`) properties. `add_where_clauses` raises a `QueryError` if it reaches Firestore.
- `not_in` in the grammar is mapped to Firestore's `not-in`.
- Tests (`tests/test_grammar.py`) cover parsing and transformation only. Nothing in `ql.py` that touches Firestore is tested.
