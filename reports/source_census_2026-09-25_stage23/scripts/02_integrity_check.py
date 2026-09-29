"""Stage 23 step 2 -- integrity evidence, read-only (modelled on Stage 22 step 9).

  * the catalog is byte-identical to its recorded SHA-256 and was not modified;
  * the source registry (product_tool/config/source_catalog.v2.json) still matches its pin;
  * every report directory of Stage 2-16 still matches the per-file hashes Stage 17 recorded;
  * no file of the Stage 17 to 22 directories was modified after Stage 23 started (mtime);
  * every migration-pinned / frozen file matches its pin (Stage 22 changed worker.py, lg.py, normalization.py, resolution.py again, each with a
    documented migration entry and a new pin; sulpak.py, supplier.py, common.py stay byte-identical to the frozen baseline);
  * no active file names the excluded dealer (word-window SHA-256 scan);
  * data/batches.sqlite3 (the user's local database) was not modified and data/lg_fetch_log.json (written by the Stage 21 and 22 probes) records no stopped host.

Writes reports/source_census_2026-09-25_stage23/protected_hashes_check.json."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import _pipeline_migration as mig  # noqa: E402
import test_coverage_queue as tcq  # noqa: E402

STAGE = ROOT / "reports/source_census_2026-09-25_stage23"
EARLIER = [ROOT / f"reports/source_census_2026-09-24_stage{n}" for n in (17, 18, 19, 20, 21, 22)]
CATALOG = ROOT / "data/catalog_2026-09-21_filtered.xlsx"
CATALOG_SHA256 = "99789238cde44dd2a5ec776f504944d9d91ab5698770cff8126f353212e107ba"
REGISTRY = "product_tool/config/source_catalog.v2.json"
FROZEN = json.loads((ROOT / "reports/source_census_2026-09-22_stage8/protected_hashes_after.json").read_text(encoding="utf-8"))["after"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


started = min(p.stat().st_mtime for p in STAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
recorded17 = json.loads((EARLIER[0] / "protected_hashes_check.json").read_text(encoding="utf-8"))["prior_report_hashes"]
changed_vs_stage17 = sorted(path for directory, files in recorded17.items() for path, digest in files.items() if not (ROOT / path).is_file() or sha(ROOT / path) != digest)
earlier_files = [p for directory in EARLIER for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
modified_after_start = sorted(p.relative_to(ROOT).as_posix() for p in earlier_files if p.stat().st_mtime > started)
pins = {path: {"ok": mig.check_migrated_file(path, sha(ROOT / path))[0]} for path in mig.ALL_AUTHORIZED_CHANGES}
lg_files = ["product_tool/adapters/sulpak.py", "product_tool/adapters/supplier.py", "product_tool/adapters/common.py"]
lg_frozen = {path: sha(ROOT / path) == FROZEN[path] for path in lg_files}

offenders = set()
lengths = set(tcq._NAME_HASHES.values())
suffixes = {".py", ".json", ".md", ".html", ".js", ".txt", ".toml", ".cfg"}
active = [ROOT / "README.md"] + [p for top in ("product_tool", "tests", "docs") for p in (ROOT / top).rglob("*") if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts]
for path in active:
    for token in set(re.findall(r"[A-Za-zА-Яа-яЁё]{5,}", path.read_text(encoding="utf-8", errors="ignore"))):
        lowered = token.casefold()
        for n in lengths:
            if any(hashlib.sha256(lowered[i:i + n].encode()).hexdigest() in tcq._NAME_HASHES for i in range(len(lowered) - n + 1)):
                offenders.add(path.relative_to(ROOT).as_posix())

from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log  # noqa: E402

stopped_hosts = sorted(stopped_hosts_from_fetch_log(e for e in json.loads((ROOT / "data/lg_fetch_log.json").read_text(encoding="utf-8")) if isinstance(e, dict))) if (ROOT / "data/lg_fetch_log.json").exists() else []
database = ROOT / "data/batches.sqlite3"
result = {
    "stage23_started_at_mtime": started, "catalog_sha256": sha(CATALOG), "catalog_unchanged": sha(CATALOG) == CATALOG_SHA256, "catalog_modified_after_stage23_started": CATALOG.stat().st_mtime > started,
    "source_registry_matches_pin": pins[REGISTRY]["ok"] if REGISTRY in pins else None,
    "earlier_report_files_checked_against_stage17_record": sum(len(v) for v in recorded17.values()), "earlier_report_files_changed_vs_stage17_record": changed_vs_stage17,
    "stage17_to_22_files": len(earlier_files), "stage17_to_22_files_modified_after_stage23_started": modified_after_start,
    "pinned_files": pins, "pinned_all_ok": all(v["ok"] for v in pins.values()), "frozen_adapters_identical_to_baseline": lg_frozen,
    "active_files_scanned_for_excluded_dealer": len(active), "active_files_naming_it": sorted(offenders),
    "local_database_modified_after_stage23_started": database.stat().st_mtime > started, "lg_fetch_log_stopped_hosts": stopped_hosts, "lg_adapter_migrated_pin_ok": pins["product_tool/adapters/lg.py"]["ok"],
}
(STAGE / "protected_hashes_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "pinned_files"}, ensure_ascii=False, indent=1))
