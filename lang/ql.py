"""This module provides the fsql query details."""
# lang/ql.py

# XWMHTQUM YBKOGUGP
import json
import ast

from typing import TypedDict
from enum import Enum

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter


class FSQLQueryType(Enum):
    SHOW = 1
    UPDATE = 2
    DELETE = 3


class SubjectType(Enum):
    COLLECTION_GROUP = 1
    DOCUMENT = 2
    COLLECTION = 3


class FSQLQuery(TypedDict):
    query_type: FSQLQueryType
    fields: list[str] | str
    subject: str
    subject_type: SubjectType
    where: FieldFilter | None


def run_query(query: str) -> list[dict]:
    sanitised = query.strip()
    query = tokenise(sanitised)

    documents = execute_query(query)
    return list(filter(object_exists, map(snapshot_to_document_fn(query), documents)))


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


def as_field_filter(where_tokens: list[str]) -> FieldFilter:
    field = where_tokens[0]
    operator = where_tokens[1]
    literal = json.loads(json.dumps(where_tokens[2]))

    return FieldFilter(field, operator, ast.literal_eval(literal))


def add_where(query: firestore.Query, fsql_query: FSQLQuery):
    if fsql_query["where"] is not None:
        return query.where(filter=fsql_query["where"])
    else:
        return query


def execute_query(fsql_query: FSQLQuery) -> list[firestore.DocumentSnapshot]:
    db = firestore.Client()

    match fsql_query["subject_type"]:
        case SubjectType.COLLECTION_GROUP:
            query = add_where(db.collection_group(
                fsql_query["subject"]), fsql_query)
            return query.get()
        case SubjectType.DOCUMENT:
            return [db.document(fsql_query["subject"]).get()]
        case SubjectType.COLLECTION:
            query = add_where(db.collection(fsql_query["subject"]), fsql_query)
            return query.get()


def subject_type(intention: str) -> SubjectType:
    if intention == "within":
        return SubjectType.COLLECTION_GROUP
    elif intention == "from":
        return SubjectType.COLLECTION
    else:
        return SubjectType.DOCUMENT

def query_type(instruction: str) -> FSQLQueryType:
    if instruction ==  "show":
        return FSQLQueryType.SHOW
    elif instruction == "update":
        return FSQLQueryType.UPDATE
    elif instruction == "delete":
        return FSQLQueryType.DELETE
    else:
        raise ValueError("Invalid query type")

def build_query(tokens: list[str]) -> str:
    return " ".join(tokens)


def tokenise(query: str) -> FSQLQuery:
    tokens = query.split(" ")
    if len(tokens) not in [8, 4]:
        raise ValueError("Invalid query")
    else:
        fields = tokens[1]
        return {
            "instruction": query_type(tokens[0]),
            "fields": "*" if fields == "*" else fields.split(","),
            "subject_type": subject_type(tokens[2]),
            "subject": tokens[3],
            "where": None if len(tokens) == 4 else as_field_filter(tokens[5:])
        }
