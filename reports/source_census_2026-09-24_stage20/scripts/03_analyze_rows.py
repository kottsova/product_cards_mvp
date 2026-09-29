"""Stage 20 step 3 -- OFFLINE, zero requests. Per-row analysis of the pilot from its own database and saved responses,
using the readiness rule and failure taxonomy fixed in raw/predeclaration.json BEFORE the run.

Output: raw/pilot_analysis.json
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent

OFFICIAL = ("lg_kz", "lg_ru")


def failure_codes(row: dict) -> list[str]:
    codes = []
    kz, ru, sp = row["sources"].get("lg_kz", {}), row["sources"].get("lg_ru", {}), row["sources"].get("sulpak", {})
    kz_error, ru_error = kz.get("error", ""), ru.get("error", "")
    if "policy_host_stopped" in kz_error + ru_error or "policy_host_stopped" in sp.get("error", ""):
        codes.append("host_stopped")
    if "policy_budget_exhausted" in kz_error + ru_error + sp.get("error", ""):
        codes.append("budget_exhausted")
    if kz_error and "sitemap" in kz_error.lower():
        codes.append("kz_sitemap_error")
    elif kz.get("match_level") == "mismatch" and "sitemap" in kz.get("evidence", ""):
        codes.append("kz_no_slug_in_sitemap")
    elif "не вернул ожидаемую карточку" in kz_error:
        codes.append("kz_page_unrecognised")
    elif kz.get("match_level") == "base_model":
        codes.append("kz_base_model_only")
    elif kz_error:
        codes.append("kz_page_error")
    if ru_error and "HTTP" in ru_error:
        codes.append("ru_no_page")
    elif "не вернул ожидаемую карточку" in ru_error:
        codes.append("ru_page_unrecognised")
    elif ru.get("match_level") == "base_model":
        codes.append("ru_base_model_only")
    docs_events = [e["message"] for e in row["events"] if e.get("stage") == 6 and ("Инструкции" in e["message"] or "инструкций" in e["message"] or "поддержки" in e["message"])]
    if any("страница LG Россия недоступна" in m for m in docs_events):
        codes.append("documents_not_checked")
    elif any("связь с моделью поддержки не найдена" in m for m in docs_events):
        codes.append("documents_no_support_link")
    elif not row["documents"] and ru.get("match_level") in ("full_sku", "base_model"):
        codes.append("documents_none_ru")
    if "нет ограниченного кандидата" in sp.get("evidence", ""):
        codes.append("supplier_no_candidate")
    if row["job"]["status"] != "done" and not any(s.get("match_level") == "full_sku" for k, s in row["sources"].items() if k == "sulpak"):
        codes.append("no_supplier_confirmation_so_not_done")
    return codes


def readiness(row: dict) -> dict:
    official = {k: v for k, v in row["sources"].items() if k in OFFICIAL}
    exact = [k for k, v in official.items() if v["match_level"] == "full_sku" and not v["error"]]
    facts = sum(v["facts"] for v in official.values())
    gallery = sum(v["photos_selected"] for v in official.values())
    russian_docs = [d for d in row["documents"] if d["language"] == "Русский"]
    gaps = []
    if not row["documents"]:
        gaps.append("instruction")
    elif not russian_docs:
        gaps.append("instruction_language_not_russian")
    if not any(s.get("match_level") == "full_sku" for k, s in row["sources"].items() if k == "sulpak"):
        gaps.append("supplier_confirmation")
    if row["job"]["status"] != "done":
        gaps.append(f"job_{row['job']['status']}")
    if row["resolved"]["conflicts"]:
        gaps.append(f"unresolved_conflicts_{row['resolved']['conflicts']}")
    if exact and facts and gallery:
        verdict = "export_ready" if not gaps else "export_ready_with_gaps"
    else:
        verdict = "not_ready"
        gaps = [g for g in gaps] + [x for x, ok in (("no_official_full_sku_page", bool(exact)), ("no_official_specifications", bool(facts)), ("no_official_gallery_photo", bool(gallery))) if not ok]
    return {"verdict": verdict, "gaps": gaps, "official_exact_regions": exact, "official_facts": facts, "official_gallery_selected": gallery}


def main() -> None:
    data = json.loads((STAGE / "raw/pilot_rows.json").read_text(encoding="utf-8"))
    requests = json.loads((STAGE / "raw/pilot_requests.json").read_text(encoding="utf-8"))
    rows = []
    for row in data["rows"]:
        kz, ru, sp, dns = (row["sources"].get(k, {}) for k in ("lg_kz", "lg_ru", "sulpak", "dns"))
        ready = readiness(row)
        rows.append({
            "seller_sku": row["seller_sku"], "category": row["category"], "title": row["title"], "requests": row["requests_in_row"], "seconds": row["seconds"],
            "official_exact_page": {"found": bool(ready["official_exact_regions"]), "regions": ready["official_exact_regions"], "kz_level": kz.get("match_level"), "kz_url": kz.get("url"), "ru_level": ru.get("match_level"), "ru_error": ru.get("error")},
            "variant_confirmed": kz.get("match_level") == "full_sku" or ru.get("match_level") == "full_sku",
            "facts": {"lg_kz": kz.get("facts", 0), "lg_ru": ru.get("facts", 0), "sulpak": sp.get("facts", 0), "dns": dns.get("facts", 0)},
            "resolved": row["resolved"],
            "photos": {"gallery_selected": kz.get("photos_selected", 0), "kinds_kz": kz.get("photos", {})},
            "instruction": {"found": len(row["documents"]), "languages": sorted({d["language"] for d in row["documents"]}), "language_basis": "label 'Русский' set by the adapter from a document row of the LG support page" if row["documents"] else ""},
            "dealer_added": {"sulpak": {"match_level": sp.get("match_level"), "facts": sp.get("facts", 0), "photos": sp.get("photos", {})}, "dns": {"match_level": dns.get("match_level"), "facts": dns.get("facts", 0)},
                             "nothing_added": not (sp.get("facts") or sp.get("photos") or dns.get("facts"))},
            "job": row["job"], "readiness": ready, "failure_codes": failure_codes(row),
        })
    codes = Counter(c for r in rows for c in r["failure_codes"])
    verdicts = Counter(r["readiness"]["verdict"] for r in rows)
    out = {
        "rows": rows, "totals": {
            "rows_run": len(rows), "requests_total": requests["requests_total"], "max_requests_in_one_row": requests["max_requests_in_one_row"], "host_blocked": bool(requests["stopped_hosts"]),
            "official_exact_page_found": sum(1 for r in rows if r["official_exact_page"]["found"]), "variant_confirmed": sum(1 for r in rows if r["variant_confirmed"]),
            "with_specifications": sum(1 for r in rows if r["facts"]["lg_kz"] + r["facts"]["lg_ru"]), "with_gallery_photos": sum(1 for r in rows if r["photos"]["gallery_selected"]),
            "instruction_found": sum(1 for r in rows if r["instruction"]["found"]), "dealer_added_anything": sum(1 for r in rows if not r["dealer_added"]["nothing_added"]),
            "job_status": dict(Counter(r["job"]["status"] for r in rows)), "readiness": dict(verdicts), "rows_with_unresolved_conflicts": sum(1 for r in rows if r["resolved"]["conflicts"]),
            "failure_codes": dict(sorted(codes.items(), key=lambda kv: (-kv[1], kv[0]))),
        },
    }
    (STAGE / "raw/pilot_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["totals"], ensure_ascii=False, indent=1))
    for r in rows:
        print(f"  {r['seller_sku']:<15} exact={r['official_exact_page']['found']!s:<5} facts={r['facts']['lg_kz']:<3} gallery={r['photos']['gallery_selected']:<3} docs={r['instruction']['found']} job={r['job']['status']:<12} {r['readiness']['verdict']:<22} {r['failure_codes']}")


if __name__ == "__main__":
    main()
