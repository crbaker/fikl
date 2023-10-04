from lark import Transformer, v_args, Tree
import ast
from rich import print as rprint
from enum import Enum
from typing import TypedDict
from typing import Union

AllTypes = Union[int, float, str, bool, None]


class FSQLQueryType(Enum):
    SHOW = 1
    UPDATE = 2
    DELETE = 3


class FSQLSubjectType(Enum):
    COLLECTION_GROUP = 1
    DOCUMENT = 2
    COLLECTION = 3


class FSQLWhere(TypedDict):
    field: str
    operator: str
    value: int | float | str | list[any]


class FSQLQuery(TypedDict):
    query_type: FSQLQueryType
    subject: str
    subject_type: FSQLSubjectType
    where: list[FSQLWhere] | None


class FSQLUpdateSet(TypedDict):
    property: str
    value: AllTypes


class FSQLUpdateQuery(FSQLQuery):
    set: list[FSQLUpdateSet]


class FSQLShowQuery(FSQLQuery):
    fields: list[str] | str


@v_args(inline=True)    # Affects the signatures of the methods
class FSQLTree(Transformer):
    def __init__(self):
        self.vars = {}

    def data_value(self, some_tree: Tree, data: str):
        data_tree: list[Tree] = list(some_tree.find_data(data))
        return self.as_value(data_tree[0])

    def as_value(self, some_tree: Tree) -> AllTypes:
        match some_tree.children[0].type:
            case "CNAME":
                return some_tree.children[0].value
            case "NULL":
                return None
            case _:
                return ast.literal_eval(some_tree.children[0].value)

    def as_fsql_match(self, where: Tree) -> AllTypes | list[AllTypes]:
        matching = list(where.find_data('matching'))[0].children[0]

        if matching.data == 'literal':
            return ast.literal_eval(self.data_value(matching, "literal"))
        elif matching.data == "array":
            values = list(map(lambda x: ast.literal_eval(
                x.children[0].value), list(matching.find_data("literal"))))
            return values

    def as_where(self, where: Tree | None) -> list[FSQLWhere] | None:
        if (where is None):
            return None
        else:

            def token_as_where(token) -> FSQLWhere:
                return {
                    'field': self.data_value(token, 'property'),
                    'operator': self.data_value(token, 'operator'),
                    'value': self.as_fsql_match(token)
                }

            return list(map(token_as_where, list(where.find_data("comparrison"))))
        
    def as_setters(self, set: Tree) -> FSQLUpdateSet:
        return list(map(lambda x: {
            "property": self.data_value(x, "property"),
            "value": self.as_value(x.children[1])
        }, list(set.find_data("setter"))))

    def as_fields(self, select: Tree) -> list[str]:
        select_type = select.children[0].data.value
        if select_type == "fields":
            values = list(map(lambda x: self.as_value(x), list(
                select.children[0].find_data("property"))))
            return values
        elif select_type == "all":
            return "*"

    def as_fsql_subject_type(self, subject_type: Tree):
        match subject_type.children[0].type:
            case "WITHIN":
                return FSQLSubjectType.COLLECTION_GROUP
            case "FROM":
                return FSQLSubjectType.COLLECTION
            case "AT":
                return FSQLSubjectType.DOCUMENT

    def show(self, select: Tree, subject_type: Tree, subject: Tree, where: Tree | None) -> FSQLShowQuery:

        return {
            "query_type": FSQLQueryType.SHOW,
            "fields": self.as_fields(select),
            "subject": self.as_value(subject),
            "subject_type": self.as_fsql_subject_type(subject_type),
            "where": self.as_where(where)
        }

    def show_collection(self, select: Tree, subject_type: Tree, subject: Tree, where: Tree | None):
        return self.show(select, subject_type, subject, where)

    def show_document(self, select: Tree, subject_type: Tree, subject: Tree):
        return self.show(select, subject_type, subject, where=None)

    def update(self, subject_type: Tree, subject: Tree, set: Tree, where: Tree | None):
        setters = self.as_setters(set)

        return {
            "query_type": FSQLQueryType.UPDATE,
            "subject": self.as_value(subject),
            "subject_type": self.as_fsql_subject_type(subject_type),
            "where": self.as_where(where),
            "set": setters
        }

    def update_collection(self, subject_type: Tree, subject: Tree, set: Tree, where: Tree):
        return self.update(subject_type, subject, set, where)

    def update_document(self, subject_type: Tree, subject: Tree, set: Tree):
        return self.update(subject_type, subject, set, where=None)

    def delete(self, subject_type: Tree, subject: Tree, where: Tree):
        return {
            "query_type": FSQLQueryType.DELETE,
            "subject": self.as_value(subject),
            "subject_type": self.as_fsql_subject_type(subject_type),
            "where": self.as_where(where)
        }

    def delete_collection(self, subject_type: Tree, subject: Tree, where: Tree):
        return self.delete(subject_type, subject, where)

    def delete_document(self, subject_type: Tree, subject: Tree):
        return self.delete(subject_type, subject, where=None)
