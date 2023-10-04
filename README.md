# Firestore Query Language

FSQL is a Firestore Query Languate CLI tool that allows users to execute SQL Like queries against a Firestore database.

* Supports **SELECT**, **UPDATE** & **DELETE** queries
* Full featured **REPL**

<p align="center">
  <img src="./img/fsql-screenshot.png" alt="FSQL Repl" width="738">
</p>

## How It Works
The FSQL CLI tool allows for SQL-like queries to be executed against a Firestore database.

1. Firestore essentially has 3 different query contexts:
   * **Document**
     *  Documents are fetched by specifying the path to that document. This is accomplised in FSQL by making use of the `at` keyword.
   * **Collection**
     *  Collections contain a number of documents and are queried by making use of the `from` keyword.
   * **Collection Group**
     *  Collection Groups are essentially a grouping of collections that are named the same but exist within different Documents. Make use of the `within` keyword to query within a Collection Groups.
1. Using Lark, the input text is parsed and the Python Firebase SDK is used to execute queries against the Firestore database.

## Build & Install
1. Create a new virtual environment so that you can have an isolated python environment
```sh
virtualenv venv
source env_name/bin/activate
```
2. Install the required dependencies
```sh
pip install -r requirements.txt
```

3. Use `pyinstaller` to create an executable. A `dist` directory will be created which will include the executable.
```sh
pyinstaller --clean -n fsql --add-data "fsql.lark:." ./lang/__main__.py
./dist/fsql/fsql
```

## Usage

Make sure that the `GOOGLE_APPLICATION_CREDENTIALS` environment variable is set and pointing to a Google Cloud credentials json file

1. To start a FSQL REPL.
```sh
fsql
```
_Note: Commands can run over multiple lines in the REPL and should be terminated with a semi-colon_

2. Supply a query as an argument to the fsql executable to execute a command direcly from the command prompt
```sh
fsql 'select * from MyCollection where year == 2005 limit 5'
```

## Powerfull when used with `jq`
https://jqlang.github.io/jq/