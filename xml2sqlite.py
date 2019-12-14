#!/usr/bin/python3

import json
import lxml
import sqlite3
from konstruktikon_browser import *


class SQLiteFieldsFrom:
    def __init__(self, lexical_entry):
        self.entry_ = lexical_entry
        #if self.sense_id:
        self.entry = self.entry_.xpath("Sense")[0]
        self.karp_ns = dict(namespaces={
            "karp": "http://spraakbanken.gu.se/eng/research/infrastructure/karp/karp"
        })
        self.my_fields = []

    def build_fields(self):
        # create table konstruktikon_xml (entry_id text, field_type text, field_content text)
        if self.language:
            self.my_fields.append(
                [self.sense_id, "language", self.language]
            )
        if self.cee:
            self.my_fields.append(
                [self.sense_id, "cee", self.py2sqlt(self.cee)]
            )
        if self.cefr_level:
            self.my_fields.append(
                [self.sense_id, "cefr", self.cefr_level]
            )
        if self.definition_json:
            self.my_fields.append(
                [self.sense_id, "definition", self.py2sqlt(self.definition_json)]
            )
        if self.examples_json:
            self.my_fields.append(
                [self.sense_id, "examples", self.py2sqlt(self.examples_json)]
            )
        if self.illustration:
            self.my_fields.append(
                [self.sense_id, "illustration", self.illustration]
            )
        if self.last_modified:
            self.my_fields.append(
                [self.sense_id, "lastModified", self.last_modified]
            )
        if self.last_modified_by:
            self.my_fields.append(
                [self.sense_id, "lastModifiedBy", self.last_modified_by]
            )
        if self.structures:
            self.my_fields.append(
                [self.sense_id, "Structures", self.py2sqlt(self.structures)]
            )

        return self.my_fields

    @staticmethod
    def py2sqlt(raw):
        if type(raw) == str:
            return raw
        elif type(raw) == list:
            if raw and type(raw[0]) == dict:
                return json.dumps(raw)
            else:
                return json.dumps(raw)
        elif raw:
            return json.dumps(raw)

    @property
    def sense_id(self):
        try:
            return self.entry_.xpath("Sense")[0].attrib["id"]
        except IndexError:
            return None

    def caught_feat(self, att, from_=None):
        from_ = from_ if from_ else self.entry
        try:
            return from_.xpath("feat[@att='{0}']".format(att))[0].attrib["val"]
        except IndexError:
            return None

    def caught_multi_feat(self, att):
        get = self.entry.xpath("feat[@att='{0}']".format(att))
        return None if not get else [t.attrib["val"] for t in get]

    @property
    def language(self):
        for (attr, val) in self.entry_.attrib.items():
            if attr.endswith("lang"):
                return val
        return None

    @staticmethod
    def nsfree(tag_name):
        ns, tag = tag_name.split("}")
        return tag

    @property
    def example_tags(self):
        tags = self.entry.xpath("karp:example", **self.karp_ns)
        return tags if tags else None

    def parse_example(self, example_tag):
        linear = example_tag.xpath("karp:e|karp:text|karp:g", **self.karp_ns)
        json_f = []
        for element in linear:
            if self.nsfree(element.tag) in ["text", "g"]:
                obj = {
                    "type": "SimpleType",
                    "cat": self.nsfree(element.tag),
                    "content": element.text
                }
                for attr in ["name", "n"]:
                    if attr in element.attrib:
                        obj[attr] = element.attrib[attr]
                json_f.append(obj)
            elif self.nsfree(element.tag) == "e":
                json_f.append({
                    "type": "ETag",
                    "children": self.process_e(element),
                    "name": element.attrib["name"]
                })

        return json_f

    def process_e(self, e_tag):
        sub_linear = e_tag.xpath("karp:e|karp:text|karp:g", **self.karp_ns)
        json_f = []
        for element in sub_linear:
            obj = {
                "type": "InsideETag",
                "cat": self.nsfree(element.tag),
                "content": element.text
            }
            for attr in ["name", "n"]:
                if attr in element.attrib:
                    obj[attr] = element.attrib[attr]
            json_f.append(obj)

        return json_f

    @property
    def definition_json(self):
        defs = self.entry.xpath("definition", **self.karp_ns)
        if not len(defs):
            return {}
        my_def = defs[0]
        in_def = my_def.xpath("karp:e|karp:text|karp:g", **self.karp_ns)
        json_f = []
        for element in in_def:
            obj = {
                "type": "InsideDefinition",
                "cat": self.nsfree(element.tag),
                "content": element.text
            }
            for attr in ["name", "n"]:
                if attr in element.attrib:
                    obj[attr] = element.attrib[attr]
            json_f.append(obj)

        return dict(definition=json_f)

    @property
    def const_objects_json(self):
        return {}

    @property
    def examples_json(self):
        array = []
        if self.example_tags:
            for example in self.example_tags:
                array.append(self.parse_example(example))
            return {"examples": array}
        else:
            return {"examples": []}

    @property
    def last_modified(self):
        return self.caught_feat("lastmodified", self.entry_)

    @property
    def last_modified_by(self):
        return self.caught_feat("lastmodifiedBy", self.entry_)

    @property
    def name(self):
        if self.sense_id:
            pref, nme = self.sense_id.split("--")
            return nme

    @property
    def illustration(self):
        return self.caught_feat("illustration")

    @property
    def cefr_level(self):
        return self.caught_feat("cefr")

    @property
    def _type_(self):
        return self.caught_feat("type")

    @property
    def cee(self):
        return self.caught_multi_feat("cee")

    @property
    def structures(self):
        return self.caught_multi_feat("structure")


konst2 = Browser("konstruktikon2.xml")
lex = konst2.lex
sqlt_bases = []

for entry in lex.xpath("//LexicalEntry"):
    print(entry)
    q = SQLiteFieldsFrom(entry)
    print(q.build_fields())
