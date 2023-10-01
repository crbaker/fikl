from lark import Transformer, v_args, Tree
from typing import List
import ast
from rich import print as rprint
from enum import Enum
from typing import TypedDict
from typing import Union

AllTypes = Union[int, float, str, bool]

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
    value: int | float | str | List[any]

class FSQLQuery(TypedDict):
    query_type: FSQLQueryType
    fields: list[str] | str
    subject: str
    subject_type: FSQLSubjectType
    where: FSQLWhere | None

@v_args(inline=True)    # Affects the signatures of the methods
class FSQLTree(Transformer):
    def __init__(self):
        self.vars = {}

    def data_value(self, some_tree: Tree, data: str):
        data_tree: List[Tree] = list(some_tree.find_data(data))
        return data_tree[0].children[0].value
    
    def as_fsql_match(self, where: Tree) -> AllTypes | List[AllTypes]:
        matching = list(where.find_data('matching'))[0].children[0]

        if matching.data == 'literal':
            return ast.literal_eval(self.data_value(matching, "literal"))
        elif matching.data == "array":
            values = list(map(lambda x: ast.literal_eval(x.children[0].value), list(matching.find_data("literal"))))
            return values

    def as_where(self, where: Tree | None) -> FSQLWhere | None:
        if (where is None):
            return None
        else:
            field = self.data_value(where, 'property')
            operator = self.data_value(where, 'operator')
            matching = self.as_fsql_match(where)

            return {
                'field': field,
                'operator': operator,
                'value': matching
            }
        
    def as_fields(self, select: Tree) -> list[str]:
        select_type = select.children[0].data.value
        if select_type == "fields":
            values = list(map(lambda x: x.children[0].value if x.children[0].type == "CNAME" else ast.literal_eval(x.children[0].value), list(select.children[0].find_data("property"))))
            return values
        elif select_type == "all":
            return "*"
        
    def show(self, select: Tree, subject_type: Tree, subject: Tree, where: Tree | None):

        def as_fsql_subject_type(subject_type: Tree):
            match subject_type.children[0].value:
                case "within":
                    return FSQLSubjectType.COLLECTION_GROUP
                case "from":
                    return FSQLSubjectType.COLLECTION
                case "at":
                    return FSQLSubjectType.DOCUMENT

        return {
            "query_type": FSQLQueryType.SHOW,
            "fields": self.as_fields(select) ,
            "subject": subject.children[0].value if subject.children[0].type == "CNAME" else ast.literal_eval(subject.children[0].value),
            "subject_type": as_fsql_subject_type(subject_type),
            "where": self.as_where(where)
        }

    def show_collection (self, select: Tree, subject_type: Tree, subject: Tree, where: Tree | None):
        return self.show(select, subject_type, subject, where)

    def show_document (self, select: Tree, subject_type: Tree, subject: Tree):
        return self.show(select, subject_type, subject, where=None)