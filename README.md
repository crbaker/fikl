### Make sure to use virtualenv

### To install requirements
pip install -r requirements.txt \

### To build an executable
pyinstaller -F -n fsql ./lang/__main__.py  \

and then you can run the fsql comand 

`./dist/fsql "[QUERY]"`

Make sure that the `GOOGLE_APPLICATION_CREDENTIALS` environment variable is set and pointing to a Google Cloud credentials json file

#### Examples

To select from a Collection Group: \
`fsql 'from Scripts` \
To select from a Collection Group with a `where`: \
`fsql 'from Scripts where uid == "asdasdasdas"'`

To select from a Collection: \
`fsql 'at Users'`

To select from a Collection with a `where`: \
`fsql 'at Users where email == "chris@emguidance.com"'`

To select a specific document: \
`fsql 'at Users/VQyxGrdksLUta1rM68SIgvv9HHY2`

pip freeze --local > requirements.txt \

### Powerfull when used with `jq`
https://jqlang.github.io/jq/