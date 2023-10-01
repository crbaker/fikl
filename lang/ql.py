"""This module provides the fsql query details."""
# lang/ql.py

# XWMHTQUM YBKOGUGP
import os
import sys
from lark import Lark, Transformer, v_args, Tree

from rich import print as rprint

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from lang.transformer import FSQLQuery, FSQLSubjectType, FSQLTree


class QueryError(ValueError):
    pass


def run_query(query: str) -> list[dict]:

    grammar = read_grammar()

    parser = Lark(grammar, lexer="basic")
    parse_tree = parser.parse(query)

    ll = FSQLTree().transform(parse_tree)
    fsql_query: FSQLQuery = ll.children[0]

    documents = execute_query(fsql_query)
    return list(filter(object_exists, map(snapshot_to_document_fn(fsql_query), documents)))


def extract_fields(obj: dict, fields: list[str]):
    reduced = {}

    for field in fields:
        if "." not in field:
            if field not in obj:
                reduced[field] = None
            else:
                reduced[field] = obj[field]
        else:
            sub_fields = field.split(".")
            if sub_fields[0] not in obj:
                reduced[field] = None
            else:
                sub_obj = obj[sub_fields[0]]
                sub_reduced = extract_fields(
                    sub_obj, [".".join(sub_fields[1:])])
                reduced.update(sub_reduced)

    return reduced


def object_exists(dict) -> bool:
    return dict is not None


def snapshot_to_document_fn(fsql_query: FSQLQuery):
    requested_fields = fsql_query["fields"]

    def extract_fields_from_snapshot(snapshot: firestore.DocumentSnapshot):
        document_dict = snapshot.to_dict()
        document_dict["_path"] = snapshot.reference.path

        if (requested_fields == "*"):
            return document_dict
        else:
            return extract_fields(document_dict, requested_fields)

    return extract_fields_from_snapshot


def add_where(query: firestore.Query, fsql_query: FSQLQuery):
    if fsql_query["where"] is not None:
        field_filter = FieldFilter(fsql_query["where"]["field"], fsql_query["where"]["operator"], fsql_query["where"]["value"])
        return query.where(filter=field_filter)
    else:
        return query


def execute_query(fsql_query: FSQLQuery) -> list[firestore.DocumentSnapshot]:
    db = firestore.Client()

    match fsql_query["subject_type"]:
        case FSQLSubjectType.COLLECTION_GROUP:
            query = add_where(db.collection_group(
                fsql_query["subject"]), fsql_query)
            return query.get()
        case FSQLSubjectType.COLLECTION:
            query = add_where(db.collection(fsql_query["subject"]), fsql_query)
            return query.get()
        case FSQLSubjectType.DOCUMENT:
            return [db.document(fsql_query["subject"]).get()]


def resource_path(relative_path):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS        
    except Exception:
        base_path = os.environ.get("_MEIPASS2",os.path.abspath("."))

    os.listdir(base_path)
    return os.path.join(base_path, relative_path)

def read_grammar():
    return open(resource_path("fsql.lark")).read()
