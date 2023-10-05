"""transformer for lark processing."""
import ast
import os
import sys

from enum import Enum
from typing import TypedDict
from typing import Union
from lark import Lark, Transformer, v_args, Tree

AllTypes = Union[int, float, str, bool, None]


class QuerySyntaxError(Exception):
    """Raised when the syntax of the query is invalid."""


class FSQLQueryType(Enum):
    """The different kinds of supported query types."""
    SELECT = 1
    UPDATE = 2
    DELETE = 3
    SHOW = 4
    INSERT = 5


class FSQLSubjectType(Enum):
    """The different kinds of supported subject types that can be queried."""
    COLLECTION_GROUP = 1
    DOCUMENT = 2
    COLLECTION = 3


class FSQLWhere(TypedDict):
    """The defniition of a where clause."""
    field: str
    operator: str
    value: int | float | str | list[any]


class FSQLQuery(TypedDict):
    """The definition of a query. This is the base definition for all queries."""
    query_type: FSQLQueryType
    subject: str | None
    subject_type: FSQLSubjectType
    where: list[FSQLWhere] | None


class FSQLUpdateSet(TypedDict):
    """The definition of a setter that is used when updating a Firestore record."""
    property: str
    value: AllTypes


class FSQLUpdateQuery(FSQLQuery):
    """The definition of an update query."""
    set: list[FSQLUpdateSet]


class FSQLInsertQuery(FSQLQuery):
    """The definition of an insert query."""
    set: list[FSQLUpdateSet]
    identifier: str


class FSQLSelectQuery(FSQLQuery):
    """The definition of a select query."""
    fields: list[str] | str
    limit: int | None
    output: str | None


@v_args(inline=True)    # Affects the signatures of the methods
class FSQLTree(Transformer):
    """The transformer class that is used to transform the Lark parse tree into a FSQLQuery."""

    def __init__(self):
        super().__init__()
        self.vars = {}

    def _data_value(self, some_tree: Tree, data: str):
        """Gets the value of a data node."""
        data_tree: list[Tree] = list(some_tree.find_data(data))
        return data_tree[0].children[0].value

    def _as_value(self, some_tree: Tree) -> AllTypes:
        """
        Gets the value of a node. Depending on the type of the node
        the Python AST will be invoked to convert the value to the appropriate type.
        """
        match some_tree.children[0].type:
            case "CNAME":
                return some_tree.children[0].value
            case "NULL":
                return None
            case _:
                return ast.literal_eval(some_tree.children[0].value)

    def _as_fsql_match(self, where: Tree) -> AllTypes | list[AllTypes] | None:
        """
        Gets the value of a match node.
        Depending on the type of the node, the Python AST will be invoked to
        convert the value to the appropriate type.
        """
        matching = list(where.find_data('matching'))[0].children[0]

        if matching.data == 'literal':
            return ast.literal_eval(self._data_value(matching, "literal"))

        if matching.data == "array":
            return [ast.literal_eval(token.children[0].value)
                    for token in list(matching.find_data("literal"))]

        return None

    def _as_limit(self, limit: Tree | None) -> list[FSQLWhere] | None:
        """Gets the limit value that is specified in the query."""
        if limit is None:
            return None
        return self._as_value(limit)

    def _as_output(self, output: Tree | None) -> list[FSQLWhere] | None:
        """Gets the output value that is specified in the query."""
        if output is None:
            return None
        return self._as_value(output)

    def _as_where(self, where: Tree | None) -> list[FSQLWhere] | None:
        """Gets the where clause that is specified in the query."""
        if where is None:
            return None

        def token_as_where(token) -> FSQLWhere:
            matching = list(token.find_data("property"))[0]
            return {
                'field': self._as_value(matching),
                'operator': self._data_value(token, 'operator'),
                'value': self._as_fsql_match(token)
            }

        return [token_as_where(token) for token in list(where.find_data("comparrison"))]

    def _as_identifier(self, identifier: Tree):
        """Gets the identifier that is specified in the query."""
        if identifier is None:
            return None

        return self._as_value(list(identifier.find_data("property"))[0])

    def _as_setters(self, setter: Tree) -> FSQLUpdateSet:
        """Gets the setters that are specified in the query."""
        def as_setter(token: Tree):
            matching = list(token.find_data("property"))[0]
            return {
                "property": self._as_value(matching),
                "value": self._as_value(token.children[1])
            }
        return list(map(as_setter, list(setter.find_data("setter"))))

    def _as_fields(self, select: Tree) -> list[str]:
        """Gets the fields that are specified in the query."""
        if select.children[0].data.value == "fields":
            values = [self._as_value(tree) for tree in list(
                select.children[0].find_data("property"))]
            return values

        return "*"

    def _as_fsql_subject_type(self, subject_type: Tree):
        """Determines the subject type that the query is referring to."""
        match subject_type.children[0].type:
            case "WITHIN":
                return FSQLSubjectType.COLLECTION_GROUP
            case "FROM":
                return FSQLSubjectType.COLLECTION
            case "AT":
                return FSQLSubjectType.DOCUMENT

    def _do_select(self, subset: Tree, subject_type: Tree,
                  subject: Tree, where: Tree | None, limit: Tree | None,
                  output: Tree | None) -> FSQLSelectQuery:
        """
        The base method for all select queries.
        Creates the appropate definition of the select query.
        """
        return {
            "query_type": FSQLQueryType.SELECT,
            "fields": self._as_fields(subset),
            "subject": self._as_value(subject),
            "subject_type": self._as_fsql_subject_type(subject_type),
            "where": self._as_where(where),
            "limit": self._as_limit(limit),
            "output": self._as_output(output)
        }

    def select_collection(self, subset: Tree, subject_type: Tree,
                          subject: Tree, where: Tree | None, limit: Tree | None,
                          output: Tree | None):
        """The method for all select collection queries."""
        return self._do_select(subset, subject_type, subject, where, limit, output)

    def select_document(self, subset: Tree, subject_type: Tree,
                        subject: Tree, output: Tree | None):
        """The method for all select document queries."""
        return self._do_select(subset, subject_type, subject, where=None, limit=None, output=output)

    def _do_update(self, subject_type: Tree, subject: Tree, setter: Tree, where: Tree | None):
        """
        The base method for all update queries.
        Creates the appropate definition of the update query.
        """

        return {
            "query_type": FSQLQueryType.UPDATE,
            "subject": self._as_value(subject),
            "subject_type": self._as_fsql_subject_type(subject_type),
            "where": self._as_where(where),
            "set": self._as_setters(setter)
        }

    def update_collection(self, subject_type: Tree, subject: Tree, setter: Tree, where: Tree):
        """The method for all update collection queries."""
        return self._do_update(subject_type, subject, setter, where)

    def update_document(self, subject_type: Tree, subject: Tree, setter: Tree):
        """The method for all update document queries."""
        return self._do_update(subject_type, subject, setter, where=None)

    def _do_delete(self, subject_type: Tree, subject: Tree, where: Tree):
        """
        The base method for all delete queries.
        Creates the appropate definition of the delete query.
        """
        return {
            "query_type": FSQLQueryType.DELETE,
            "subject": self._as_value(subject),
            "subject_type": self._as_fsql_subject_type(subject_type),
            "where": self._as_where(where)
        }

    def delete_collection(self, subject_type: Tree, subject: Tree, where: Tree):
        """The method for all delete collection queries."""
        return self._do_delete(subject_type, subject, where)

    def delete_document(self, subject_type: Tree, subject: Tree):
        """The method for all delete document queries."""
        return self._do_delete(subject_type, subject, where=None)

    def show_collections(self):
        """The method for all show collections queries."""
        return {
            "query_type": FSQLQueryType.SHOW,
            "subject": None,
            "subject_type": FSQLSubjectType.COLLECTION,
            "where": None
        }

    def insert_document(self, subject: Tree, setter: Tree, identifier: Tree) -> FSQLInsertQuery:
        """The method for all insert document queries."""
        return {
            "query_type": FSQLQueryType.INSERT,
            "subject": self._as_value(subject),
            "subject_type": FSQLSubjectType.COLLECTION,
            "set": self._as_setters(setter),
            "identifier": self._as_identifier(identifier)
        }

def parse(query: str) -> FSQLQuery:
    """
    Uses Lark to parse the query against the grammar and then provides a tokenised query
    """
    try:

        parse_tree = build_parse_tree(query)

        ql_tree = FSQLTree().transform(parse_tree)
        fsql_query: FSQLQuery = ql_tree.children[0]
        return fsql_query
    except Exception as err:
        raise QuerySyntaxError(err) from err


def build_parse_tree(query: str):
    """
    Parses the supplied query against the grammar and returns the parse tree.

    Returns:
        The Lark Tree that represents the tokenized query.
    """
    grammar = read_grammar()

    parser = Lark(grammar, lexer="basic")
    return parser.parse(query)


def resource_path(relative_path):
    """
    Fetches the base path of the running application. If running from a built
    version then the _MEIPASS environment variable will be present.

    Returns:
        str: The base path of the running application.
    """
    try:
        base_path = sys._MEIPASS
    except (AttributeError, ModuleNotFoundError):
        base_path = os.environ.get("_MEIPASS2", os.path.abspath("."))

    return os.path.join(base_path, relative_path)


def read_grammar():
    """
    Reads the grammar file for the FSQL language.

    Returns:
        str: The contents of the grammar file.
    """
    with open(resource_path("fsql.lark"), encoding="utf-8") as file:
        return file.read()
