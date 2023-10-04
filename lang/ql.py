"""This module provides the fsql query details."""
# lang/ql.py

import os
import sys
from collections import defaultdict
from lark import Lark

from rich import print as rprint

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from lang.transformer import FSQLQuery, FSQLQueryType, FSQLSelectQuery, FSQLSubjectType, FSQLTree, FSQLUpdateQuery


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


def merge_setters(dicts: list[dict]) -> dict:
    result = {}
    for d in dicts:
        result.update({d["property"]: d["value"]})
    return result


def expand_key(dictionary: dict, key: str, value) -> dict:
    if "." in key:
        key, rest = key.split(".", 1)
        if key not in dictionary:
            dictionary[key] = {}
            expand_key(dictionary[key], rest, value)
    else:
        dictionary[key] = value
    return dictionary


def merge_dicts(dicts):
    result = defaultdict(dict)
    for d in dicts:
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = merge_dicts([result[key], value])
            else:
                result[key] = value
    return dict(result)


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
            case FSQLQueryType.SELECT:
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
        new_values = merge_setters(fsql_query["set"])

        dicts = list(map(lambda x: expand_key(
            {}, x, new_values[x]), new_values))
        merged_dict = merge_dicts(dicts)

        try:
            update_document_ref(doc.reference, merged_dict)
            count += 1
        except Exception:
            pass

    return count


def execute_show_query(fsql_query: FSQLSelectQuery) -> list[firestore.DocumentSnapshot]:
    db = firestore.Client()

    def execute_collection_query(query: firestore.Query) -> list[firestore.DocumentSnapshot]:
        query = add_where_clauses(query, fsql_query)
        if fsql_query["limit"] is not None:
            query = query.limit(fsql_query["limit"])

        return query.get()

    match fsql_query["subject_type"]:
        case FSQLSubjectType.COLLECTION_GROUP:
            return execute_collection_query(db.collection_group(fsql_query["subject"]))
        case FSQLSubjectType.COLLECTION:
            return execute_collection_query(db.collection(fsql_query["subject"]))
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
