#!/usr/bin/python3

from flask import Flask, jsonify, Markup, render_template, request, send_file, make_response
from lxml import etree
from lxml.html import fromstring
import datetime
import html
import json
import konstruktikon_browser
import login
import math
import os
import re
import sqlite_browser
import time
import urllib.parse

browser = konstruktikon_browser.Browser("konstruktikon2.xml")
app = Flask(__name__)


@app.route('/')
def hello_world():
    phrases = browser.lex.xpath("//LexicalEntry")
    constructions = [le.xpath('Sense')[0].attrib["id"].replace("konstruktikon-rus--", "").replace("_", " ") for le in phrases]
    return render_template("main_page.html", base=constructions)


def karp_example2html(example_tag):
    inner_html = etree.tostring(example_tag, pretty_print=True, encoding="unicode")
    x = re.sub(r"</?karp:example.*>", "", inner_html)
    x = re.sub(r"</?definition>", "", x) # if 'definition' tag was passed in args2
    x = re.sub(r'<karp:e\s+.*name="([^"]+)"[^>]*>', '<font color="red"><small>\g<1>[</small></font>', x)
    x = re.sub(r'</karp:e>(?=[\n\s\t]*<karp:[^g])', '<font color="red"></small>]</small></font>&nbsp;', x)
    x = re.sub(r'</karp:e>', '<font color="red"></small>]</small></font>', x)
    x = re.sub(r'<karp:g[^>]*>', '', x)
    x = re.sub(r'</*karp:text[^>]*/*\s*>', '', x)
    return Markup(x)


def karp_example2cats(example_tag):
    inner_html = etree.tostring(example_tag, pretty_print=True, encoding="unicode")
    x = re.sub(r"</?karp:example.*>", "", inner_html)
    x = re.sub(r"</?definition>", "", x)  # if 'definition' tag was passed in args2
    cats = [mth.group(1) for mth in re.finditer(r'<karp:e\s+.*name="([^"]+)"[^>]*>', x)]
    return cats


@app.route("/hints")
def ajax_hints():
    if "prefix" not in request.args:
        return jsonify(
            {"error": "Prefix expected, but was not found"}
        )

    limit = 5 if "limit" not in request.args else int(request.args["limit"])
    hints = []

    for entry in browser.entries_walk({
        "prefix": request.args["prefix"]
    }):
        name = entry.xpath("Sense")[0].attrib["id"]
        meta, name = name.split("--")
        hints.append(" ".join(name.split("_")))
        limit -= 1
        if not limit:
            break

    return jsonify(
        {"hints": hints}
    )


SEARCH_URL = "/search"


@app.route(SEARCH_URL)
def browser_search():
    if "q" not in request.args:
        return "Invalid request"

    offset = 0 if "offset" not in request.args else int(request.args["offset"])
    selected_index = 1 if "index" not in request.args else int(request.args["index"])

    try:
        query = json.loads(request.args["q"])
        if type(query) != dict:
            raise json.decoder.JSONDecodeError
    except json.decoder.JSONDecodeError:
        return "Invalid request"

    results = browser.entries_walk(query)
    max_on_page = 5
    max_offsets = 20

    basic_url = SEARCH_URL + "?q=" + urllib.parse.quote(request.args["q"])
    index_url = [basic_url]

    if len(results) < max_on_page * max_offsets:
        page_indexes = list(range(1, math.ceil(len(results) / max_on_page) + 1))
        pages_count = max_on_page
        for index in page_indexes:
            index_url.append(basic_url + "&offset=" + str(max_on_page * index) + "&index=" + str(index + 1))
    else:
        page_indexes = list(range(1, max_offsets + 1))
        rest = math.ceil(len(results) / max_offsets)
        pages_count = rest
        for n in range(1, max_offsets):
            index_url.append(basic_url + "&offset=" + str(rest * n) + "&index=" + str(n + 1))

    query = json.loads(request.args["q"])
    found = browser.entries_walk(query)
    entries = []

    for tag in found:
        entry_dict = {}
        name = tag.xpath("Sense")[0].attrib["id"]
        entry_dict["ID"] = name
        meta, name = name.split("--")
        entry_dict["name"] = " ".join(name.split("_"))

        for param in ["cefr", "illustration", "structure"]:
            try:
                entry_dict[param] = tag.xpath("Sense/feat[@att='{0}']".format(param))[0].attrib["val"]
            except IndexError:
                entry_dict[param] = "?"

        entry_dict["definition"] = karp_example2html(tag.xpath("Sense/definition")[0])
        entry_dict["content_cats"] = karp_example2cats(tag.xpath("Sense/definition")[0])
        entry_dict["content_cats"] = Markup(",&nbsp;".join([
            ('<a href="{1}" class="__field__ccat"><font color="red" class="ccat"><small class="ccat">{0}</small>' +
            '</font></a>').format(
                cat, '/search?q=%s' % urllib.parse.quote('{"sem_search":["%s"]}' % cat)
            )
            for cat in set(entry_dict["content_cats"])
            if not re.search(r'[А-Яа-я]', cat)
        ]))

        try:
            entry_dict["semantics"] = ""
            sem1, sem12, sem2, sem22 = [
                tag.xpath("Sense/feat[@att='%s']" % st)[0] for st in ["SemType1", "SemSubType1", "SemType2", "SemSubType2"]
            ]
            synt_el = tag.xpath("Sense/feat[@att='Syntax']")[0]
            if sem1.attrib["val"]:
                entry_dict["semantics"] += ('<a href="{1}" class="__field__ccat"><font color="red" class="ccat">' +
                '<small class="ccat">{0}</small></font></a>').format(
                    sem1.attrib["val"], "/search?q=%s" % urllib.parse.quote('{"sem_search":["%s"]}' % sem1.attrib["val"])
                )
            if sem12.attrib["val"]:
                entry_dict["semantics"] += ('&nbsp;(<a href="{1}" class="__field__ccat"><font color="red" class="ccat">' +
                                            '<small class="ccat">{0}</small></font></a>)').format(
                    sem12.attrib["val"], "/search?q=%s" % urllib.parse.quote('{"sem_search":["%s"]}' % sem12.attrib["val"])
                )
            if sem2.attrib["val"]:
                entry_dict["semantics"] += (',&nbsp;<a href="{1}" class="__field__ccat"><font color="red" class="ccat">' +
                '<small class="ccat">{0}</small></font></a>').format(
                    sem2.attrib["val"], "/search?q=%s" % urllib.parse.quote('{"sem_search":["%s"]}' % sem2.attrib["val"])
                )
            if sem22.attrib["val"]:
                entry_dict["semantics"] += ('&nbsp;(<a href="{1}" class="__field__ccat"><font color="red" class="ccat">' +
                                            '<small class="ccat">{0}</small></font></a>)').format(
                    sem22.attrib["val"], "/search?q=%s" % urllib.parse.quote('{"sem_search":["%s"]}' % sem22.attrib["val"])
                )
            entry_dict["semantics"] = Markup(entry_dict["semantics"])

            entry_dict["syntax"] = Markup(",&nbsp;".join([
                ('<a href="{1}" class="__field__ccat"><font color="red" class="ccat"><small class="ccat">{0}</small>' +
                 '</font></a>').format(
                    cat, '/search?q=%s' % urllib.parse.quote('{"synt_search":["%s"]}' % cat)
                )
                for cat in set(synt_el.attrib["val"].split(","))
            ]))
        except IndexError:
            entry_dict["semantics"] = "-"
            entry_dict["syntax"] = "-"

        karp = dict(namespaces={
            "karp": "http://spraakbanken.gu.se/eng/research/infrastructure/karp/karp"
        })
        examples = tag.xpath("Sense/karp:example", **karp)
        entry_dict["examples"] = []

        for examp in examples:
            try:
                examp_name = examp.xpath("karp:e", **karp)[0].attrib["name"]
            except IndexError:
                continue
            entry_dict["examples"].append({
                "name": examp_name,
                "sentence": karp_example2html(examp)
            })

        entries.append(entry_dict)

    return render_template(
        "search_results.html",
        count=len(entries),
        entries=entries[offset:offset+pages_count],
        index_url=index_url,
        page_indexes=page_indexes,
        selected_index=selected_index
    )


def entry_repack(data):
    return_data = []
    for (k, v) in data:
        if k == "cee":
            for _el in json.loads(v):
                return_data.append(("cee.OBJECT", _el))
        elif k == "syntax":
            for _el in json.loads(v):
                return_data.append(("syntax.OBJECT", _el))
        elif k == "Structures":
            for _el in json.loads(v):
                return_data.append(("Structures.OBJECT", _el))
        elif k == "definition":
            common_text = ""
            for part in json.loads(v)["definition"]:
                if "content" in part and type(part["content"]) == str:
                    common_text += part["content"]
            common_text = re.sub(r"\n", " ", common_text)
            common_text = re.sub(r"\s+", " ", common_text)
            return_data.append(("definition.TEXT", common_text))
        elif k == "examples":
            for ex_json in json.loads(v)["examples"]:
                example_text = ""
                for part in ex_json:
                    if "content" in part and type(part["content"]) == str:
                        example_text += part["content"]
                    if "children" in part:
                        for part2 in part["children"]:
                            if "content" in part2 and type(part2["content"]) == str:
                                example_text += " " + part2["content"]
                example_text = re.sub(r"\n", " ", example_text)
                example_text = re.sub(r"\s+", " ", example_text)
                return_data.append(("examples.OBJECT", example_text))
        else:
            return_data.append((k, v))

    return return_data


@app.route("/auth", methods=["GET", "POST"])
def auth_func():
    return render_template("credentials.html", returnto=request.args["returnto"])


@app.route("/auth_", methods=["GET", "POST"])
def auth_process():
    m = login.LoginManager()
    if request.form["req_type"] == "register":
        m.create_account(**dict(request.form))
    resp = make_response("konstruktikon login")
    resp.set_cookie("konst_session", m.get_session(**dict(request.form)), max_age=60 * 60 * 24 * 365 * 2)
    resp.headers["location"] = "/entry_edit?_id=" + request.form["returnto"]
    return resp, 302


@app.route("/entry_edit")
def entry_edit():
    if "_id" not in request.args:
        return "Invalid request"

    s = request.cookies.get("konst_session")
    if not s:
        resp = make_response("go auth")
        resp.headers["location"] = "/auth?returnto=" + request.args["_id"]
        return resp, 302

    browser = sqlite_browser.BaseBrowser()
    this = browser.get_entries("'%s'" % request.args["_id"])
    try:
        data = [list(g) for (k, g) in this][0]
        data = [(x[1], x[2]) for x in data]
    except IndexError:
        data = [("ENTRY_ID", request.args["_id"])]

    data.append(("lastModifiedBy", s))
    data = entry_repack(data)

    browser.stop_session()

    body = etree.Element("body")
    table = etree.SubElement(body, "table", attrib=dict(contenteditable="true"))

    tr1 = etree.SubElement(table, "tr")

    prop = etree.SubElement(tr1, "th")
    prop.text = "Property"
    val = etree.SubElement(tr1, "th")
    val.text = "Value"
    items = []

    for (p, v) in data:
        items.append(etree.SubElement(table, "tr"))
        items.append(etree.SubElement(items[-1], "td"))
        items[-1].text = p
        items.append(etree.SubElement(items[-1], "td"))
        items[-1].text = v

    add_interface = [
        etree.SubElement(body, "select"),
        etree.SubElement(body, "input", attrib=dict(type="text")),
        etree.SubElement(body, "button", attrib=dict(onclick="addField()"))
    ]
    add_interface[-1].text = "Add field"
    types2add = [
        "examples.TEXT", "syntax.OBJECT", "illustration", "lastModified",
        "lastModifiedBy", "Structures", "SemType1", "SemType2",
        "SemSubType1", "SemSubType2", "usageLabels.OBJECT"
    ]
    _options = []
    for typ in types2add:
        _options.append(etree.SubElement(add_interface[0], "option", attrib=dict(value=typ)))
        _options[-1].text = typ

    script = etree.SubElement(body, "script")
    script.text = """
    function addField () {
        item = document.createElement("tr");
        prop = document.createElement("td");
        prop.innerHTML = document.querySelector("select").value;
        item.appendChild(prop);
        val = document.createElement("td");
        val.innerHTML = document.querySelector("input[type=text]").value;
        item.appendChild(val);
        document.querySelector("table").appendChild(item);
    }
    function updateEntry () {
        post_form = document.createElement("form");
        post_form.setAttribute("action", "/entry_submit");
        post_form.setAttribute("method", "POST");
        table_data = document.createElement("input");
        table_data.setAttribute("name", "table_data");
        table_data.setAttribute("value", document.querySelector("table").innerHTML);
        entry_id = document.createElement("input");
        entry_id.setAttribute("name", "entry_id");
        entry_id.setAttribute("value", ENTRY_ID);
        post_form.appendChild(table_data);
        post_form.appendChild(entry_id);
        document.body.appendChild(post_form);
        document.form[0].submit();
    }
    """
    script.text += "ENTRY_ID = '{_id}'".format(**request.args)

    br = etree.SubElement(body, "br")
    send = etree.SubElement(body, "button", attrib=dict(onclick="updateEntry()"))
    send.text = "Update entry"

    return etree.tostring(body, encoding="unicode")


@app.route("/entry_submit", methods=["POST"])
def entry_submit():
    if "table_data" not in request.form or "entry_id" not in request.form:
        return "Invalid request"

    entry_id = request.form["entry_id"]
    table = fromstring(request.form["table_data"])
    table_items = []
    for n, tr_tag in enumerate(table.cssselect("tr")):
        if n == 0:
            continue
        table_items.append(el.text for el in tr_tag.cssselect("td"))

    agent = sqlite_browser.BaseBrowser()
    flds = {}
    fields = agent.get_entries("'%s'" % entry_id)
    for _id, this in fields:
        for row in this:
            flds[row[1]] = row[2]

    if table_items:
        agent.add_field([
            entry_id,
            "lastModified",
            datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        ])

    for (key, value) in table_items:
        if key == "language":
            agent.add_field([entry_id, "language", value], rewrite=True)
        if key == "cee.OBJECT":
            if "cee" in flds:
                agent.add_field([entry_id, "cee", json.dumps(json.loads(flds["cee"]) + [value])], True)
            else:
                agent.add_field([entry_id, "cee", json.dumps([value])])
        if key == "usageLabels.OBJECT":
            if "usageLabels" in flds:
                agent.add_field([entry_id, "usageLabels", json.dumps(json.loads(flds["usageLabels"]) + [value])], True)
            else:
                agent.add_field([entry_id, "usageLabels", json.dumps([value])])
        if key == "cefr":
            agent.add_field([entry_id, "cefr", value])
        if key == "definition.TEXT":
            agent.add_field([
                entry_id,
                "definition",
                json.dumps(
                    dict(
                        definition=dict(
                            type="InsideDefinition",
                            cat="text",
                            content=value,
                            n="0"
                        )
                    )
                )
            ], rewrite=True)
        if key == "examples.TEXT.OBJECT":
            examples = json.loads(flds["examples"])["examples"]
            examples.append(
                dict(
                    type="SimpleType",
                    cat="text",
                    content=value,
                    n="0"
                )
            )
            agent.add_field([
                entry_id,
                "examples",
                json.dumps(dict(examples=examples))
            ], rewrite=True)
        if key == "syntax.OBJECT":
            agent.add_field([
                entry_id,
                "syntax",
                json.dumps(json.loads(flds["syntax"]) + [value])
            ], rewrite=True)
        if key == "illustration":
            agent.add_field([entry_id, "illustration", value], rewrite=True)
        if key == "Structures":
            agent.add_field([entry_id, "Structures", value], rewrite=True)
        if key == "SemType1":
            agent.add_field([entry_id, "SemType1", value], rewrite=True)
        if key == "SemSubType1":
            agent.add_field([entry_id, "SemSubType1", value], rewrite=True)
        if key == "SemType2":
            agent.add_field([entry_id, "SemType2", value], rewrite=True)
        if key == "SemSubType2":
            agent.add_field([entry_id, "SemSubType2", value], rewrite=True)

    agent.stop_session()

    return "Submitted."


if __name__ == "__main__":
    app.run(host="0.0.0.0")
