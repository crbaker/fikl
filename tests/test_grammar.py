"""Tests the Transformer class and language grammar"""
# pylint: disable=missing-function-docstring,missing-class-docstring, no-method-argument, invalid-name
import unittest

from lang.transformer import (parse, read_grammar, build_parse_tree,
                              FSQLQueryType, FSQLSubjectType, QuerySyntaxError)


class TestTransformer(unittest.TestCase):

    def test_read_grammer(self):
        grammar = read_grammar()
        self.assertIsNotNone(grammar)

    def test_should_build_parse_tree(self):
        tree = build_parse_tree('select * from SOME_COLLECTION')
        self.assertIsNotNone(tree)

    def test_should_parse_valid_select_query(self):
        query = parse('select * from SOME_COLLECTION')
        self.assertEqual(query["query_type"], FSQLQueryType.SELECT)
        self.assertEqual(query["fields"], "*")
        self.assertEqual(query["subject_type"], FSQLSubjectType.COLLECTION)
        self.assertEqual(query["subject"], "SOME_COLLECTION")
        self.assertIsNone(query["where"])
        self.assertIsNone(query["limit"])

    def test_should_parse_valid_select_with_fields_query(self):
        query = parse('select first_field, "some.nested.field" from SOME_COLLECTION')
        self.assertEqual(query["query_type"], FSQLQueryType.SELECT)
        self.assertEqual(query["fields"], ["first_field", "some.nested.field"])
        self.assertEqual(query["subject_type"], FSQLSubjectType.COLLECTION)
        self.assertEqual(query["subject"], "SOME_COLLECTION")
        self.assertIsNone(query["where"])
        self.assertIsNone(query["limit"])

    def test_should_parse_valid_select_with_limit_query(self):
        query = parse('select * from SOME_COLLECTION limit 10')
        self.assertEqual(query["query_type"], FSQLQueryType.SELECT)
        self.assertEqual(query["fields"], "*")
        self.assertEqual(query["subject_type"], FSQLSubjectType.COLLECTION)
        self.assertEqual(query["subject"], "SOME_COLLECTION")
        self.assertIsNone(query["where"])
        self.assertEqual(query["limit"], 10)

    def test_should_not_parse_invalid_select(self):
        with self.assertRaises(QuerySyntaxError):
            parse('select from SOME_COLLECTION')

if __name__ == '__main__':
    unittest.main()
