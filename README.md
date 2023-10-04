### Make sure to use virtualenv

### To get locally used modules
`pip freeze --local > requirements.txt \`
### To install requirements
`pip install -r requirements.txt \`

### To build an executable
`pyinstaller --clean -n fsql --add-data "fsql.lark:." ./lang/__main__.py`

and then you can run the fsql comand from the shell

`./dist/fsql "[QUERY]"`

Make sure that the `GOOGLE_APPLICATION_CREDENTIALS` environment variable is set and pointing to a Google Cloud credentials json file

## Examples

### Collection Group Query
>A collection group query fetches documents from a collection group and uses the `within` keyword to indicate that a Collection Group is being queried.

#### General Form:
`select [FIELDS | *] within [COLLECTION_GROUP] [where [FIELD] [OPERATOR] [LITERAL]]`

`select * within Scripts where scriptId == "ABCNFRGH"`

### Collection Query
>A collection query fetches documents from a collection and uses the `from` keyword to indicate that a Collection is being queried.

#### General Form:
`select [FIELDS | *] from [COLLECTION_PATH] [where [FIELD] [OPERATOR] [LITERAL]]`

`select * from Users where uid == "1234566"`

### Document Fetch
>A collection query fetches a documents and uses the `at` keyword to indicate that a Document is being requested.\
 _Note: Even though a single document is being requested, the result is still a list, either empty if the document does not exist or a list of length 1._

#### General Form:
`select [FIELDS | *] at [DOCUMENT_PATH]`

`select * at Users/VQyxGrdksLUta1rM68SIgvv9HHY2`

## Powerfull when used with `jq`
https://jqlang.github.io/jq/