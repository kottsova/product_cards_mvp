"""Stage 48 offline regression against saved Stage 47 LG product snapshots."""
from __future__ import annotations
from pathlib import Path
import unittest
from dataclasses import asdict
from bs4 import BeautifulSoup

from product_tool import jobs
from product_tool.adapters.common import RawAttribute
from product_tool.adapters.lg import extract_lg_attributes, extract_lg_ru_attributes
from product_tool.fetch_history import latest_source_snapshot
from product_tool.normalization import normalize_fact, normalize_facts
from product_tool.resolution import resolve_attributes

DB=Path(__file__).resolve().parents[1]/"data"/"batches.sqlite3"
IDS=(7,8,9,10,11,12,14)
EXPECTED_CONFLICTS=(3,3,0,2,0,0,0)

class LGStage48Semantics(unittest.TestCase):
    def test_separate_concepts(self):
        washer=normalize_fact(RawAttribute("AI DD","Да","ОСОБЕННОСТИ СТИРАЛЬНОЙ МАШИНЫ"))
        dryer=normalize_fact(RawAttribute("AI DD","Нет","ОСОБЕННОСТИ СУШИЛЬНОЙ МАШИНЫ"))
        self.assertNotEqual(washer.normalized_name,dryer.normalized_name)
        self.assertEqual(normalize_fact(RawAttribute("Хлопок+","Нет")).normalized_name,"хлопок_plus")
        self.assertEqual(normalize_fact(RawAttribute("Bluetooth","ver 4.0")).normalized_name,"bluetooth_version")
        self.assertEqual(normalize_fact(RawAttribute("Вес без упаковки (кг)","70")).normalized_name,"product_weight")
        self.assertEqual(normalize_fact(RawAttribute("Вес с упаковкой (кг)","78")).normalized_name,"package_weight")
        self.assertEqual(normalize_fact(RawAttribute("Кабель питания","Да (Прикрепленный к)")).normalized_value,"true")
        self.assertEqual(normalize_fact(RawAttribute("Гарантийный талон","O","Пульт дистанционного управления и аксессуары")).normalized_value,"true")
        self.assertEqual(normalize_fact(RawAttribute("Телескопическая трубка","Телескопическая")).normalized_value,"true")

    def test_saved_stage47_snapshots(self):
        if not DB.exists():
            self.skipTest("Working LG database is unavailable")
        for pid, expected in zip(IDS,EXPECTED_CONFLICTS):
            with self.subTest(product_id=pid):
                facts=[f for f in jobs.get_facts(DB,pid) if f['source_key'] not in ('lg_kz','lg_ru')]
                pages=jobs.get_source_pages(DB,pid)
                seen=0
                for source, extractor in (('lg_kz',extract_lg_attributes),('lg_ru',extract_lg_ru_attributes)):
                    page=next((p for p in pages if p['source_key']==source),None)
                    snap=latest_source_snapshot(DB,pid,source)
                    if not page or not snap or not snap['content'] or page['url']!=snap['source_url']:
                        continue
                    raw=extractor(BeautifulSoup(snap['content'],'html.parser'))
                    self.assertTrue(raw)
                    self.assertTrue(all(a.section for a in raw))
                    facts.extend({'source_key':source,'site_name':page['site_name'],**asdict(f)} for f in normalize_facts(raw))
                    seen+=1
                self.assertGreaterEqual(seen,1)
                resolved=resolve_attributes(facts,pages,jobs.get_manual_decisions(DB,pid))
                self.assertEqual(sum(bool(r.conflict) for r in resolved),expected)

if __name__=="__main__":
    unittest.main()

