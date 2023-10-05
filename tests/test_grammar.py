"""Tests the Transformer class and language grammar"""
# pylint: disable=missing-function-docstring,missing-class-docstring
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
        query = parse(
            'select first_field, "some.nested.field" from SOME_COLLECTION')
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

    def test_should_parse_valid_select_with_limit_and_where_query(self):
        query = parse("""
            select * from SOME_COLLECTION
                      where some_field == "ABDEFG" and some_other_field == 2000 limit 10
        """)

        self.assertIsNotNone(query["where"])
        self.assertEqual(len(query["where"]), 2)

        self.assertEqual(query["where"][0]["field"], "some_field")
        self.assertEqual(query["where"][0]["operator"], "==")
        self.assertEqual(query["where"][0]["value"], "ABDEFG")

        self.assertEqual(query["where"][1]["field"], "some_other_field")
        self.assertEqual(query["where"][1]["operator"], "==")
        self.assertEqual(query["where"][1]["value"], 2000)

    def test_should_parse_valid_update_with_limit_and_where_query(self):
        query = parse("""
            update from SOME_COLLECTION
                      set some_field = "ABC", some_other_field = 2000
                      where some_field == "ABDEFG" and some_other_field == 2000
        """)

        self.assertIsNotNone(query["where"])
        self.assertEqual(len(query["where"]), 2)

        self.assertEqual(query["where"][0]["field"], "some_field")
        self.assertEqual(query["where"][0]["operator"], "==")
        self.assertEqual(query["where"][0]["value"], "ABDEFG")

        self.assertEqual(query["where"][1]["field"], "some_other_field")
        self.assertEqual(query["where"][1]["operator"], "==")
        self.assertEqual(query["where"][1]["value"], 2000)

        self.assertIsNotNone(query["set"])
        self.assertEqual(len(query["set"]), 2)

        self.assertEqual(query["set"][0]["property"], "some_field")
        self.assertEqual(query["set"][0]["value"], "ABC")

        self.assertEqual(query["set"][1]["property"], "some_other_field")
        self.assertEqual(query["set"][1]["value"], 2000)

    def test_should_not_parse_update_that_does_not_have_where(self):
        with self.assertRaises(QuerySyntaxError):
            parse("""
                update from SOME_COLLECTION
                          set some_field = "ABC", some_other_field = 2000
            """)

    def test_should_parse_valid_select_on_collection_group(self):
        query = parse('select * within SOME_COLLECTION_GROUP limit 10')
        self.assertEqual(query["query_type"], FSQLQueryType.SELECT)
        self.assertEqual(query["fields"], "*")
        self.assertEqual(query["subject_type"],
                         FSQLSubjectType.COLLECTION_GROUP)
        self.assertEqual(query["subject"], "SOME_COLLECTION_GROUP")
        self.assertIsNone(query["where"])
        self.assertEqual(query["limit"], 10)


    def test_should_not_parse_document_select_that_has_where(self):
        with self.assertRaises(QuerySyntaxError):
            parse("""
                select * at "SOME_COLLECTION/DOC_ID" where some_field == 2000
            """)

    def test_should_not_parse_delete_that_does_not_have_where(self):
        with self.assertRaises(QuerySyntaxError):
            parse("""
                delete from SOME_COLLECTION
            """)

    def test_should_not_parse_invalid_select(self):
        with self.assertRaises(QuerySyntaxError):
            parse('select from SOME_COLLECTION')


if __name__ == '__main__':
    unittest.main()
