"""Contextual LG marker normalization on saved pages and focused fixtures."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from bs4 import BeautifulSoup

from product_tool import jobs, storage
from product_tool.adapters.common import RawAttribute, SourceDocument
from product_tool.adapters.lg import extract_lg_attributes, extract_lg_ru_attributes
from product_tool.fetch_history import latest_source_snapshot
from product_tool.normalization import normalize_fact, normalize_facts, normalize_value
from product_tool.resolution import resolve_attributes

DB=Path(__file__).resolve().parents[1]/"data"/"batches.sqlite3"
BATCH="ae3d2cb381744ba8a811e54231233254"

def kz_html(values):
    rows="".join(
        '<li class="c-compare-selling__item"><span class="c-compare-selling__spec-name">'+name+
        '</span><span class="c-compare-selling__spec-desc">'+value+'</span></li>'
        for name,value in values
    )
    return ('<div id="pdp-specs-section"><div class="c-compare-selling--all">'
            '<div class="c-compare-selling__table"><h4>ФУНКЦИИ</h4>'+rows+
            '</div></div></div>')

class LGMarkerCells(unittest.TestCase):
    def test_exact_markers_empty_and_composites(self):
        html=kz_html([
            ("Filled","●"),("Bullet","•"),("Open","○"),
            ("Hyphen","-"),("Dash","—"),("Empty",""),
            ("Two modes","● / —"),("Bluetooth","●"),("Bluetooth","ver 4.0"),
        ])
        raw=extract_lg_attributes(BeautifulSoup(html,"html.parser"))
        self.assertEqual(len(raw),9)
        self.assertTrue(all(f.section=="ФУНКЦИИ" and f.value_cell is True for f in raw))
        self.assertIn(RawAttribute("Empty","","ФУНКЦИИ",True),raw)
        facts={f.normalized_name:f for f in normalize_facts(raw)}
        for name in ("filled","bullet","bluetooth"):
            self.assertEqual((facts[name].normalized_value,facts[name].unit),("true","bool"))
        self.assertEqual((facts["open"].normalized_value,facts["open"].unit),("unknown","unknown"))
        for name in ("hyphen","dash"):
            self.assertEqual((facts[name].normalized_value,facts[name].unit),("false","bool"))
        self.assertEqual((facts["empty"].raw_value,facts["empty"].normalized_value),("","unknown"))
        self.assertEqual((facts["two_modes"].normalized_value,facts["two_modes"].unit),("true/false","bool_vector"))
        self.assertEqual((facts["bluetooth_version"].normalized_value,facts["bluetooth_version"].unit),("4",""))
        self.assertEqual(normalize_value("Feature","-",value_cell=False),("-",""))
        self.assertEqual(normalize_fact(RawAttribute("Feature","-",value_cell=False)).unit,"")
        self.assertEqual(normalize_value("Feature","● / —",value_cell=True),("true/false","bool_vector"))

    def test_ru_o_version_and_empty_not_false(self):
        html=('''<div id="pdp_spec"><div class="tech-spacs">
             <div class="tech-spacs-title">Интерфейсы</div>
             <div class="tech-spacs-contents">
             <dl><dt>Bluetooth</dt><dd>O v 4.0, диапазон 2402~2480MHz</dd></dl>
             <dl><dt>Пульт</dt><dd>O</dd></dl>
             <dl><dt>Кабель</dt><dd></dd></dl>
             </div></div></div>''')
        raw=extract_lg_ru_attributes(BeautifulSoup(html,"html.parser"))
        self.assertEqual(len(raw),3)
        facts=normalize_facts(raw)
        by={(f.normalized_name,f.normalized_value) for f in facts}
        self.assertIn(("bluetooth","true"),by)
        self.assertIn(("bluetooth_version","4"),by)
        self.assertIn(("пульт","true"),by)
        self.assertIn(("кабель","unknown"),by)
        pages=[{"source_key":"lg_ru","site_name":"LG","match_level":"full_sku"},
               {"source_key":"lg_kz","site_name":"LG","match_level":"full_sku"}]
        supplied=[{"source_key":"lg_ru","site_name":"LG",**f.__dict__} for f in facts]
        supplied.append({"source_key":"lg_kz","site_name":"LG",
                         **normalize_fact(RawAttribute("Версия Bluetooth","4","Совместимость",True)).__dict__})
        resolved=resolve_attributes(supplied,pages)
        self.assertNotIn("кабель",{r.normalized_name for r in resolved})
        self.assertFalse(any(r.conflict for r in resolved))

    def test_raw_empty_and_section_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"fixture.sqlite3"
            jobs.initialize(db)
            with storage._connection(db) as c:
                c.execute("INSERT INTO batches (id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('b','fixture.xlsx','s','{}','2026-09-29')")
                c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'b',1,'','LG','X','','test',0,'[]','{}')")
            html=kz_html([("Feature","●"),("Missing","")])
            raw=extract_lg_attributes(BeautifulSoup(html,"html.parser"))
            jobs.save_source_document(db,1,SourceDocument("lg_kz","LG","https://example.test/x",found_model="X",match_level="full_sku",attributes=raw,html=html))
            jobs.resolve_product(db,1)
            rows=jobs.get_facts(db,1)
            empty=next(x for x in rows if x["raw_name"]=="Missing")
            self.assertEqual((empty["raw_value"],empty["section"],empty["value_cell"],empty["normalized_value"]),("","ФУНКЦИИ",1,"unknown"))
            self.assertNotIn("missing",{x["normalized_name"] for x in jobs.get_resolved(db,1)})

    def test_saved_batch_marker_counts(self):
        if not DB.exists():
            self.skipTest("Working LG database unavailable")
        counts=Counter()
        for pid in (4,5,6,7,8,9,10,11,12,13,14,15):
            product=jobs.get_product(DB,pid)
            self.assertEqual(product["batch_id"],BATCH)
            for source,extractor in (("lg_kz",extract_lg_attributes),("lg_ru",extract_lg_ru_attributes)):
                snap=latest_source_snapshot(DB,pid,source)
                if not snap or not snap["content"]:
                    continue
                for f in extractor(BeautifulSoup(snap["content"],"html.parser")):
                    counts[f.value]+=1
        self.assertEqual(counts["●"],357)
        self.assertEqual(counts["O"],68)
        self.assertEqual(counts["-"],13)

if __name__=="__main__":
    unittest.main()

