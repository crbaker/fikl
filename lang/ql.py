"""This module provides the fsql query details."""
# lang/ql.py

# XWMHTQUM YBKOGUGP
import json
import ast

from enum import Enum
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

class QueryType(Enum):
    COLLECTION_GROUP = 1
    DOCUMENT = 2
    COLLECTION = 3

def run_query(query: str) -> list[dict]:
    sanitised = query.strip()
    tokens = tokenise(sanitised)

    valid_query_lengths = [8, 4]

    if len(tokens) not in valid_query_lengths:
        raise ValueError("Invalid query")
    else:
        documents = execute_query(tokens)
        return list(filter(object_exists, map(snapshot_to_document_fn(tokens), documents)))

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
                sub_reduced = extract_fields(sub_obj, [".".join(sub_fields[1:])])
                reduced.update(sub_reduced)

    return reduced

def object_exists(dict) -> bool:
    return dict is not None

def snapshot_to_document_fn(tokens: list[str]):
    requested_fields = tokens[1]

    def extract_fields_from_snapshot(snapshot: firestore.DocumentSnapshot):
        document_dict = snapshot.to_dict()
        document_dict["_path"] = snapshot.reference.path

        if (requested_fields == "*"):
            return document_dict
        else:
            return extract_fields(document_dict, requested_fields.split(","))
    
    return extract_fields_from_snapshot

def has_where_tokens(tokens: list[str]) -> bool:
    return len(tokens) == 8

def as_field_filter(tokens: list[str]) -> FieldFilter:
    operator = tokens[6]
    field = tokens[5]
    literal = json.loads(json.dumps(tokens[7]))

    return FieldFilter(field, operator, ast.literal_eval(literal))

def add_where(query: firestore.Query, tokens: list[str]):
    if (has_where_tokens(tokens)):
        return query.where(filter=as_field_filter(tokens))
    else:
        return query

def execute_query(tokens: list[str]) -> list[firestore.DocumentSnapshot]:
    db = firestore.Client()

    subject = tokens[3]

    match query_type(tokens):
        case QueryType.COLLECTION_GROUP:
            query = add_where(db.collection_group(subject), tokens)
            return query.get()
        case QueryType.DOCUMENT:
            return [db.document(subject).get()]
        case QueryType.COLLECTION:
            query = add_where(db.collection(subject), tokens)
            return query.get()

def query_type(tokens: list[str]) -> QueryType:
    intention = tokens[2]
    subject = tokens[3]

    if intention == "from":
        return QueryType.COLLECTION_GROUP
    elif intention == "at":
        return QueryType.COLLECTION if (subject.count("/") % 2) == 0 else QueryType.DOCUMENT

def build_query(tokens: list[str]) -> str:
    return " ".join(tokens)

def tokenise(query: str) -> list[str]:
    tokens = query.split(" ")
    return tokens