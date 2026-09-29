"""Offline planner: classify every unique catalog product, roll the result up
to brand-category pairs, priority brands, request groups and adapter waves.

Deterministic by construction: no clock, no network, sorted output. Running
it twice on the same catalog, config and repository state gives identical
bytes (see `plan_bytes`).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..census.catalog import category_group
from .catalog_units import CatalogSnapshot, CatalogUnit, load_catalog, reconcile
from .classify import (
    HOST_BLOCKED, IDENTITY_CONFLICT, MANUAL, NEEDS_FIXTURE, READY, ROUTE_NO_ADAPTER, URL_MISSING,
    ClassifierContext, Classification, classify,
)
from .facts import (
    PLANNER_CONFIG, ROOT, build_family_facts, load_brand_registry, load_config, load_profiles,
    recorded_blocked_hosts, selected_products, supplementary_routes, working_routes,
)

PLAN_VERSION = "18.0.0"
DEFAULT_CATALOG = "data/catalog_2026-09-21_filtered.xlsx"
WORKED_IN_WAVE = (ROUTE_NO_ADAPTER, NEEDS_FIXTURE)  # units a first-wave family still has to bring to run_once()


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


# ------------------------------------------------------------------ units


def classify_units(snapshot: CatalogSnapshot, config: dict, root: Path, extra_fetch_logs=()):
    routes = working_routes()
    blocked = recorded_blocked_hosts(config, root, extra_fetch_logs)
    facts = build_family_facts(config, load_profiles(), blocked)
    context = ClassifierContext.build(
        snapshot.units, brands=load_brand_registry(), facts=facts, routes=routes,
        supplementary=supplementary_routes(), blocked_hosts=blocked, product_facts=config["product_facts"],
        product_flags=config.get("product_flags", []),
        url_findings={family: block["rows"] for family, block in config.get("url_findings", {}).items()},
        selected=selected_products(config),
    )
    return [(unit, classify(unit, context)) for unit in snapshot.units], facts, blocked


def unit_record(unit: CatalogUnit, result: Classification) -> dict:
    return {
        "unit_id": unit.unit_id, "catalog_row": unit.row_number, "brand": unit.brand, "category": unit.category,
        "category_group": category_group(unit.category), "seller_sku": unit.seller_sku, "title": unit.title,
        "source_rows": unit.source_rows, "status": result.status, "reason": result.reason,
        "next_action": result.next_action, "family": result.family, "route_id": result.route_id,
        "url_basis": result.url_basis, "exact_url": result.exact_url, "hosts": list(result.hosts),
        "flags": list(result.flags), "dealer_exact_urls": [list(item) for item in result.dealer_exact_urls],
        "detail": result.detail, "sku_risk": result.sku_risk, "scope_id": result.scope_id,
        "url_finding": result.url_finding,
    }


# ------------------------------------------------------------------ pairs


def build_pairs(records: list[dict], tiebreak: list[str]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        grouped[(record["brand"], record["category"])].append(record)
    order = {status: index for index, status in enumerate(tiebreak)}
    pairs = []
    for (brand, category), items in sorted(grouped.items(), key=lambda kv: (kv[0][0].casefold(), kv[0][1])):
        counts = Counter(item["status"] for item in items)
        total = len(items)
        ready = counts.get(READY, 0)
        if ready == total:
            status = READY
        else:
            rest = {s: n for s, n in counts.items() if s != READY}
            status = sorted(rest, key=lambda s: (-rest[s], order[s]))[0]
        pairs.append({
            "brand": brand, "category": category, "category_group": category_group(category),
            "families": sorted({item["family"] for item in items if item["family"]}),
            "unique_products": total, "source_rows": sum(item["source_rows"] for item in items),
            "status": status, "ready_units": ready, "partially_ready": 0 < ready < total,
            "unit_status_counts": dict(sorted(counts.items())),
            "reasons": dict(sorted(Counter(item["reason"] for item in items).items())),
        })
    return pairs


# ---------------------------------------------------------- request groups

_ASK_TEXT = {
    URL_MISSING: "Один запрос по {brand} на {hosts}: для {units} тов. ({categories} категорий) адаптер есть, но точного официального URL нет и угадывать его он не будет. Ниже по каждому товару, что уже выяснено и что нужно.",
    NEEDS_FIXTURE: "Нужен сохранённый fixture страницы товара ({brand}, {category_group}, {hosts}): {units} тов. ждут, пока адаптеру будет на чём строить identity/характеристики/фото. Причина: {reason}.",
    ROUTE_NO_ADAPTER: "Официальный маршрут ({hosts}) подтверждён, адаптера нет: {units} тов. ({brand}, {category_group}) ждут реализации адаптера.",
    HOST_BLOCKED: "Host {hosts} остановлен после блокировки (причина: {reason}): {units} тов. ({brand}, {category_group}) не запускаются, пока человек не примет решение.",
    IDENTITY_CONFLICT: "Нужно решение по identity ({reason}): {units} тов. ({brand}, {category_group}).",
    MANUAL: "Нужна ручная проверка ({reason}): {units} тов. ({brand}, {category_group}).",
}
_KIND = {URL_MISSING: "ask_user", NEEDS_FIXTURE: "capture_fixture", ROUTE_NO_ADAPTER: "dev_task", HOST_BLOCKED: "human_decision", IDENTITY_CONFLICT: "human_decision", MANUAL: "human_decision"}


def build_request_groups(records: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """One group per (status, reason, family-or-brand, category group, host)."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for record in records:
        if record["status"] == READY:
            continue
        host = record["hosts"][0] if record["hosts"] else ""
        subject = record["family"] or record["brand"].casefold() or "(no brand)"
        # One question per brand and host for missing URLs, however many categories it spans.
        cgroup = "*" if record["status"] == URL_MISSING else record["category_group"]
        buckets[(record["status"], record["reason"], subject, cgroup, host)].append(record)
    groups, assignment = [], {}
    for key in sorted(buckets):
        status, reason, subject, cgroup, host = key
        items = buckets[key]
        group_id = "G" + hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:10]
        brands = sorted({item["brand"] for item in items if item["brand"]}) or ["(бренд не указан)"]
        groups.append({
            "group_id": group_id, "kind": _KIND[status], "status": status, "reason": reason, "subject": subject,
            "brand_labels": brands, "category_group": cgroup, "host": host, "units": len(items),
            "pairs": len({(item["brand"], item["category"]) for item in items}),
            "categories": sorted({item["category"] for item in items}),
            "sample_seller_skus": sorted(item["seller_sku"] for item in items)[:5],
            "message_ru": _ASK_TEXT[status].format(
                hosts=host or "официальном host", units=len(items), brand=", ".join(brands[:3]) + ("…" if len(brands) > 3 else ""),
                category_group=cgroup, reason=reason, categories=len({item["category"] for item in items})),
        })
        if status == URL_MISSING:
            groups[-1]["findings_by_outcome"] = dict(sorted(Counter(item["url_finding"] or "not_examined" for item in items).items()))
            groups[-1]["items"] = [
                {"seller_sku": item["seller_sku"], "category": item["category"], "title": item["title"], "finding": item["url_finding"] or "not_examined", "detail": item["detail"]}
                for item in sorted(items, key=lambda i: (i["category"], i["seller_sku"]))
            ]
        for item in items:
            assignment[item["unit_id"]] = group_id
    return groups, assignment


# ----------------------------------------------------------- priority queue


def build_priority_queue(config: dict, records: list[dict], facts, wave_of_family: dict[str, str]) -> list[dict]:
    by_family: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record["family"]:
            by_family[record["family"]].append(record)
    rows = []
    for position, family in enumerate(config["priority_brands"]["families"], start=1):
        items = by_family.get(family, [])
        counts = Counter(item["status"] for item in items)
        fact = facts.get(family)
        if not items:
            note = "No catalog unit routes to this family (Xbox products are catalogued under Microsoft)."
            dominant = ""
        else:
            note = ""
            dominant = sorted(counts, key=lambda s: (-counts[s], s))[0]
        rows.append({
            "user_order": position, "family": family, "unique_products": len(items),
            "pairs": len({(item["brand"], item["category"]) for item in items}),
            "unit_status_counts": dict(sorted(counts.items())), "dominant_status": dominant,
            "ready_units": counts.get(READY, 0), "template_group": fact.template_group if fact else "",
            "fixture_level": fact.fixture_level if fact else "none", "discovery_status": fact.discovery_status if fact else "none",
            "host_blocked": bool(fact and fact.host_blocked), "wave_id": wave_of_family.get(family, ""), "note": note,
        })
    # Recommended order: unblocked before blocked, work that changes status first
    # (largest addressable share), already-served brands last.
    def gain(row):
        return row["unit_status_counts"].get(ROUTE_NO_ADAPTER, 0) + row["unit_status_counts"].get(NEEDS_FIXTURE, 0) + row["unit_status_counts"].get(URL_MISSING, 0)
    for rank, row in enumerate(sorted(rows, key=lambda r: (r["host_blocked"], -gain(r), r["user_order"])), start=1):
        row["recommended_rank"] = rank
    return rows


# -------------------------------------------------------------------- waves


def build_waves(config: dict, records: list[dict], facts, total_units: int) -> list[dict]:
    """Gain is counted per proven scope: only units whose own category, host and
    market are covered by a complete Product page fixture (official_route_no_adapter)
    move when the adapter lands. Units waiting for a fixture are listed apart and
    never counted as adapter gain."""
    by_family: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record["family"]:
            by_family[record["family"]].append(record)
    confirmed = {(item["brand_family"], item["seller_sku"].casefold()): item for item in config["confirmed_exact_urls"]["counted"]}
    waves = []
    for group in config["template_groups"]:
        wave_families = [f for f in group["first_wave_families"] if f in by_family]
        ready_scope = [r for f in wave_families for r in by_family[f] if r["status"] == ROUTE_NO_ADAPTER]
        waiting = [r for f in wave_families for r in by_family[f] if r["status"] == NEEDS_FIXTURE]
        per_family = []
        via_discovery = guaranteed = 0
        for family in wave_families:
            fact = facts[family]
            items = by_family[family]
            ready = [r for r in items if r["status"] == ROUTE_NO_ADAPTER]
            waits = [r for r in items if r["status"] == NEEDS_FIXTURE]
            scope_rows = []
            for scope in fact.scopes:
                in_scope = [r for r in items if r["scope_id"] == scope.scope_id]
                is_ready = scope.market_matches_catalog and scope.level in ("full_value", "structural_sufficient")
                known = [r for r in in_scope if r["status"] == ROUTE_NO_ADAPTER and (family, r["seller_sku"].casefold()) in confirmed]
                discovered = len(in_scope) if is_ready and scope.discovery_status == "confirmed" else 0
                via_discovery += discovered
                guaranteed += len(known)
                scope_rows.append({
                    "scope_id": scope.scope_id, "label": scope.label, "categories": list(scope.categories), "hosts": list(scope.hosts),
                    "market": scope.market, "market_matches_catalog": scope.market_matches_catalog, "fixture_level": scope.level,
                    "missing_layers": list(scope.missing_layers), "discovery_status": scope.discovery_status, "discovery_route": scope.discovery_route,
                    "units": len(in_scope), "unit_status_counts": dict(sorted(Counter(r["status"] for r in in_scope).items())),
                    "after_adapter": (READY if scope.discovery_status == "confirmed" else URL_MISSING) if is_ready else "still_" + NEEDS_FIXTURE,
                    "next_step": "build_adapter" if is_ready else _scope_next_step(scope),
                    "confirmed_exact_urls_on_record": [{"seller_sku": r["seller_sku"], "url": confirmed[(family, r["seller_sku"].casefold())]["url"]} for r in known],
                    "caveat": scope.caveat,
                })
            uncovered = [r for r in waits if not r["scope_id"]]
            per_family.append({
                "family": family, "current_unit_status_counts": dict(sorted(Counter(r["status"] for r in items).items())),
                "adapter_ready_units": len(ready), "adapter_ready_pairs": len({(r["brand"], r["category"]) for r in ready}),
                "waiting_on_fixture_units": len(waits), "waiting_on_fixture_reasons": dict(sorted(Counter(r["reason"] for r in waits).items())),
                "scopes": scope_rows,
                "categories_without_evidence": dict(sorted(Counter(r["category"] for r in uncovered).items(), key=lambda kv: (-kv[1], kv[0]))),
                "hosts": list(fact.hosts), "prerequisites": _prerequisites(fact, waits),
            })
        units = len(ready_scope)
        gain = {
            "adapter_ready_units": units, "adapter_ready_pairs": len({(r["brand"], r["category"]) for r in ready_scope}),
            "adapter_ready_pct": _pct(units, total_units),
            "ready_guaranteed_by_urls_on_record_units": guaranteed,
            "ready_via_confirmed_discovery_route_units": via_discovery, "ready_via_confirmed_discovery_route_pct": _pct(via_discovery, total_units),
            "ready_if_every_exact_url_is_supplied_units": units,
            "waiting_on_fixture_units": len(waiting), "waiting_on_fixture_pairs": len({(r["brand"], r["category"]) for r in waiting}),
            "reading": ("adapter_ready_units are the only units the adapter can serve on evidence that covers their own category, host and market; "
                        "they move out of official_route_no_adapter. They become ready_to_run only where an exact URL is on record (guaranteed) or the "
                        "scope's own discovery route is confirmed (upper bound); otherwise they wait as adapter_url_missing. waiting_on_fixture_units "
                        "need a Product page fixture first and are not adapter gain. Nothing counts as ready before a positive fixture passes the criteria."),
        }
        waves.append({
            "wave_id": f"W1-{group['group_id']}", "group_id": group["group_id"], "group_title": group["title"],
            "template_source": group["source"], "families": wave_families, "later_wave_families": [f for f in group["families"] if f not in wave_families],
            "shared_primitives": group["shared_primitives"], "stays_separate": group["stays_separate"],
            "expected_gain": gain, "per_family": per_family,
            "readiness_criteria": _criteria(config, per_family),
            "measure_with": "python -m product_tool.coverage delta --before <coverage_units.jsonl before> --after <coverage_units.jsonl after>",
        })
    return waves


def _scope_next_step(scope) -> str:
    if not scope.market_matches_catalog:
        return "capture_fixture_in_catalog_market_or_decide_market_equivalence"
    return "capture_fixture_with_" + "_and_".join(scope.missing_layers)


def _prerequisites(fact, waits: list[dict]) -> list[str]:
    needs = []
    if fact.scopes:
        for scope in fact.scopes:
            if scope.market_matches_catalog and not scope.missing_layers:
                continue
            needs.append(f"{scope.scope_id}: " + ("a Product page fixture in the catalog's market (" + scope.market + " is not it)" if not scope.market_matches_catalog
                                                  else "a Product page fixture with " + ", ".join(scope.missing_layers)) + ".")
        if any(r["reason"] == "no_product_page_evidence_for_category" for r in waits):
            needs.append("A Product page fixture for each catalog category without one (categories_without_evidence).")
    elif fact.fixture_level in ("none", "structural_partial"):
        missing = ", ".join(fact.fixture_missing_layers) if fact.fixture_missing_layers else "identity, specifications, media"
        needs.append(f"Product page fixture(s) covering: {missing}.")
    needs.append("A negative variant fixture (wrong region/colour/suffix) per category in scope.")
    if fact.discovery_status not in ("confirmed", "category_scoped") or any(s.discovery_status != "confirmed" for s in fact.scopes):
        needs.append("An exact product URL per row from a human, or a confirmed discovery route for that category; URLs are never guessed.")
    if fact.host_blocked:
        needs.append("A human decision to clear the blocked host.")
    return needs


def _criteria(config: dict, per_family: list[dict]) -> list[dict]:
    scope_text = "; ".join(f"{item['family']}: {item['adapter_ready_units']} adapter-ready units in {sum(1 for s in item['scopes'] if s['next_step'] == 'build_adapter')} scope(s), {item['waiting_on_fixture_units']} waiting on a fixture" for item in per_family)
    return [{"id": item["id"], "text": item["text"], "scope": scope_text} for item in config["wave_readiness_criteria"]]


# ---------------------------------------------------------------- the plan


def build_plan(catalog_path: str | Path = DEFAULT_CATALOG, *, root: Path = ROOT, config_path: Path = PLANNER_CONFIG, extra_fetch_logs=()) -> dict:
    catalog_file = Path(catalog_path)
    if not catalog_file.is_absolute():
        catalog_file = root / catalog_file
    config = load_config(config_path)
    snapshot = load_catalog(catalog_file)
    reconciliation = reconcile(snapshot)
    classified, facts, blocked = classify_units(snapshot, config, root, extra_fetch_logs)
    records = [unit_record(unit, result) for unit, result in classified]
    groups, assignment = build_request_groups(records)
    wave_of_family: dict[str, str] = {}
    waves = build_waves(config, records, facts, len(records))
    for wave in waves:
        for family in wave["families"]:
            wave_of_family[family] = wave["wave_id"]
    for record in records:
        record["request_group_id"] = assignment.get(record["unit_id"], "")
        record["wave_id"] = wave_of_family.get(record["family"], "") if record["status"] in WORKED_IN_WAVE else ""
    pairs = build_pairs(records, config["pair_tiebreak_order"])
    total = len(records)
    unit_counts = Counter(record["status"] for record in records)
    pair_counts = Counter(pair["status"] for pair in pairs)
    ready_units = unit_counts.get(READY, 0)
    by_basis = Counter(record["url_basis"] for record in records if record["status"] == READY)
    summary = {
        "unique_products": total, "source_rows": sum(r["source_rows"] for r in records), "brand_category_pairs": len(pairs),
        "units_by_status": {s["id"]: unit_counts.get(s["id"], 0) for s in config["statuses"]},
        "units_by_status_pct": {s["id"]: _pct(unit_counts.get(s["id"], 0), total) for s in config["statuses"]},
        "pairs_by_status": {s["id"]: pair_counts.get(s["id"], 0) for s in config["statuses"]},
        "pairs_fully_ready": sum(1 for p in pairs if p["status"] == READY),
        "pairs_partially_ready": sum(1 for p in pairs if p["partially_ready"]),
        "ready_units_by_url_basis": dict(sorted(by_basis.items())),
        "ready_units_pct": _pct(ready_units, total),
        "reasons": {status: dict(sorted(Counter(r["reason"] for r in records if r["status"] == status).items(), key=lambda kv: (-kv[1], kv[0])))
                    for status in (s["id"] for s in config["statuses"])},
        "flags": dict(sorted(Counter(f for r in records for f in r["flags"]).items())),
        "units_by_scope": dict(sorted(Counter(r["scope_id"] for r in records if r["scope_id"]).items())),
        "units_with_shared_seller_sku_risk": sum(1 for r in records if r["sku_risk"]),
        "units_with_dealer_exact_url": sum(1 for r in records if r["dealer_exact_urls"]),
        "request_groups": len(groups),
        "units_needing_a_request_group": sum(1 for r in records if r["request_group_id"]),
    }
    meta = {
        "plan_version": PLAN_VERSION,
        "catalog": {"path": Path(catalog_path).as_posix(), "sha256": snapshot.sha256, "read_only": True},
        "reconciliation": reconciliation,
        "inputs_sha256": {
            "product_tool/config/coverage_planner.v1.json": _sha256(config_path),
            "product_tool/config/adapter_profiles.v1.json": _sha256(root / "product_tool/config/adapter_profiles.v1.json"),
            "product_tool/config/brand_normalization.v1.json": _sha256(root / "product_tool/config/brand_normalization.v1.json"),
        },
        "working_adapters": [
            {"route_id": r.route_id, "family": r.family, "adapters": list(r.adapter_keys), "url_basis": r.url_basis,
             "dispatch_constant": f"worker.{r.dispatch_constant}", "known_exact_urls": len(r.known_urls())}
            for r in working_routes()
        ],
        "dealer_routes": {
            **{r.source_key: {"known_exact_urls": len(r.known_urls()), "scope": r.scope} for r in supplementary_routes()},
            "technopark": config["dealer_routes"]["technopark"],
        },
        "blocked_hosts_from_logs": blocked,
        "network": "none: the planner reads files only",
    }
    return {
        "meta": meta, "summary": summary,
        "family_facts": {family: fact.to_dict() for family, fact in sorted(facts.items())},
        "priority_queue": build_priority_queue(config, records, facts, wave_of_family),
        "waves": waves, "request_groups": groups, "pairs": pairs, "units": records,
    }


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def plan_files(plan: dict) -> dict[str, str]:
    """Deterministic file contents for one plan (name -> text)."""
    units_jsonl = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in plan["units"])
    return {
        "coverage_summary.json": dump({"meta": plan["meta"], "summary": plan["summary"]}),
        "coverage_units.jsonl": units_jsonl,
        "coverage_pairs.json": dump(plan["pairs"]),
        "priority_queue.json": dump(plan["priority_queue"]),
        "waves.json": dump(plan["waves"]),
        "request_groups.json": dump(plan["request_groups"]),
        "family_facts.json": dump(plan["family_facts"]),
    }


def plan_bytes(plan: dict) -> bytes:
    return "".join(f"== {name}\n{text}" for name, text in sorted(plan_files(plan).items())).encode("utf-8")


def write_plan(plan: dict, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in plan_files(plan).items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
        written.append(name)
    return sorted(written)


def _move_cause(before: dict, after: dict) -> str:
    """Why a unit changed status, from the two records alone."""
    if before["status"] == ROUTE_NO_ADAPTER and after["status"] == NEEDS_FIXTURE:
        return "evidence_scope_corrected"
    if before["status"] == IDENTITY_CONFLICT and before.get("reason", "").startswith("seller_sku_shared_across") and after["status"] != IDENTITY_CONFLICT:
        return "identity_rule_corrected"
    if after["status"] == READY and after.get("reason") == "exact_url_on_record" and before["status"] != READY:
        return "exact_url_confirmed"
    return "other"


def delta(before_units: Path, after_units: Path) -> dict:
    def load(path):
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]
        return {row["unit_id"]: row for row in rows}
    before, after = load(before_units), load(after_units)
    moves = Counter()
    causes = Counter()
    cause_moves: dict[str, Counter] = defaultdict(Counter)
    for unit_id in sorted(set(before) & set(after)):
        if before[unit_id]["status"] != after[unit_id]["status"]:
            key = (before[unit_id]["status"], after[unit_id]["status"])
            moves[key] += 1
            cause = _move_cause(before[unit_id], after[unit_id])
            causes[cause] += 1
            cause_moves[cause][key] += 1
    counts = lambda rows: dict(sorted(Counter(row["status"] for row in rows.values()).items()))
    return {
        "units_before": len(before), "units_after": len(after), "only_before": len(set(before) - set(after)), "only_after": len(set(after) - set(before)),
        "status_counts_before": counts(before), "status_counts_after": counts(after),
        "moves": [{"from": a, "to": b, "units": n} for (a, b), n in sorted(moves.items())],
        "moves_by_cause": {cause: {"units": causes[cause], "moves": [{"from": a, "to": b, "units": n} for (a, b), n in sorted(items.items())]}
                           for cause, items in sorted(cause_moves.items())},
        "ready_to_run_gain": counts(after).get(READY, 0) - counts(before).get(READY, 0),
    }
