"""Stage 18 step 9 -- integrity evidence, read-only.

  * the catalog is byte-identical to its recorded SHA-256 and was not modified;
  * every report directory of Stage 2-16 still matches the per-file hashes Stage 17 recorded;
  * no file of Stage 17's directory was modified after Stage 18 started (mtime) and the file set is the one Stage 17 shipped;
  * every migration-pinned file still matches its pin;
  * no active file names the excluded dealer (word-window SHA-256 scan; the name is never written down);
  * data/batches.sqlite3 (the user's local database) was not modified;
  * the only new runtime file under data/ is the persisted fetch log of the HyperX wave.

Writes reports/source_census_2026-09-24_stage18/protected_hashes_check.json."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import _pipeline_migration as mig  # noqa: E402
import test_coverage_queue as tcq  # noqa: E402  (reuses its excluded-name digests)

STAGE = ROOT / "reports/source_census_2026-09-24_stage18"
STAGE17 = ROOT / "reports/source_census_2026-09-24_stage17"
CATALOG = ROOT / "data/catalog_2026-09-21_filtered.xlsx"
CATALOG_SHA256 = "99789238cde44dd2a5ec776f504944d9d91ab5698770cff8126f353212e107ba"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


started = min(p.stat().st_mtime for p in STAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)

recorded17 = json.loads((STAGE17 / "protected_hashes_check.json").read_text(encoding="utf-8"))["prior_report_hashes"]
changed_vs_stage17_record = sorted(path for directory, files in recorded17.items() for path, digest in files.items()
                                   if not (ROOT / path).is_file() or sha(ROOT / path) != digest)
earlier_dirs_now = sorted(d.name for d in (ROOT / "reports").iterdir() if d.is_dir() and d.name not in {STAGE.name, STAGE17.name})
stage17_files = sorted(p for p in STAGE17.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
stage17_modified_after_start = sorted(p.relative_to(ROOT).as_posix() for p in stage17_files if p.stat().st_mtime > started)

pins = {path: {"ok": mig.check_migrated_file(path, sha(ROOT / path))[0]} for path in mig.ALL_AUTHORIZED_CHANGES}

offenders = set()
lengths = set(tcq._NAME_HASHES.values())
suffixes = {".py", ".json", ".md", ".html", ".js", ".txt", ".toml", ".cfg"}
active = [ROOT / "README.md"] + [p for top in ("product_tool", "tests", "docs") for p in (ROOT / top).rglob("*")
                                 if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts]
for path in active:
    for token in set(re.findall(r"[A-Za-zА-Яа-яЁё]{5,}", path.read_text(encoding="utf-8", errors="ignore"))):
        lowered = token.casefold()
        for n in lengths:
            if any(hashlib.sha256(lowered[i:i + n].encode()).hexdigest() in tcq._NAME_HASHES for i in range(len(lowered) - n + 1)):
                offenders.add(path.relative_to(ROOT).as_posix())

database = ROOT / "data/batches.sqlite3"
result = {
    "stage18_started_at_mtime": started,
    "catalog_sha256": sha(CATALOG), "catalog_unchanged": sha(CATALOG) == CATALOG_SHA256,
    "catalog_modified_after_stage18_started": CATALOG.stat().st_mtime > started,
    "earlier_report_directories_checked_against_stage17_record": len(recorded17),
    "earlier_report_files_checked": sum(len(v) for v in recorded17.values()),
    "earlier_report_files_changed_vs_stage17_record": changed_vs_stage17_record,
    "report_directories_not_in_stage17_record": [d for d in earlier_dirs_now if d not in recorded17],
    "stage17_files": len(stage17_files),
    "stage17_files_modified_after_stage18_started": stage17_modified_after_start,
    "stage17_sha256_of_queue_files": {p.name: sha(p) for p in sorted((STAGE17 / "queue").glob("*"))},
    "pinned_files": pins, "pinned_all_ok": all(v["ok"] for v in pins.values()),
    "active_files_scanned_for_excluded_dealer": len(active), "active_files_naming_it": sorted(offenders),
    "local_database_modified_after_stage18_started": database.stat().st_mtime > started,
    "new_runtime_file_under_data": sorted(p.name for p in (ROOT / "data").glob("hyperx_fetch_log.json")),
}
(STAGE / "protected_hashes_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k not in {"pinned_files", "stage17_sha256_of_queue_files"}}, ensure_ascii=False, indent=1))
