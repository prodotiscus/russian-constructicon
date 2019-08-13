#!/usr/bin/python3

from lxml import etree
import re


class Browser:
    def __init__(self, konst_file):
        self.konst_file = konst_file
        self.konst_xml = etree.parse(konst_file)
        self.lex = self.konst_xml.xpath("/LexicalResource/Lexicon")[0]

    def entries_walk(self, search_request):
        # TODO: replace with iterator
        entries = []
        for entry in self.lex.xpath("//LexicalEntry"):
            if LexicalEntry(entry).test_entry(search_request):
                entries.append(entry)

        return entries


class StructureParser:
    def __init__(self, q):
        q = re.sub("\[(\w+)\]", "<\g<1>/>", q)
        q = re.sub("\[(\w+)", "<\g<1>>", q)
        q = q.replace(" ", "")
        tag_groups = []

        for group in re.split("\]+", q):
            if not group:
                continue
            tag_groups.append(re.findall("<\w+>", group))

        g = -1
        b = False
        for e, char in enumerate(q):
            if not b and char == "]":
                b = True
                g += 1
            if char == "]":
                try:
                    q = q.replace("]", "</" + tag_groups[g].pop()[1:], 1)
                except IndexError:
                    pass
            else:
                b = False

        for group in reversed(tag_groups):
            for tag in reversed(group):
                q = q.replace("]", "</" + tag[1:], 1)

        self.tree = etree.fromstring(q)

    @staticmethod
    def between_tags(tag1, tag2, same_level=True):
        query = "//*["
        query += "preceding::" + tag1 + " and following::" + tag2
        if same_level:
            query += " and count(ancestor::*) = count(" + tag1 + "/ancestor::*)"
        query += "]"

        return query

    @staticmethod
    def test(filt):
        # TODO
        return False


class LexicalEntry:
    def __init__(self, entry_tag):
        self.entry_tag = entry_tag

    def test_entry(self, filter_dict):
        return (
                ("prefix" in filter_dict and self.name_prefix(filter_dict["prefix"])) or
                ("sem_search" in filter_dict and self.toksem_and_filsem(filter_dict["sem_search"])) or
                ("structure" in filter_dict and self.structure_contains(filter_dict["structure"]))
               ) and \
               (
                ("cefr" not in filter_dict or self.cefr(filter_dict["cefr"])) and
                ("language" not in filter_dict or self.language(filter_dict["language"]))
               )

    def name_prefix(self, prefix):
        name = self.entry_tag.xpath("Sense")[0].attrib["id"]
        meta, name = name.split("--")
        name = " ".join(name.lower().split("_"))
        prefix = " ".join(prefix.lower().split())

        try:
            return name.startswith(prefix)
        except KeyError:
            return False

    def cefr(self, cefr_options):
        try:
            cefr_elem = self.entry_tag.xpath("Sense/feat[@att='cefr']")[0]
        except IndexError:
            return False

        try:
            return cefr_elem.attrib["val"] in cefr_options
        except KeyError:
            return False

    @staticmethod
    def language(language_options):
        # TODO
        return False

    def toksem_and_filsem(self, filsem):
        try:
            first_def = self.entry_tag.xpath("Sense/definition")[0]
        except IndexError:
            return False

        for karp_tag in first_def.xpath("*"):
            if "name" in karp_tag.attrib and karp_tag.attrib["name"].strip("., ") in filsem:
                return True

        return False

    def structure_contains(self, struct_filter):
        structures = self.entry_tag.xpath("Sense/feat[@att='structure']")
        for struct in structures:
            parser = StructureParser(struct)
            if parser.test(struct_filter):
                return True

        return False


"""
browser = Browser("konstruktikon.xml")
entry1 = browser.lex.xpath("LexicalEntry")[0]
entry1 = LexicalEntry(entry1)

print(entry1.toksem_and_filsem(["Theme"]))
"""
