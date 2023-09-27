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

    if len(tokens) != 6 and len(tokens) != 2:
        raise ValueError("Invalid query")
    else:
        documents = execute_query(tokens)
        return list(filter(object_exists, map(snapshot_to_document, documents)))

def object_exists(dict) -> bool:
    return dict is not None

def snapshot_to_document(snapshot: firestore.DocumentSnapshot) -> dict:
    return snapshot.to_dict()

def has_where_tokens(tokens: list[str]) -> bool:
    return len(tokens) == 6

def as_field_filter(tokens: list[str]) -> FieldFilter:
    literal = json.loads(json.dumps(tokens[5]))
    operator = tokens[4]
    field = tokens[3]

    return FieldFilter(field, operator, ast.literal_eval(literal))

def add_where(query: firestore.Query, tokens: list[str]):
    if (has_where_tokens(tokens)):
        return query.where(filter=as_field_filter(tokens))
    else:
        return query

def execute_query(tokens: list[str]) -> list[firestore.DocumentSnapshot]:
    db = firestore.Client()

    match query_type(tokens):
        case QueryType.COLLECTION_GROUP:
            collection_group = tokens[1]
            query = add_where(db.collection_group(collection_group), tokens)
            return query.get()
        case QueryType.DOCUMENT:
            path = tokens[1]
            return [db.document(path).get()]
        case QueryType.COLLECTION:
            collection_path = tokens[1]
            query = add_where(db.collection(collection_path), tokens)
            return query.get()

def query_type(tokens: list[str]) -> QueryType:
    intention = tokens[0]
    if intention == "from":
        return QueryType.COLLECTION_GROUP
    elif intention == "at":
        return QueryType.COLLECTION if (tokens[1].count("/") % 2) == 0 else QueryType.DOCUMENT

def build_query(tokens: list[str]) -> str:
    return " ".join(tokens)

def tokenise(query: str) -> list[str]:
    tokens = query.split(" ")
    return tokens