"""Stage 19 step 4 -- OFFLINE, zero requests. Hand every HyperX row that has a URL of record to the ordinary
worker.run_once() through the coverage executor, with the saved official pages as the only transport:

  * 2 Stage 15 rows       -> the Stage 11 / 11.1 saved pages,
  * 11 Stage 18 rows      -> the Stage 18 saved pages (one is the Stage 5.1 snapshot),
  * 7 Stage 19 rows       -> the pages fetched at their own ?variant= URLs in step 2.

Records, per row, the outcome, what was found (variant vs shared-model attributes, photos of the variant and the
ones excluded as other variants, documents) and any attribute still in conflict, and compares the five Stage 18
`needs_review` rows before and after the extraction rule change.

Output: controls/all_ready_summary.json, controls/all_ready_checkpoint.json
"""
from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
STAGE18 = ROOT / "reports/source_census_2026-09-24_stage18"
sys.path.insert(0, str(ROOT))

from product_tool import jobs  # noqa: E402
from product_tool.adapters.hyperx import HyperXAdapter, KNOWN_URLS  # noqa: E402
from product_tool.census.endpoint_probe import ProbePolicy  # noqa: E402
from product_tool.coverage import executor, planner  # noqa: E402
from product_tool.offline_guard import offline_only  # noqa: E402
from tests.coverage_controls import FixtureSession, MICROPHONE_PAGE, MOUSE_PAGE, NoDealer  # noqa: E402

STAGE18_REVIEW = ["4P5D4AA", "4P5J1AA", "4P5L3AA", "683L9AA", "B5VC4AA"]


def _gz(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return handle.read()


def saved_pages() -> dict[str, str]:
    pages = {KNOWN_URLS["9A273AA"]: MICROPHONE_PAGE.read_text(encoding="utf-8"), KNOWN_URLS["A1KY6AA"]: MOUSE_PAGE.read_text(encoding="utf-8")}
    for item in json.loads((STAGE18 / "raw/accepted_urls.json").read_text(encoding="utf-8"))["accepted"]:
        if item["basis"] == "saved_official_snapshot":
            connection = sqlite3.connect(f"file:{ROOT / item['database']}?mode=ro", uri=True)
            try:
                pages[item["url"]] = connection.execute("SELECT content FROM source_snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()[0]
            finally:
                connection.close()
        else:
            pages[item["url"]] = _gz(STAGE18 / item["saved_as"])
    for item in json.loads((STAGE / "raw/accepted_variant_urls.json").read_text(encoding="utf-8"))["accepted"]:
        pages[item["url"]] = _gz(STAGE / item["saved_as"])
    # 4P5D4AA: the sanitised Stage 5.1 snapshot has no product JSON and no gallery; step 5 fetched the real page once.
    pages[KNOWN_URLS["4P5D4AA"]] = _gz(STAGE / "raw/pages/products_hyperx-cloud-alpha-wireless.gz")
    return pages


def replay(out: Path, plan_units: list[dict] | None = None) -> tuple[dict, Path]:
    plan_units = plan_units if plan_units is not None else planner.build_plan()["units"]
    units = sorted((u for u in plan_units if u["family"] == "hyperx" and u["status"] == "ready_to_run"), key=lambda u: u["seller_sku"])
    assert {u["seller_sku"].upper() for u in units} == set(KNOWN_URLS), "ready HyperX rows and KNOWN_URLS differ"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    session = FixtureSession({url: (200, html) for url, html in saved_pages().items()})
    clock = lambda: 0.0  # noqa: E731
    log = out / "hyperx_fetch_log.json"
    factories = executor.RunFactories(
        session=session,
        hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=clock, fetch_log_path=log, policy=ProbePolicy(min_interval_seconds=0.0)),
        dns_adapter_factory=lambda: NoDealer(), fetch_log_paths=(log,),
    )
    checkpoint_path = out / "checkpoint.json"
    checkpoint = executor.run_units(units, workdir=out, checkpoint_path=checkpoint_path, factories=factories, clock=clock)
    calls_after_first = list(session.calls)
    executor.run_units(units, workdir=out, checkpoint_path=checkpoint_path, factories=factories, clock=clock)

    per_unit = []
    for entry in sorted(checkpoint["units"].values(), key=lambda e: e["seller_sku"]):
        card = entry.get("card", {})
        hyperx = next((s for s in card.get("sources", []) if s["source_key"] == "hyperx"), {})
        evidence = hyperx.get("evidence", "")
        per_unit.append({
            "seller_sku": entry["seller_sku"], "category": entry["category"], "outcome": entry["outcome"], "stop_code": entry.get("stop_code", ""),
            "job_status": entry.get("job_status", ""), "hyperx_match_level": hyperx.get("match_level", ""),
            "variant_source": next((part.split("=", 1)[1].split(" ")[0] for part in evidence.split("; ") if part.startswith("variant_source=")), ""),
            "url": hyperx.get("url", ""), "facts": card.get("facts"), "variant_attributes": len(card.get("attribute_scope", {}).get("variant", [])),
            "shared_model_attributes": len(card.get("attribute_scope", {}).get("model", [])), "photos": card.get("photos"), "photos_excluded": card.get("photos_excluded"), "photos_by_kind": card.get("photos_by_kind"),
            "documents": card.get("documents"), "gaps": card.get("gaps"), "conflicts": card.get("conflicts"), "conflict_names": card.get("conflict_names"),
        })
    before = {r["seller_sku"]: r for r in json.loads((STAGE18 / "controls/new_ready_summary.json").read_text(encoding="utf-8"))["per_unit"]}
    review_rows = []
    for sku in STAGE18_REVIEW:
        now = next(r for r in per_unit if r["seller_sku"] == sku)
        review_rows.append({"seller_sku": sku, "stage18_outcome": before[sku]["outcome"], "stage18_conflicts": before[sku]["conflicts"], "now_outcome": now["outcome"],
                            "now_stop_code": now["stop_code"], "now_conflict_names": now["conflict_names"]})
    summary = {
        "step": "offline replay of saved official pages through worker.run_once(); zero requests", "units": len(units), **executor.summarize(checkpoint),
        "resume_pass_new_calls": len(session.calls) - len(calls_after_first), "requests_to_fixture_transport": len(calls_after_first), "refused_requests": session.refused,
        "per_unit": per_unit, "stage18_review_rows": review_rows,
    }
    return summary, checkpoint_path


def main() -> None:
    (STAGE / "controls").mkdir(parents=True, exist_ok=True)
    summary, checkpoint_path = replay(STAGE / "controls" / "replay_workdir")
    (STAGE / "controls" / "all_ready_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy(checkpoint_path, STAGE / "controls" / "all_ready_checkpoint.json")
    shutil.rmtree(STAGE / "controls" / "replay_workdir")
    print({k: v for k, v in summary.items() if k not in {"per_unit", "stage18_review_rows"}})
    for r in summary["per_unit"]:
        print(f"  {r['seller_sku']:<8} {r['outcome']:<7} {r['stop_code']:<18} {r['variant_source']:<24} facts={r['facts']} var={r['variant_attributes']} model={r['shared_model_attributes']} photos={r['photos']}(+{r['photos_excluded']} excl) docs={r['documents']} conflicts={r['conflict_names']}")
    print("Stage 18 review rows:")
    for r in summary["stage18_review_rows"]:
        print(" ", r)


if __name__ == "__main__":
    with offline_only():
        main()
