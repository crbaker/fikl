"""Tests the Transformer class and language grammar"""
# pylint: disable=missing-function-docstring,missing-class-docstring,line-too-long,too-many-public-methods
import unittest

from lang.transformer import (parse, read_grammar, build_parse_tree,
                              FIKLQueryType, FIKLSubjectType, QuerySyntaxError)


class TestTransformer(unittest.TestCase):

    def test_read_grammer(self):
        grammar = read_grammar()
        self.assertIsNotNone(grammar)

    def test_should_build_parse_tree(self):
        tree = build_parse_tree('select * from SOME_COLLECTION')
        self.assertIsNotNone(tree)

    def test_should_parse_valid_select_query(self):
        query = parse('select * from SOME_COLLECTION')
        self.assertEqual(query["query_type"], FIKLQueryType.SELECT)
        self.assertEqual(query["fields"], "*")
        self.assertEqual(query["subject_type"], FIKLSubjectType.COLLECTION)
        self.assertEqual(query["subject"], "SOME_COLLECTION")
        self.assertIsNone(query["where"])
        self.assertIsNone(query["limit"])

    def test_should_parse_valid_select_with_fields_query(self):
        query = parse(
            'select first_field, "some.nested.field" from SOME_COLLECTION')
        self.assertEqual(query["query_type"], FIKLQueryType.SELECT)
        self.assertEqual(query["fields"], ["first_field", "some.nested.field"])
        self.assertEqual(query["subject_type"], FIKLSubjectType.COLLECTION)
        self.assertEqual(query["subject"], "SOME_COLLECTION")
        self.assertIsNone(query["where"])
        self.assertIsNone(query["limit"])

    def test_should_parse_valid_select_with_limit_query(self):
        query = parse('select * from SOME_COLLECTION limit 10')
        self.assertEqual(query["query_type"], FIKLQueryType.SELECT)
        self.assertEqual(query["fields"], "*")
        self.assertEqual(query["subject_type"], FIKLSubjectType.COLLECTION)
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

    def test_should_parse_valid_select_and_array_based_where_query(self):
        query = parse("""
            select * from SOME_COLLECTION
                      where some_field in ["ABDEFG", "HIJKLNOP"]
        """)

        self.assertIsNotNone(query["where"])
        self.assertEqual(len(query["where"]), 1)

        self.assertEqual(query["where"][0]["field"], "some_field")
        self.assertEqual(query["where"][0]["operator"], "in")
        self.assertEqual(query["where"][0]["value"], ["ABDEFG", "HIJKLNOP"])

    def test_should_parse_valid_document_update(self):
        query = parse("""
            update at "SOME_COLLECTION/DOC_ID"
                      set some_field = "ABC", some_other_field = 2000, some_nullable_field = null
        """)
        self.assertEqual(query["query_type"], FIKLQueryType.UPDATE)
        self.assertEqual(query["subject_type"], FIKLSubjectType.DOCUMENT)

        self.assertIsNotNone(query["set"])
        self.assertEqual(len(query["set"]), 3)

        self.assertEqual(query["set"][0]["property"], "some_field")
        self.assertEqual(query["set"][0]["value"], "ABC")

        self.assertEqual(query["set"][1]["property"], "some_other_field")
        self.assertEqual(query["set"][1]["value"], 2000)

        self.assertEqual(query["set"][2]["property"], "some_nullable_field")
        self.assertEqual(query["set"][2]["value"], None)

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
        self.assertEqual(query["query_type"], FIKLQueryType.SELECT)
        self.assertEqual(query["fields"], "*")
        self.assertEqual(query["subject_type"],
                         FIKLSubjectType.COLLECTION_GROUP)
        self.assertEqual(query["subject"], "SOME_COLLECTION_GROUP")
        self.assertIsNone(query["where"])
        self.assertEqual(query["limit"], 10)

    def test_should_parse_valid_select_on_document(self):
        query = parse('select * at "SOME_COLLECTION/DOC_ID"')
        self.assertEqual(query["query_type"], FIKLQueryType.SELECT)
        self.assertEqual(query["fields"], "*")
        self.assertEqual(query["subject_type"],
                         FIKLSubjectType.DOCUMENT)
        self.assertEqual(query["subject"], "SOME_COLLECTION/DOC_ID")
        self.assertIsNone(query["where"])
        self.assertIsNone(query["limit"], 10)

    def test_should_parse_valid_show_query(self):
        query = parse('show collections')
        self.assertEqual(query["query_type"], FIKLQueryType.SHOW)
        self.assertEqual(query["subject_type"], FIKLSubjectType.COLLECTION)

    def test_should_parse_valid_delete_query(self):
        query = parse('delete from COLLECTION where some_field == 2000')

        self.assertEqual(query["query_type"], FIKLQueryType.DELETE)
        self.assertEqual(query["subject_type"], FIKLSubjectType.COLLECTION)

        self.assertIsNotNone(query["where"])
        self.assertEqual(len(query["where"]), 1)

    def test_should_parse_valid_delete_document_query(self):
        query = parse('delete at "COLLECTION/DOC_ID"')

        self.assertEqual(query["query_type"], FIKLQueryType.DELETE)
        self.assertEqual(query["subject_type"], FIKLSubjectType.DOCUMENT)
        self.assertEqual(query["subject"], "COLLECTION/DOC_ID")

        self.assertIsNone(query["where"])

    def test_should_parse_valid_show_with_output(self):
        query = parse('select * from COLLECTION where some_field == 2000 output "~/output.json"')

        self.assertEqual(query["query_type"], FIKLQueryType.SELECT)
        self.assertEqual(query["subject_type"], FIKLSubjectType.COLLECTION)
        self.assertEqual(query["subject"], "COLLECTION")
        self.assertEqual(query["output"], "~/output.json")

    def test_should_parse_valid_insert(self):
        query = parse('insert into COLLECTION set some_field = 2000, some_other_field = "ABC", "some.nested.field" = "something" identified by "ABCD"')

        self.assertEqual(query["query_type"], FIKLQueryType.INSERT)
        self.assertEqual(query["subject_type"], FIKLSubjectType.COLLECTION)
        self.assertEqual(query["subject"], "COLLECTION")

        self.assertIsNotNone(query["set"])
        self.assertEqual(len(query["set"]), 3)

        self.assertEqual(query["set"][0]["property"], "some_field")
        self.assertEqual(query["set"][0]["value"], 2000)

        self.assertEqual(query["set"][1]["property"], "some_other_field")
        self.assertEqual(query["set"][1]["value"], "ABC")
        self.assertEqual(query["identifier"], "ABCD")

    def test_should_parse_valid_insert_with_no_identifier(self):
        query = parse('insert into COLLECTION set some_field = 2000, some_other_field = "ABC", "some.nested.field" = "something"')

        self.assertEqual(query["identifier"], None)

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
