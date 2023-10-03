"""This module provides the fsql query details."""
# lang/ql.py

import os
import sys
from lark import Lark

from rich import print as rprint

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from lang.transformer import FSQLQuery, FSQLQueryType, FSQLShowQuery, FSQLSubjectType, FSQLTree, FSQLUpdateQuery


class QueryError(ValueError):
    pass


def run_query(query: str) -> list[dict] | dict:

    grammar = read_grammar()

    parser = Lark(grammar, lexer="basic")
    parse_tree = parser.parse(query)

    ql_tree = FSQLTree().transform(parse_tree)
    fsql_query: FSQLQuery = ql_tree.children[0]

    response = execute_query(fsql_query)

    if isinstance(response, int):
        return {"count": response}
    else:
        return list(filter(object_exists, map(snapshot_to_document_fn(fsql_query), response)))


def merge_dicts(dicts: list[dict]) -> dict:
    result = {}
    for d in dicts:
        result.update({d["property"]: d["value"]})
    return result


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
    requested_fields = fsql_query["fields"] if "fields" in fsql_query else "*"

    def extract_fields_from_snapshot(snapshot: firestore.DocumentSnapshot):
        document_dict = snapshot.to_dict()
        document_dict["_path"] = snapshot.reference.path

        if (requested_fields == "*"):
            return document_dict
        else:
            return extract_fields(document_dict, requested_fields)

    return extract_fields_from_snapshot


def add_where_clauses(query: firestore.Query, fsql_query: FSQLQuery):
    if fsql_query["where"] is not None:
        for where in fsql_query["where"]:
            field_filter = FieldFilter(
                where["field"], where["operator"], where["value"])
            query = query.where(filter=field_filter)
        return query
    else:
        return query


def update_document_ref(ref: firestore.DocumentReference, new_values: dict):
    ref.update(new_values)


def delete_document_ref(ref: firestore.DocumentReference):
    ref.delete()


def execute_query(fsql_query: FSQLQuery) -> list[firestore.DocumentSnapshot] | int:

    def fn_for_query(fsql_query: FSQLQuery):
        match fsql_query["query_type"]:
            case FSQLQueryType.SHOW:
                return execute_show_query
            case FSQLQueryType.UPDATE:
                return execute_update_query
            case FSQLQueryType.DELETE:
                return execute_delete_query
            case _:
                return lambda x: []

    query_fn = fn_for_query(fsql_query)

    return query_fn(fsql_query)


def execute_delete_query(fsql_query: FSQLUpdateQuery) -> int:
    docs = execute_show_query(fsql_query)

    count = 0

    for doc in docs:
        try:
            delete_document_ref(doc.reference)
            count += 1
        except Exception:
            pass

    return count


def execute_update_query(fsql_query: FSQLUpdateQuery) -> int:
    docs = execute_show_query(fsql_query)

    count = 0

    for doc in docs:
        new_values = merge_dicts(fsql_query["set"])
        try:
            update_document_ref(doc.reference, new_values)
            count += 1
        except Exception:
            pass

    return count


def execute_show_query(fsql_query: FSQLShowQuery) -> list[firestore.DocumentSnapshot]:
    db = firestore.Client()

    match fsql_query["subject_type"]:
        case FSQLSubjectType.COLLECTION_GROUP:
            query = add_where_clauses(db.collection_group(
                fsql_query["subject"]), fsql_query)
            return query.get()
        case FSQLSubjectType.COLLECTION:
            query = add_where_clauses(db.collection(fsql_query["subject"]), fsql_query)
            return query.get()
        case FSQLSubjectType.DOCUMENT:
            return [db.document(fsql_query["subject"]).get()]


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.environ.get("_MEIPASS2", os.path.abspath("."))

    return os.path.join(base_path, relative_path)


def read_grammar():
    return open(resource_path("fsql.lark")).read()
