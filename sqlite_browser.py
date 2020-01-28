#!/usr/bin/python3

import sqlite3
from xml2sqlite import SQLAgent

escape_q = lambda s: s.replace("'", "\\'")


class BaseBrowser(SQLAgent):
    def __init__(self, sqlite_filename="newBase.sqlite3"):
        super().__init__(sqlite_filename)

    @staticmethod
    def fields_of_entry(entry_id, f_type):
        return "SELECT field_content FROM konstruktikon_xml " +\
               "WHERE entry_id='{0}' AND field_type='{1}'".format(
            entry_id, f_type
        )

    @staticmethod
    def all_fields_of_entry(entry_id):
        return "SELECT field_type, field_content FROM konstruktikon_xml " +\
                "WHERE entry_id='{0}'".format(entry_id)

    @staticmethod
    def entries_by_field_value(f_type, f_lambda_str):
        return "SELECT entry_id FROM konstruktikon_xml " +\
                "WHERE field_type='{0}' AND ".format(f_type) +\
                f_lambda_str

    @staticmethod
    def generate_or_group(param, values):
        return "(" + " OR ".join(["%s='%s'" % (param, vn) for vn in values]) + ")"

    def generate_filter(self, filter_dict):
        select_queries = []
        if "substring" in filter_dict:
            select_queries.append(
                "SELECT entry_id FROM konstruktikon_xml WHERE field_type LIKE '%{substr}%'".format(
                    substr=filter_dict["substring"]
                )
            )
        if "sem_search" in filter_dict:
            select_queries.append(
                "SELECT entry_id FROM konstruktikon_xml, json_tree(konstruktikon_xml.field_content) " +
                "WHERE json_valid(field_content) AND field_type='definition' AND path LIKE '$.definition[%%]' " +
                "AND key='name' AND " + self.generate_or_group("value", filter_dict["sem_search"])
            )
        if "sem_search2" in filter_dict:
            select_queries.append(
                "SELECT entry_id FROM konstruktikon_xml WHERE " +
                self.generate_or_group("field_content", filter_dict["sem_search2"]) +
                " AND field_type LIKE '%Sem%"
            )
        if "syntax" in filter_dict:
            select_queries.append(
                "SELECT entry_id FROM konstruktikon_xml, json_tree(konstruktikon_xml.field_content) " +
                "WHERE json_valid(field_content) AND field_type='syntax' AND " +
                self.generate_or_group("field_content", filter_dict["syntax"])
            )
        if "gram_search" in filter_dict:
            select_queries.append(
                "SELECT entry_id FROM konstruktikon_xml WHERE entry_id LIKE '%{gram}%".format(
                    gram=filter_dict["gram_search"]
                )
            )

    lambda_str_equal = lambda v: "field_content='%s'" % escape_q(v)
    lambda_str_contains = lambda v: "'%s' in field_content" % escape_q(v)
    lambda_json_query = lambda q: q


