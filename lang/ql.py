"""This module provides the fsql query details."""
# lang/ql.py
import json
import os

from collections import defaultdict


from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from lang.transformer import (FSQLQuery,
                              FSQLQueryType,
                              FSQLSelectQuery,
                              FSQLSubjectType,
                              FSQLUpdateQuery, parse)


class QueryError(ValueError):
    """
    Exception raised for errors in the input query.

    Attributes:
        message -- explanation of the error
    """


def should_output(fsql_query: FSQLQuery) -> bool:
    return "output" in fsql_query and object_exists(fsql_query["output"])


def run_query(query: str) -> list[dict] | dict:
    """
    Parses the supplied query against the grammar and and executes the query.

    Returns:
        list: The list of records returned in the case of a select query.
        int: The number of records affected.
    """
    try:
        fsql_query: FSQLQuery = parse(query)
        response = execute_query(fsql_query)

        if isinstance(response, int):
            return {"count": response}

        documents = [snapshot_to_document_fn(fsql_query)(
            doc) for doc in response if object_exists(doc)]

        if should_output(fsql_query):
            saved_to_path = output_json_to_file(json.dumps(
                documents, indent=2), fsql_query["output"])
            return {"count": len(documents), "file": saved_to_path}
        else:
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


def snapshot_to_document_fn(fsql_query: FSQLQuery):
    """
    Creates a function that can be used to convert a firestore.DocumentSnapshot to a dictionary.
    This function will also reduce the returned fields to only those requested in the query.

    Returns:
        The function that can be called to convert a firestore.DocumentSnapshot to a dictionary.
    """
    requested_fields = fsql_query["fields"] if "fields" in fsql_query else "*"

    def extract_fields_from_snapshot(response: firestore.DocumentSnapshot | str):
        if isinstance(response, str):
            return response

        document_dict = response.to_dict()
        document_dict["_path"] = response.reference.path

        if requested_fields == "*":
            return document_dict

        return extract_fields(document_dict, requested_fields)

    return extract_fields_from_snapshot


def add_where_clauses(query: firestore.Query, fsql_query: FSQLQuery) -> firestore.Query:
    """
    Adds the where clauses to the query.

    Returns:
        firestore.Query: The query with the where clauses added.
    """
    if fsql_query["where"] is not None:
        for where in fsql_query["where"]:
            field_filter = FieldFilter(
                where["field"], where["operator"], where["value"])
            query = query.where(filter=field_filter)
        return query

    return query


def execute_query(fsql_query: FSQLQuery) -> list[firestore.DocumentSnapshot] | int:
    """
    Determines the appropraite query function to execute based on the query type.

    Returns:
        int: The number of records affected.
        list: The list of records recturned in the case of a select query
    """

    def fn_for_query(fsql_query: FSQLQuery):
        match fsql_query["query_type"]:
            case FSQLQueryType.SELECT:
                return execute_select_query
            case FSQLQueryType.UPDATE:
                return execute_update_query
            case FSQLQueryType.DELETE:
                return execute_delete_query
            case FSQLQueryType.SHOW:
                return execute_show_query
            case _:
                return lambda x: []

    query_fn = fn_for_query(fsql_query)

    return query_fn(fsql_query)


def execute_delete_query(fsql_query: FSQLUpdateQuery) -> int:
    """
    Executes a delete query against the Firestore database.

    Returns:
        int: The number of records deleted.
    """
    docs = execute_select_query(fsql_query)

    count = 0

    for doc in docs:
        try:
            doc.reference.delete()
            count += 1
        except Exception:
            pass

    return count


def execute_update_query(fsql_query: FSQLUpdateQuery) -> int:
    """
    Executes an update query against the Firestore database.

    Returns:
        int: The number of records updated.
    """
    docs = execute_select_query(fsql_query)

    count = 0
    new_values = merge_setters(fsql_query["set"])
    for doc in docs:

        dicts = [expand_key({}, key, value)
                 for key, value in new_values.items()]
        merged_dict = merge_dicts(dicts)

        try:
            doc.reference.update(merged_dict)
            count += 1
        except Exception:
            pass

    return count


def execute_show_query(_: FSQLSelectQuery) -> list[str]:
    """
    Fetches the list of root level collections from the Firestore database.

    Returns:
        list[str]: A list of collections names.
    """
    client = firestore.Client()

    collections = []
    for coll in client.collections():
        collections.append(coll.id)

    return collections


def execute_select_query(fsql_query: FSQLSelectQuery) -> list[firestore.DocumentSnapshot]:
    """
    Executes a select query against the Firestore database.

    Returns:
        list: A list of documents that match the query.
    """
    client = firestore.Client()

    def execute_collection_query(query: firestore.Query) -> list[firestore.DocumentSnapshot]:
        query = add_where_clauses(query, fsql_query)
        if "limit" in fsql_query and fsql_query["limit"] is not None:
            query = query.limit(fsql_query["limit"])

        return query.get()

    match fsql_query["subject_type"]:
        case FSQLSubjectType.COLLECTION_GROUP:
            return execute_collection_query(client.collection_group(fsql_query["subject"]))
        case FSQLSubjectType.COLLECTION:
            return execute_collection_query(client.collection(fsql_query["subject"]))
        case FSQLSubjectType.DOCUMENT:
            return [client.document(fsql_query["subject"]).get()]
