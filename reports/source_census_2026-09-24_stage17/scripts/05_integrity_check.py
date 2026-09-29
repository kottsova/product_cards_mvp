"""Stage 17 -- integrity evidence, read-only.

  * the catalog is byte-identical to its recorded SHA-256;
  * every earlier reports/ directory (Stage 2 - 16) is hashed (compare with the
    previous run of this script, or with git, to prove nothing changed);
  * every migration-pinned file still matches its pin (tests/_pipeline_migration.py);
  * no active file names the excluded dealer (word-window SHA-256 scan, the
    name itself is never written down);
  * the one authorised deletion is still absent (checked by path hash).

Writes reports/source_census_2026-09-24_stage17/protected_hashes_check.json."""
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

STAGE_DIR = ROOT / "reports/source_census_2026-09-24_stage17"
OUT = STAGE_DIR / "protected_hashes_check.json"
CATALOG = ROOT / "data/catalog_2026-09-21_filtered.xlsx"
CATALOG_SHA256 = "99789238cde44dd2a5ec776f504944d9d91ab5698770cff8126f353212e107ba"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


prior = {}
for directory in sorted((ROOT / "reports").iterdir()):
    if directory.is_dir() and directory.name != "source_census_2026-09-24_stage17":
        files = sorted(p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        prior[directory.name] = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}

# Compare with the per-file hashes Stage 13 recorded for every directory through Stage 12 (the last stage that stored per-file hashes), and
# look for any earlier file modified after this stage began (its first script).
recorded = json.loads((ROOT / "reports/source_census_2026-09-23_stage13/protected_hashes_check.json").read_text(encoding="utf-8"))["prior_stage_hashes"]
changed_vs_stage13_record = sorted(path for directory, files in recorded.items() for path, digest in files.items()
                            if not (ROOT / path).is_file() or sha(ROOT / path) != digest)
started = (STAGE_DIR / "scripts/01_repin_migration_hashes.py").stat().st_mtime
modified_after_start = sorted(
    path for directory, files in prior.items() for path in files if (ROOT / path).stat().st_mtime > started
)

pins = {}
for path in mig.ALL_AUTHORIZED_CHANGES:
    ok, message = mig.check_migrated_file(path, sha(ROOT / path))
    pins[path] = {"ok": ok}

deleted_still_absent = all(
    not mig.is_deleted_file_path(p.relative_to(ROOT).as_posix())
    for p in ROOT.rglob("*") if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts and "__pycache__" not in p.parts
)

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

result = {
    "catalog_sha256": sha(CATALOG), "catalog_unchanged": sha(CATALOG) == CATALOG_SHA256,
    "prior_report_directories": len(prior), "prior_report_files": sum(len(v) for v in prior.values()),
    "prior_report_hashes": prior,
    "stage2_to_12_files_changed_vs_stage13_record": changed_vs_stage13_record,
    "prior_report_files_modified_after_stage17_started": modified_after_start,
    "pinned_files": pins, "pinned_all_ok": all(v["ok"] for v in pins.values()),
    "authorised_deletion_still_absent": deleted_still_absent,
    "active_files_scanned_for_excluded_dealer": len(active), "active_files_naming_it": sorted(offenders),
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print({k: v for k, v in result.items() if k != "prior_report_hashes"})
