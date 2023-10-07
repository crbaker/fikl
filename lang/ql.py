"""This module provides the fikl query details."""
# pylint: disable=too-many-return-statements
# lang/ql.py
import json
from operator import itemgetter as i
from functools import cmp_to_key
import os

from collections import defaultdict
from collections.abc import MutableMapping

import pydash

from firebase_admin import firestore as fs

from google.cloud.firestore_v1.base_query import FieldFilter

from lang.transformer import (FIKLQuery,
                              FIKLQueryType,
                              FIKLWhere,
                              FIKLOrderBy,
                              FIKLSelectQuery,
                              FIKLInsertQuery,
                              FIKLSubjectType,
                              FIKLUpdateQuery, parse)


class QueryError(ValueError):
    """
    Exception raised for errors in the input query.

    Attributes:
        message -- explanation of the error
    """


def should_output(fikl_query: FIKLQuery) -> bool:
    "Indicates if the output of the query should be saved to a file"
    return "output" in fikl_query and object_exists(fikl_query["output"])


def run_query(query: str) -> list[dict] | dict:
    """
    Parses the supplied query against the grammar and and executes the query.

    Returns:
        list: The list of records returned in the case of a select query.
        int: The number of records affected.
    """
    try:
        fikl_query: FIKLQuery = parse(query)
        response = execute_query(fikl_query)

        if isinstance(response, int):
            return {"count": response}

        documents = [snapshot_to_document_fn(fikl_query)(
            doc) for doc in response if object_exists(doc)]

        if should_output(fikl_query):
            saved_to_path = output_json_to_file(json.dumps(
                documents, indent=2), fikl_query["output"])
            return {"count": len(documents), "file": saved_to_path}

        return documents
    except QueryError:
        raise
    except Exception as exception:
        raise QueryError(exception) from exception


def output_json_to_file(json_output: str, path: str):
    """ Writes the provided json to the provided path."""
    full_path = os.path.expanduser(path)
    with open(full_path, "w", encoding="utf-8") as file:
        file.write(json_output)

    return full_path


def merge_setters(dicts: list[dict]) -> dict:
    """
    Merges a list of setter values into a single dict.

    Returns:
        dict: The dict with the setters.
    """
    result = {}
    for setter in dicts:
        result.update({setter["property"]: setter["value"]})
    return result


def flatten(dictionary, parent_key="", separator="."):
    """Flattens a nested dictionary"""
    items = []
    for key, value in dictionary.items():
        new_key = parent_key + separator + key if parent_key else key
        if isinstance(value, MutableMapping):
            items.extend(flatten(value, new_key, separator=separator).items())
        else:
            items.append((new_key, value))
    return dict(items)


def expand_key(dictionary: dict, key: str, value) -> dict:
    """
    Expands keys in a dictionary to allow for nested dictionaries.

    Returns:
        dict: The dict with the key expanded.
    """
    if "." in key:
        key, rest = key.split(".", 1)
        if key not in dictionary:
            dictionary[key] = {}
            expand_key(dictionary[key], rest, value)
    else:
        dictionary[key] = value
    return dictionary


def merge_dicts(dicts) -> dict:
    """
    Merges a collection of nested dicts into a single dict.

    Returns:
        dict: The dict with all the nested dicts merged.
    """
    result = defaultdict(dict)
    for sub_dict in dicts:
        for key, value in sub_dict.items():
            if isinstance(value, dict):
                result[key] = merge_dicts([result[key], value])
            else:
                result[key] = value
    return dict(result)


def extract_fields(obj: dict, fields: list[str]) -> dict:
    """
    Returns only fields from the provided object that are in the provided list of fields.

    Returns:
        dict: The dict with only the requested fields.
    """
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


def object_exists(obj: dict) -> bool:
    """
    Checks if the provided object is not None.

    Returns:
        bool: True if the object is not None, False otherwise.
    """
    return obj is not None


def snapshot_to_document_fn(fikl_query: FIKLQuery):
    """
    Creates a function that can be used to convert a DocumentSnapshot to a dictionary.
    This function will also reduce the returned fields to only those requested in the query.

    Returns:
        The function that can be called to convert a DocumentSnapshot to a dictionary.
    """
    requested_fields = fikl_query["fields"] if "fields" in fikl_query else "*"

    def extract_fields_from_snapshot(response: fs.firestore.DocumentSnapshot | str):
        if isinstance(response, str):
            return response

        document_dict = response.to_dict()
        document_dict["_path"] = response.reference.path

        if requested_fields == "*":
            return document_dict

        return extract_fields(document_dict, requested_fields)

    return extract_fields_from_snapshot


def add_order_by_clauses(query: fs.firestore.Query,
                         fikl_query: FIKLQuery) -> fs.firestore.Query:
    """
    Adds the order by clauses to the query.

    Returns:
        firestore.Query: The query with the order by clauses added.
    """
    if "order" in fikl_query and fikl_query["order"] is not None:
        remote_orders = [where for where in fikl_query["order"]
                         if where["local"] is False]
        for order in remote_orders:
            direction = "ASCENDING" if order["direction"] == "asc" else "DESCENDING"
            query = query.order_by(
                order["property"], direction=direction)
        return query

    return query


def add_where_clauses(query: fs.firestore.Query,
                      fikl_query: FIKLQuery) -> fs.firestore.Query:
    """
    Adds the where clauses to the query.

    Returns:
        firestore.Query: The query with the where clauses added.
    """
    if fikl_query["where"] is not None:
        remote_wheres = [where for where in fikl_query["where"]
                         if where["local"] is False]
        for where in remote_wheres:
            corrected_operator = "not-in" if where["operator"] == "not_in" else where["operator"]
            field_filter = FieldFilter(
                where["property"], corrected_operator, where["value"])
            query = query.where(filter=field_filter)
        return query

    return query


def execute_query(fikl_query: FIKLQuery) -> list[fs.firestore.DocumentSnapshot] | int:
    """
    Determines the appropraite query function to execute based on the query type.

    Returns:
        int: The number of records affected.
        list: The list of records recturned in the case of a select query
    """

    def fn_for_query(fikl_query: FIKLQuery):
        match fikl_query["query_type"]:
            case FIKLQueryType.SELECT:
                return execute_select_query
            case FIKLQueryType.UPDATE:
                return execute_update_query
            case FIKLQueryType.DELETE:
                return execute_delete_query
            case FIKLQueryType.SHOW:
                return execute_show_query
            case FIKLQueryType.INSERT:
                return execute_insert_query
            case _:
                return lambda x: []

    query_fn = fn_for_query(fikl_query)

    return query_fn(fikl_query)


def execute_delete_query(fikl_query: FIKLUpdateQuery) -> int:
    """
    Executes a delete query against the Firestore database.

    Returns:
        int: The number of records deleted.
    """
    docs = execute_select_query(fikl_query)

    count = 0

    for doc in docs:
        try:
            doc.reference.delete()
            count += 1
        except Exception:
            pass

    return count


def execute_update_query(fikl_query: FIKLUpdateQuery) -> int:
    """
    Executes an update query against the Firestore database.

    Returns:
        int: The number of records updated.
    """
    docs = execute_select_query(fikl_query)

    count = 0
    new_values = merge_setters(fikl_query["set"])

    for doc in docs:
        try:
            doc.reference.update(new_values)
            count += 1
        except Exception:
            pass

    return count


def execute_insert_query(fikl_query: FIKLInsertQuery) -> int:
    """
    Inserts a document into the Firestore database.

    Returns:
        int: The number of documents inserted.
    """
    new_values = merge_setters(fikl_query["set"])

    dicts = [expand_key({}, key, value)
             for key, value in new_values.items()]
    merged_dict = merge_dicts(dicts)

    client = fs.client()

    client.collection(fikl_query["subject"]).add(
        merged_dict, document_id=fikl_query["identifier"])
    return 1


def execute_show_query(_: FIKLSelectQuery) -> list[str]:
    """
    Fetches the list of root level collections from the Firestore database.

    Returns:
        list[str]: A list of collections names.
    """
    client = fs.client()

    collections = []
    for coll in client.collections():
        collections.append(coll.id)

    return collections


def local_compare(document: dict, prop: str, where: FIKLWhere) -> bool:
    """
    Compares the provided value with the provided filter.
    """
    if prop not in document:
        return False

    value = document[prop]
    match where['operator']:
        case ">":
            return value > where['value']
        case ">=":
            return value >= where['value']
        case "<":
            return value < where['value']
        case "<=":
            return value <= where['value']
        case "!=":
            return value != where['value']
        case "==":
            return value == where['value']
        case "in":
            return value in where['value']
        case "not_in":
            return value not in where['value']
        case "array_contains":
            return where['value'] in value
        case "array_contains_any":
            return pydash.every(where['value'], lambda v: v in value)

    return False


def includes(document: dict, local_filters: list[FIKLWhere]) -> bool:
    """
    Determines if the provided document should be included in the results.
    """
    flat_dict = flatten(document)
    return pydash.every(local_filters,
                        lambda where: local_compare(flat_dict, where["property"], where))


def filter_locally(records: list[fs.firestore.DocumentSnapshot],
                   fikl_query: FIKLSelectQuery):
    """Filters the list of records locally."""
    if fikl_query["where"] is not None:
        local_wheres = [
            where for where in fikl_query["where"] if where["local"] is True]
        return [doc for doc in records if includes(doc.to_dict(), local_wheres)]

    return records


def cmp(left, right):
    """Polyfill for cmp function."""
    return (left > right) - (left < right)


def multikeysort(items, columns):
    """Sorts the provided list of items by the provided list of columns."""
    comparers = [
        ((i(col[1:].strip()), -1) if col.startswith('-')
         else (i(col.strip()), 1))
        for col in columns
    ]

    def comparer(left: fs.firestore.DocumentSnapshot,
                 right: fs.firestore.DocumentSnapshot):
        left_dict = left.to_dict()
        right_dict = right.to_dict()
        comparer_iter = (
            cmp(fn(left_dict), fn(right_dict)) * mult
            for fn, mult in comparers
        )
        return next((result for result in comparer_iter if result), 0)
    return sorted(items, key=cmp_to_key(comparer))


def order_by_as_sort_column(order_by: FIKLOrderBy) -> str:
    """Creates a new sort column from the provided order by clause."""
    return order_by["property"] if order_by["direction"] == "asc" else f"-{order_by['property']}"


def sort_locally(records: list[fs.firestore.DocumentSnapshot], fikl_query: FIKLSelectQuery):
    """Sorts the list of records locally."""
    if "order" in fikl_query and fikl_query["order"] is not None:
        sorters = [order_by_as_sort_column(order_by)
                   for order_by in fikl_query["order"]]
        return multikeysort(records, sorters)
    return records


def execute_select_query(fikl_query: FIKLSelectQuery) -> list[fs.firestore.DocumentSnapshot]:
    """
    Executes a select query against the Firestore database.

    Returns:
        list: A list of documents that match the query.
    """

    client = fs.client()

    def execute_collection_query(query: fs.firestore.Query) -> list[fs.firestore.DocumentSnapshot]:
        query = add_where_clauses(query, fikl_query)
        query = add_order_by_clauses(query, fikl_query)

        if "limit" in fikl_query and fikl_query["limit"] is not None:
            query = query.limit(fikl_query["limit"])

        return sort_locally(filter_locally(query.get(), fikl_query), fikl_query)

    match fikl_query["subject_type"]:
        case FIKLSubjectType.COLLECTION_GROUP:
            return execute_collection_query(client.collection_group(fikl_query["subject"]))
        case FIKLSubjectType.COLLECTION:
            return execute_collection_query(client.collection(fikl_query["subject"]))
        case FIKLSubjectType.DOCUMENT:
            return [client.document(fikl_query["subject"]).get()]
