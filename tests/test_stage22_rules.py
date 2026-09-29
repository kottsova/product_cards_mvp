"""Stage 22: two naming/format defects the second pilot showed on real pages, and their limits.

* One edge of the product (depth 455) or a depth counted with the door (495) is not the W x H x D triple: they are different quantities.
* A range written "87.5 ~ 108.0 MHz" and "87.5 - 108.0 МГц" is the same value; a different range is still a conflict.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from product_tool import jobs, worker
from product_tool.adapters.common import RawAttribute, SourceDocument
from product_tool.normalization import normalize_fact, normalize_name
from product_tool.resolution import _canonical_value

from test_lg_workflow import StaticAdapter, seed_product, source
from test_stage21_lg_fixes import D3DifferentQuantitiesKeepDifferentNames, _NoDealer


def fact(name, value):
    return normalize_fact(RawAttribute(name, value))


class DepthAndTheTriple(unittest.TestCase):
    conflicts = D3DifferentQuantitiesKeepDifferentNames.conflicts

    def test_one_edge_and_the_triple_get_different_names(self):
        self.assertNotEqual(normalize_name("Глубина (Г, мм)"), normalize_name("Размеры (Ш × В × Г, мм)"))
        self.assertEqual(normalize_name("Глубина (Г, мм)"), "product_dimensions__depth")
        self.assertEqual(normalize_name("Ширина (мм)"), "product_dimensions__width")
        self.assertEqual(normalize_name("Высота (мм)"), "product_dimensions__height")

    def test_depth_with_the_door_is_its_own_quantity(self):
        self.assertEqual(normalize_name("Глубина с учетом двери (Г' мм)"), "product_dimensions__depth_with_door")
        self.assertNotEqual(normalize_name("Глубина с учетом двери (Г' мм)"), normalize_name("Глубина (Г, мм)"))

    def test_the_same_edge_in_two_regions_keeps_one_name_and_two_depths_still_conflict(self):
        self.assertEqual(normalize_name("Глубина (мм)"), normalize_name("Глубина (Г, мм)"))
        self.assertEqual(self.conflicts([("Глубина (мм)", "455")], [("Глубина (Г, мм)", "455")]), [])
        self.assertEqual(self.conflicts([("Глубина (мм)", "455")], [("Глубина (Г, мм)", "495")]), ["product_dimensions__depth"])

    def test_the_pilot_row_no_longer_conflicts_inside_one_source(self):
        self.assertEqual(self.conflicts([("Глубина с учетом двери (Г' мм)", "495"), ("Размеры (Ш × В × Г, мм)", "600 x 850 x 455")]), [])

    def test_the_triple_itself_is_unchanged(self):
        self.assertEqual(fact("Размеры (Ш × В × Г, мм)", "600 x 850 x 455").normalized_name, "product_dimensions")
        self.assertEqual(fact("Размеры (Ш × В × Г, мм)", "600 x 850 x 455").normalized_value, "w=600;h=850;d=455")


class RangesAndUnits(unittest.TestCase):
    conflicts = D3DifferentQuantitiesKeepDifferentNames.conflicts

    def test_the_same_range_in_two_spellings_is_one_value(self):
        self.assertEqual(_canonical_value("87.5 - 108.0 мгц"), _canonical_value("87.5 ~ 108.0 mhz"))
        self.assertEqual(_canonical_value("60hz"), _canonical_value("60 Гц"))
        self.assertEqual(self.conflicts([("Диапазон", "87.5 - 108.0 мгц")], [("Диапазон", "87.5 ~ 108.0 mhz")]), [])

    def test_a_different_range_is_still_a_conflict(self):
        self.assertEqual(len(self.conflicts([("Диапазон", "87.5 - 108.0 мгц")], [("Диапазон", "88.0 ~ 108.0 mhz")])), 1)
        self.assertEqual(len(self.conflicts([("Диапазон", "87.5 - 108.0 мгц")], [("Диапазон", "87.5 - 108.0 кгц")])), 1)

    def test_symbols_with_no_proven_meaning_are_not_merged(self):
        self.assertEqual(len(self.conflicts([("Гарантийный талон", "o")], [("Гарантийный талон", "да")])), 1)


if __name__ == "__main__":
    unittest.main()
