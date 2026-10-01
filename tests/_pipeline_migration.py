"""Single source of truth for the one authorized, documented exception to
this project's "reports/ and past artifacts never change" convention.

Every stage from Stage 2 through Stage 11.3 was pure research/reporting --
it read the catalog and prior reports and wrote new report files, never
touching product_tool/ (the actual application). Stage 8's own
protected_hashes_after.json therefore includes a broad snapshot of the
whole repository, INCLUDING product_tool source files and even the
tests/test_structural_census_v8_1.py .. v9_1.py files themselves, as a
side effect of proving "nothing changed" during that research work.

Stage 11.4 was explicitly authorized by the user to modify the real
application (a DNS dealer-fallback pipeline integration) -- the first
stage whose task was to change product_tool/, not just study it. That
authorized exactly three files:

    product_tool/display.py, product_tool/jobs.py, product_tool/worker.py

Stage 11.5 closes the resulting gap: every one of the ten
tests/test_structural_census_v8_1.py .. v9_1.py files independently
re-checks those three files against the frozen Stage 8 baseline, so all
ten started failing the moment Stage 11.4 touched them. Making those tests
pass again required editing this exemption INTO the ten test files
themselves -- which meant their own byte content also changed relative to
the (also frozen, also reports/-adjacent) cross-stage checks that verify
"tests/test_structural_census_v8_N.py has not changed since stage M". This
module is that second, smaller layer of the same one-time, fully-documented
migration: every test file this project's own protection tests compare
against a frozen hash is listed here, exactly once, with a reason.

Nothing in reports/ was edited to make this module true. Every path listed
below was deliberately, visibly changed in this session, on this date, for
the stated reason -- verifiable directly by reading the file's current
content, which begins with a comment pointing back to this module.
"""
from __future__ import annotations

import hashlib

MIGRATION_DATE = "2026-09-23"


def _hash_path(path: str) -> str:
    """SHA-256 of a repo-relative path string. DELETED_FILES is keyed by
    this, not by the path itself -- see DELETED_FILES below for why."""
    return hashlib.sha256(path.encode("utf-8")).hexdigest()

# The actual application code Stage 11.4 was authorized to change.
PRODUCTION_CODE_MIGRATION: dict[str, str] = {
    "product_tool/display.py": (
        "Added SOURCE_NAMES['dns'] = 'DNS' -- a display label for the new "
        "dealer-fallback source key, additive only."
        " Stage 26: SOURCE_NAMES['samsung'] = 'Samsung Казахстан'; display_status() takes an optional source so the resolved status 'official_base_only' reads as a Samsung value whose variant is judged apart (the text for every other source is unchanged)."
    ),
    "product_tool/jobs.py": (
        "get_source_pages() ORDER BY now lists 'dns' explicitly (after the "
        "LG-only supplier fallback, before the generic fallback); enqueue() "
        "no longer rejects non-LG brands outright, since the DNS dealer "
        "fallback (unlike the LG-only supplier fallback) is available for "
        "any brand/category."
        " Stage 26: identification_status() reads a Samsung page's own levels (full article in the markup/title; the article only in the page text; only the base model) when a samsung source exists -- added before the LG lookups, which are unchanged; comparison_rows() passes the resolved value's source to display_status() so a Samsung value is not labelled as an LG base-model value."
    ),
    "product_tool/worker.py": (
        "run_once() now runs a DNS dealer-fallback stage after the official/"
        "LG-only-supplier stage (for LG products) or in their place (for any "
        "other brand, which previously hit a hard error with no fallback at "
        "all). The LG-only supplier fallback remains strictly LG-only and "
        "its own code path is otherwise byte-for-byte unchanged. Stage 12: "
        "added _compute_missing_fields() and now passes its concrete, "
        "per-row result as find_source()'s missing_fields argument "
        "(previously never passed at all, so DNS's own hardcoded default "
        "silently fired every time) -- closes the gap where dealer_url_"
        "needed listed all three field categories as missing regardless of "
        "what a prior stage in the same run had already found, or of which "
        "stages the job even requested. Stage 13: a second, no-longer-"
        "authorized LG-only supplier adapter was removed from the product "
        "entirely per explicit user instruction -- the adapter_factory "
        "tuple contract shrank from 3/4-tuple (lg_kz[,lg_ru],sulpak,<removed>) "
        "to 2/3-tuple (lg_kz[,lg_ru],sulpak); the fallback loop over two "
        "suppliers became a direct call to the one remaining supplier; "
        "'confirmed' now checks resolution.SUPPLIERS instead of a hardcoded "
        "two-name literal. Stage 14: added an is_hyperx branch (a new "
        "hyperx_adapter_factory parameter, mirroring dns_adapter_factory) "
        "that runs adapters.hyperx.HyperXAdapter for HYPERX-brand products "
        "-- a single official adapter, no regional split, no supplier "
        "fallback (none exists for HyperX). Its finish() logic checks "
        "exact_variant success first, then dns_confirmed (so a DNS "
        "confirmation is never discarded just because HyperX itself found "
        "nothing this run), then HyperX's own error/official_url_needed "
        "states, matching the existing non-official-brand priority order. "
        "Stage 16: the default hyperx_adapter_factory now passes "
        "fetch_log_path=database.parent/'hyperx_fetch_log.json' -- colocates "
        "HyperXAdapter's persisted fetch log with whatever jobs database "
        "this run uses, so a host-stop (403/429/challenge) survives a "
        "fresh run_once() call. Root-cause fix for the Stage 15 incident: "
        "populating a real KNOWN_URLS entry made worker.py's OLD default "
        "(a bare HyperXAdapter(clock=clock), which built a bare "
        "requests.Session()) capable of a real outbound request from 3 "
        "unrelated, pre-existing tests that never overrode "
        "hyperx_adapter_factory -- see adapters/hyperx.py and "
        "adapters/policy_fetch.py. Stage 17: the two inline brand-alias sets "
        "became module constants LG_BRAND_ALIASES / HYPERX_BRAND_ALIASES "
        "(identical contents) so the offline coverage planner reads the real "
        "dispatch table; no behavior change. Stage 20: the default LG adapter "
        "triple (used when no adapter_factory is injected) is now built by "
        "adapters.lg_policy.default_lg_adapters(database.parent) -- the same "
        "LGAdapter/LGRUAdapter/SulpakAdapter, but every request goes through "
        "adapters.policy_session.PolicyAwareSession with a persisted log "
        "(data/lg_fetch_log.json), so a 401/403/429 or a confirmed challenge "
        "stops the host in the next run too. Search and extraction code is "
        "unchanged. Stage 21 (owner decision): an LG job now finishes done when "
        "an official page matches the FULL row article and there is no real "
        "conflict -- a trusted-supplier confirmation is no longer required; "
        "the card's export readiness and its gaps (readiness.py) are appended "
        "to the job message and written as a progress event, so they never "
        "hide behind done. Stage 22: the documents stage reports how many "
        "instructions were CONFIRMED BY CONTENT and how many of them are "
        "Russian (the LG Russia documents adapter, adapters/"
        "lg_documents_adapter.py, saves a document only after its own text "
        "was read, and states its language from that text, so a non-Russian "
        "instruction can now be saved and must not be reported as Russian)."
        " Stage 26: an is_samsung branch (SAMSUNG_BRAND_ALIASES, a samsung_adapter_factory parameter mirroring hyperx_adapter_factory) runs the Samsung official adapter (adapters/samsung_source.py) through PolicyAwareSession with a persisted stop log (data/samsung_fetch_log.json) and a per-row request budget; the Samsung stages themselves live in samsung_pipeline.py (official page, instruction files, dealer gate and dispute check, readiness, final status), the worker only dispatches. The Samsung instruction stage runs BEFORE the dealer fallback so the dealer is asked only about what is still missing; an unconfirmed dealer page contributes no values. LG and HyperX branches are unchanged."
        " Stage 28: the Samsung branch passes documents_deadline=total_deadline to samsung_pipeline.official_stage, which now reads the instruction BEFORE saving the page (the manual's technical-data tables are the evidence for which size and weight belong to which part of a product) and persists the documents in documents_stage; nothing else in the worker changed."
        " Stage 30: for a Samsung product the dealer link request (dns_missing_fields) is built by samsung_pipeline.dealer_missing_fields(): the instruction counts as missing until a FULL RUSSIAN instruction is confirmed (a saved English file or a brief multilingual guide with a Russian section no longer closes it); characteristics and photos are checked exactly as before; every other brand keeps _compute_missing_fields() unchanged. No dealer request is made by this: without a verified exact URL the dealer adapter only writes the request text."
    ),
    "product_tool/census/endpoint_probe.py": (
        "Stage 13: added blocked_hosts_from_fetch_log() and "
        "AccessProbe.__init__(initial_stopped_hosts=...) -- lets a caller "
        "seed a brand-new AccessProbe with hosts a PAST run already recorded "
        "as blocked (401/403/429), so the stop-after-block guarantee survives "
        "a fresh process/script invocation, not just one instance's lifetime. "
        "Added because Stage 12 Part B made 4 requests to www.razer.com "
        "after robots.txt returned 403 by using raw requests.Session calls "
        "instead of AccessProbe -- see reports/source_census_2026-09-23_"
        "stage13/report.md for the full audit. Stage 14: added "
        "DirectNetworkCallBlocked and enforce_policy_aware_fetch_only() -- "
        "a context manager that, while active, makes every direct "
        "requests.Session.get() call NOT routed through AccessProbe.probe() "
        "raise before any network I/O. Closes the remaining gap: Stage 12's "
        "actual mistake was never using AccessProbe at all, so seeding it "
        "with a blocked-host set (the Stage 13 fix) only helps code that "
        "already goes through it. AccessProbe.probe() itself now calls "
        "through a pre-captured _REAL_SESSION_GET reference (via the new "
        "_get() helper) so it is immune to its own guard. Stage 15: added "
        "guarded_entry_point(), a decorator that wraps a whole function "
        "call in enforce_policy_aware_fetch_only() -- closes the gap that "
        "the guard existing as a context manager some code could opt into "
        "is not the same as it being active at every place research code "
        "actually starts. product_tool/census/{runner,runner_v5,runner_v71,"
        "report_v71}.py's own __main__ entry points (main()/render()) are "
        "now each decorated with it, see their own migration entries below. "
        "Stage 16: enforce_policy_aware_fetch_only() is now reentrant -- it "
        "saves and restores whatever requests.Session.get WAS, instead of a "
        "hardcoded _REAL_SESSION_GET -- so a test that itself calls this "
        "context manager (several already do) no longer clears a "
        "process-wide activation (see tests/__init__.py) on exit. Also "
        "added RealNetworkIOBlocked and block_all_real_network_io(): "
        "patches requests.adapters.HTTPAdapter.send (below Session.get(), "
        "below AccessProbe's own immunity) so a real HTTP call of ANY kind "
        "-- including through AccessProbe's otherwise-legitimate real-"
        "session path -- fails before socket I/O. This is what "
        "tests/__init__.py activates for the whole test process; it is a "
        "different, stricter guarantee than enforce_policy_aware_fetch_"
        "only() (which deliberately exempts AccessProbe, since that guard "
        "is about bypassing AccessProbe specifically, not about being in a "
        "test process at all)."
    ),
    "product_tool/census/runner.py": (
        "Stage 15: main() is now decorated with endpoint_probe."
        "guarded_entry_point() -- the real entry point a person invokes "
        "(`python -m product_tool.census.runner ...`) is now covered by "
        "enforce_policy_aware_fetch_only() for its whole run, not only code "
        "that separately remembers to opt in. probe_sources() already only "
        "ever reaches the network through AccessProbe (immune to the "
        "guard), so this is additive protection, not a behavior change. "
        "Stage 16: probe_sources()'s eligibility filter no longer excludes "
        "by the removed dealer's literal source_id -- this legacy census "
        "registry has no such record at all, so the check was redundant "
        "with the generic official_status=='official_verified' filter "
        "already there; removed, not replaced with another branch."
    ),
    "product_tool/census/runner_v2.py": (
        "Stage 16: same removal as runner.py above -- probe_sources()'s "
        "eligibility filter no longer names the removed dealer's "
        "source_id; the generic official_status==OFFICIAL_VERIFIED filter "
        "already excludes anything not verified in this registry."
    ),
    "product_tool/census/runner_v5.py": (
        "Stage 15: the inline `if __name__ == '__main__':` argument-parsing "
        "block was split into its own main(), decorated with endpoint_probe."
        "guarded_entry_point(), same reasoning as runner.py above. Stage 17: "
        "one prose sentence in the generated report text no longer names "
        "the removed dealer (now 'the dealer exclusion'); no behavior change."
    ),
    "product_tool/census/runner_v71.py": (
        "Stage 15: same as runner_v5.py -- the inline `if __name__ == "
        "'__main__':` block became its own main(), decorated with "
        "endpoint_probe.guarded_entry_point(). This module's --live path "
        "(BoundedHTTP) already only reaches the network through "
        "endpoint_probe.AccessProbe (immune to the guard)."
    ),
    "product_tool/census/report_v71.py": (
        "Stage 15: render(), this module's own entry point, is now "
        "decorated with endpoint_probe.guarded_entry_point(). render() only "
        "ever reads saved JSON and writes report.md -- no network involved "
        "-- decorated anyway for uniform coverage across every research "
        "script entry point, not because it was ever at risk itself. "
        "Stage 17: one prose sentence in the generated report text no "
        "longer names the removed dealer; no behavior change."
    ),
    **{
        f"product_tool/census/{name}.py": (
            "Stage 17: a prose sentence inside this one-off report script's "
            "generated text named the removed dealer literally; it now says "
            "'the dealer exclusion' / 'excluded dealers'. Text-only, no "
            "filtering or other behavior change; immutable reports/ output "
            "already produced by the old wording is untouched."
        )
        for name in ("report_v5_1", "report_v6", "report_v7", "structural_report_v8")
    },
    "product_tool/config/source_catalog.v2.json": (
        "Stage 13: a second, no-longer-authorized LG-only supplier's source "
        "record (official_status=not_allowed, enabled=false) was deleted "
        "entirely, per explicit user instruction to remove it from the "
        "product completely rather than keep a disabled, named record. The "
        "generic 'official_status==not_allowed sources are excluded' "
        "mechanism in product_tool/sources.py and product_tool/census/"
        "registry.py is untouched and unnamed -- it still applies to any "
        "future source, it just has no live example in this file right now."
    ),
    "product_tool/resolution.py": (
        "Stage 13: SUPPLIERS shrank to a single-member set. The two-or-more-"
        "suppliers-agree/conflict logic itself was kept (it is generic "
        "multi-supplier resolution, not tied to any one dealer's name) but "
        "de-hardcoded: the conflict message no longer names any dealer "
        "literally, and the confirmed_two_suppliers source string is now "
        "'+'.join(sorted(source_keys)) instead of a literal two-name string. "
        "Stage 14: OFFICIAL gained 'hyperx' (a second official manufacturer "
        "source, alongside lg/lg_kz/lg_ru). The official_base_only and "
        "official_regions_conflict messages, previously hardcoded to name "
        "LG specifically ('базовой модели LG', 'LG Россия и LG Казахстан'), "
        "are now generic -- built from each source's own site_name (with a "
        "source_key fallback for synthetic test facts lacking it), since "
        "they are no longer LG-exclusive text once a second official "
        "source exists. Stage 21 (D3): the conflict test compares a "
        "canonical KEY of each value (spacing, thousands separators, 'шт.' "
        "and the multiplication sign are formatting), so '1шт' and '1 шт.' "
        "are the same value; the same key also treats a unit mark after the "
        "number ('23.8\"', '0.2745 x 0.2745 мм'), '(r/l)'/'(п/л)' and "
        "'(u/d)'/'(в/н)', and 'меньше'/'менее' as the same wording; display "
        "and storage still use the normalized value, and different values "
        "(a colour name, a depth, a remote kind) still conflict. Stage 22: the "
        "same key reads '~' as '-' and MHz/kHz/GHz/Hz as their Cyrillic "
        "forms, so '87.5 ~ 108.0 MHz' and '87.5 - 108.0 МГц' are one value."
        " Stage 26: OFFICIAL gained 'samsung' (a third official manufacturer source). Nothing else changed: the priority order (official over an unconfirmed dealer value) and the same-name conflict test are the ones LG and HyperX use."
    ),
    "product_tool/adapters/lg.py": (
        "Stage 21 (D4): lg_base_model() strips a dotted regional suffix of "
        "3 or more capital letters (was 5 or more), so a base model such as "
        "24MR400-B is searched for when the article is 24MR400-B.ARUQ. This "
        "changes ONLY which sitemap page is looked up; whether the page "
        "confirms the FULL article is still decided by _designation() on the "
        "page text, so a base-code hit never becomes an exact variant. Stage 21 "
        "(D1/D5): LGRUAdapter.find_source() no longer requests the constructed "
        "URL https://www.lg.com/ru/laundry/lg-{model} (404 for every pilot "
        "row); it reads the observed LG Russia sitemap "
        "(https://www.lg.com/ru/sitemap.xml, reached from lg.com/sitemap.xml "
        "-> ru/index.xml) and fetches the product URL whose slug equals the "
        "article or its base model, exactly like the KZ adapter; parsing, "
        "identity level and find_documents() are unchanged. Stage 22: the LG "
        "Russia gallery is read from the observed structure "
        "/ru/images/<category>/<md...>/gallery/ (the old filter accepted "
        "only /stylers/, which no saved page uses, so RU pages never gave "
        "a photo; the second pilot then showed pages whose pictures lie "
        "directly in /ru/images/<category>/<md...>/ without a gallery "
        "folder, accepted as well): a thumbnail is taken at the largest size its own node "
        "names (data-medium/data-large), the objet placeholder and any "
        "picture outside the gallery folder are dropped, and the match "
        "level is decided as before -- a photo never raises it. The "
        "Kazakhstan extraction is unchanged. Stage 23 (owner decision): "
        "lg_base_model() also drops a trailing market tag '_KZ' / '_SU' of "
        "the seller's article, so a candidate page can be FOUND; the match "
        "stays base_model until the official content shows the full "
        "article (nothing else about the match levels changed)."
    ),
    "product_tool/normalization.py": (
        "Stage 21 (D3): normalize_name()/normalize_fact() keep different "
        "physical quantities apart -- weight/size/colour of a named part or "
        "state (with/without stand, gross/net, indoor/outdoor unit, cavity, "
        "turntable, door/body/inside colour, speaker parts, maximum laundry "
        "load, shipping box) get a qualifier suffix, and an otherwise "
        "unmapped name whose value is a dimension or a weight gets a kind "
        "suffix. Two different values of the SAME quantity still share one "
        "name and still conflict. Later in Stage 21: NAME_RULES apply only "
        "when the name BEGINS with the quantity word (colour bits, colour "
        "gamut, load detector, LCD feature, 'max time' no longer fold into "
        "colour / capacity / display_type / max_rpm); a dash-only value is "
        "not a fact. Stage 22: one edge of the product (width / height / depth "
        "stated alone) and a depth counted with the door get their own "
        "names, so a single depth value is no longer compared with the "
        "W x H x D triple."
        " Stage 26 (Samsung pages): the closed vocabulary of quantities grew by what the eleven Samsung cards showed folding into one name: a display's size (display_size) and an 'image size' mode (image_size_mode) are not the size of the product; a turntable is 'вращающийся стол' too; depth/height with the door handle, without the door handle, without the doors, with or without the hinges, and for the packaging get their own qualifiers. Names that were already package_* keep their name; an unknown wording still shares a name and ends in a conflict for a person."
        " Stage 27 (a real Samsung dishwasher page): 'Цвет/материал: Нет' (a yes/no option) and 'Цвет подсветки дисплея' (a backlight colour) no longer fold into the product colour (color_material_option, backlight_color); nothing else changed. The two same-named rows a Samsung robot-vacuum page lists for the robot and its station (size, weight) still share one name and still end in a conflict for a person."
        " Stage 28 (a Samsung robot vacuum and its cleaning station): a size / weight row that names the cleaning station (cleaning_station) or, by an explicit manual table, the main device ('основное изделие', main_unit) is that part's own quantity; nothing else changed."
    ),
    "product_tool/exporter.py": (
        "Stage 13: the 'Проверка источников' sheet's hardcoded column for "
        "the removed dealer (header and per-row value) was removed."
        " Stage 26: when the batch has a Samsung source page, the 'Проверка источников' sheet gets a Samsung column, the 'Источники' sheet names the level 'Артикул только в тексте страницы', and a 'Готовность Samsung' sheet lists each Samsung card's verdict, evidence levels, open variant differences, gaps, the three document facts, photos selected/found, dealer disputes and open reviews. A batch without a Samsung page exports exactly as before."
        " Stage 27: the sheet 'Готовность Samsung' shows the instruction's PDF-code line with the acceptance mark and gains a last column with the acceptance basis ('exact_page_link_only: принята', 'code_relation_declared_by_page_data: принята', 'family_mask_in_pdf: принята', ...: не принята); a batch without a Samsung page exports exactly as before."
        " Stage 28: the sheet 'Готовность Samsung' gains a last column with the reason for every remaining gap."
    ),
    "docs/MULTI_DOMAIN_OFFICIAL_FALLBACK_V7.md": (
        "Stage 13: removed a standalone sentence naming the removed dealer "
        "from the dealer_gate paragraph -- the paragraph's remaining text "
        "(Sulpak allowlist only) already states the actual rule without "
        "naming an excluded dealer."
    ),
    "docs/SOURCE_CENSUS.md": (
        "Stage 13: the paragraph naming the removed dealer as 'disabled "
        "legacy compatibility data with official_status=not_allowed' was "
        "rewritten to describe the exclusion rule generically (any "
        "not_allowed record is excluded from SourceRegistry), matching "
        "source_catalog.v2.json no longer containing that record at all."
    ),
}


# Stage 36: the owner explicitly authorized the narrow Bosch Home production
# integration. These are the precise existing files it changes. The Stage 8
# baseline stays frozen; after implementation their exact hashes are pinned
# in PINNED_SHA256 below. New Bosch modules have their own Stage 36 report.
STAGE36_MIGRATION_DATE = "2026-09-26"
STAGE36_CODE_MIGRATION: dict[str, str] = {
    "product_tool/worker.py": "Stage 36: dispatch BOSCH through bosch_pipeline only after its selected category/model gate; other Bosch rows finish before client construction.",
    "product_tool/jobs.py": "Stage 36: enqueue rejects unselected Bosch rows; identification_status reports the verified KZ model while keeping E-Nr revision unknown.",
    "product_tool/exporter.py": "Stage 36: Bosch comparison column and a separate readiness sheet carry job status, model evidence, unknown revision, selected photos and family-manual limits.",
    "product_tool/resolution.py": "Stage 36: bosch_home joins official source keys so KZ technical values receive the existing official priority.",
    "product_tool/display.py": "Stage 36: add the Bosch Home Kazakhstan source label.",
    "product_tool/web.py": "Stage 36: pass Bosch card readiness to the ordinary product page when its source exists.",
    "product_tool/templates/product.html": "Stage 36: show Bosch's own comparison column and card readiness separately from job status; make the search heading brand-neutral.",
    "product_tool/source_types.py": "Stage 36: label bosch_home as an official source for provenance.",
    "product_tool/config/coverage_planner.v1.json": "Stage 36: select only TWK7203 in kettles and MMB2111M in blenders, one checked Bosch Home row per category.",
}
STAGE37_MIGRATION_DATE = "2026-09-27"
STAGE37_CODE_MIGRATION: dict[str, str] = {
    "product_tool/web.py": "Stage 37: add a one-click selected LG batch route, stage selection and separate readiness context.",
    "product_tool/jobs.py": "Stage 37: claim_next permits only one globally running job; the worker process lock prevents a second startup from recovering an active job.",
    "product_tool/worker.py": "Stage 37: record unreadable LG PDF evidence in the ordinary job event; existing DNS full manufacturer-code check is retained.",
    "product_tool/exporter.py": "Stage 37: add an LG sheet with job status, card readiness, stages and human-readable gap reasons.",
    "product_tool/templates/product.html": "Stage 37: full LG stage set checked by default; show job status separately from LG card readiness and causes.",
    "product_tool/templates/batch.html": "Stage 37: explicit one-per-category LG selection, counters, stage controls and manual progress refresh.",
}
for _path, _reason in STAGE37_CODE_MIGRATION.items():
    if _path in PRODUCTION_CODE_MIGRATION:
        PRODUCTION_CODE_MIGRATION[_path] += " " + _reason
    else:
        PRODUCTION_CODE_MIGRATION[_path] = _reason

STAGE38_CODE_MIGRATION: dict[str, str] = {
    "product_tool/web.py": "Stage 38: start the queued-job processor with the ordinary web app so the owner needs only one terminal.",
    "product_tool/templates/batch.html": "Stage 38: describe automatic queue processing in the batch page.",
    "product_tool/templates/product.html": "Stage 38: describe automatic queue processing in the product page.",
    "product_tool/lg_batch.py": "Stage 38: choose LG rows from each uploaded category instead of a fixed historical pilot-code list.",
}
for _path, _reason in STAGE38_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

STAGE39_CODE_MIGRATION: dict[str, str] = {
    "product_tool/importer.py": "Stage 39: treat a descriptive Model column as product name and infer category from that name without replacing the full article.",
    "product_tool/adapters/lg.py": "Stage 39: split explicit LG kit codes and search a shorter model named in the title without promoting it to a confirmed variant.",
    "product_tool/worker.py": "Stage 39: read descriptive names from older imported rows and pass shorter LG model candidates into official discovery.",
    "product_tool/jobs.py": "Stage 39: a missing sitemap page no longer reports a false article contradiction.",
}
for _path, _reason in STAGE39_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

STAGE40_CODE_MIGRATION: dict[str, str] = {
    "product_tool/adapters/sulpak.py": "Stage 40: record the owner's exact two-component LG kit URL as a candidate and withhold dealer fields when only the base model appears in page text.",
}
for _path, _reason in STAGE40_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

STAGE41_CODE_MIGRATION: dict[str, str] = {
    "product_tool/adapters/sulpak.py": "Stage 41: normalize the known two-unit LG kit lookup and explain that a policy-blocked page does not prove its codes.",
    "product_tool/adapters/supplier.py": "Stage 41: match complete two-unit articles with optional spacing and strict suffix boundaries.",
    "product_tool/adapters/lg.py": "Stage 41: recognize full two-unit LG articles in visible official page text without promoting a different suffix.",
    "product_tool/resolution.py": "Stage 41: withhold LG colour and colour-bearing door finish when only a base-model page supports them; accept exact-code DNS colour only after code confirmation.",
    "product_tool/lg_batch.py": "Stage 41: show a blocked Sulpak page and unconfirmed variant colour or finish as concrete card and Excel gaps.",
}
for _path, _reason in STAGE41_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

for _path, _reason in STAGE36_CODE_MIGRATION.items():
    if _path in PRODUCTION_CODE_MIGRATION:
        PRODUCTION_CODE_MIGRATION[_path] += " " + _reason
    else:
        PRODUCTION_CODE_MIGRATION[_path] = _reason

# Stage 13: a second, no-longer-authorized LG-only supplier adapter was
# part of the Stage 8 baseline (protected_hashes_after.json) and is now
# DELETED, not edited -- a file that used to exist and no longer does needs
# a different check than check_migrated_file() (which assumes the file is
# still readable). Every path here must be independently confirmed ABSENT,
# never merely assumed.
#
# Stage 15: this dict is keyed by the SHA-256 of the deleted module's
# repo-relative path, not the path itself -- the removed dealer's literal
# name no longer appears anywhere in this active module. The real,
# historical filename is still on record: reports/source_census_2026-09-23_
# stage13/report.md and *_stage13/scripts/*.py (archival, immutable) name
# it plainly, exactly as they did when the deletion happened. Any caller
# that already knows a real repo-relative path (an archived baseline
# manifest, an OS directory listing) can still ask "is this specific path
# an authorized deletion" via is_deleted_file_path()/check_deleted_file()
# below and get back the same reason text as before.
DELETED_FILES: dict[str, str] = {
    # SHA-256 of the deleted module's repo-relative path, precomputed --
    # never hashlib.sha256(b"...") on a literal path string here, since
    # that would just put the name back into this file's own source text.
    "08bb36ffcd33c71ebfbfd0e26455d7da2c5380b5e84cb2713b953eda56c89621": (
        "Stage 13: a second, no-longer-authorized LG-only supplier adapter "
        "was removed from the product entirely, per explicit user "
        "instruction -- not disabled, not stubbed, the module itself "
        "deleted. See PRODUCTION_CODE_MIGRATION above for every other file "
        "this same removal touched (config, resolution, jobs, display, "
        "worker, source_types, dealer_fallback, exporter, the product page "
        "template, and the docs/ pages that described the old rule). The "
        "deleted module's real, historical filename is preserved in the "
        "archival Stage 13 report (see reports/source_census_2026-09-23_"
        "stage13/), never in this active module -- see the comment above "
        "DELETED_FILES for why this dict is keyed by path hash, not path."
    ),
}


def is_deleted_file_path(path: str) -> bool:
    """True if `path` (repo-relative, forward slashes) is one of the paths
    in DELETED_FILES, checked by hash so the literal path text never has
    to appear as a string literal in this module's own source."""
    return _hash_path(path) in DELETED_FILES


def check_deleted_file(path: str) -> tuple[bool, str]:
    """The protection check for a Stage-8-baseline path that this project
    deliberately deleted rather than edited. Returns (ok, message). A path
    not in DELETED_FILES is never excused just because it happens to be
    missing -- a missing protected file is still a bug unless it is listed
    here with a reason, exactly like check_migrated_file() for edits."""
    if not is_deleted_file_path(path):
        return False, f"{path!r} is not part of any authorized deletion."
    return True, f"{path!r} is an authorized deletion: {DELETED_FILES[_hash_path(path)]}"

# The ten regression-test files that, as an unavoidable consequence of the
# above, also needed a small, identical, documented edit: an exemption so
# their own "these files must match the Stage 8 baseline exactly" check
# does not re-flag the three files above as an unexplained anomaly.
TEST_FILE_MIGRATION: dict[str, str] = {
    f"tests/test_structural_census_{name}.py": (
        "Added the Stage 11.4 production-code exemption (see "
        "PRODUCTION_CODE_MIGRATION in tests/_pipeline_migration.py) to this "
        "file's own Stage-8-baseline check, and -- for every stage test file "
        "after v8_1 -- the matching exemption in its own cross-stage "
        "'earlier test files untouched' check, since editing this file also "
        "changed its own hash. Stage 13: its Stage-8-baseline check now also "
        "skips the existence assertion for any path in DELETED_FILES (only "
        "the one deleted adapter module so far, see DELETED_FILES above), "
        "asserting it is actually absent instead; and its registry_files_"
        "sha256 loop (present from v8_3 onward) now applies the same "
        "check_migrated_file() exemption to product_tool/config/"
        "source_catalog.v2.json. v8_1/v8_2/v8_2_1/v8_2_2 additionally "
        "flipped their live source_catalog.v2.json presence check for the "
        "removed dealer's record from assertIn to assertNotIn. Stage 15: "
        "DELETED_FILES is now keyed by path hash, not the literal path (see "
        "DELETED_FILES above) -- every one of these 10 files' 'if path in "
        "DELETED_FILES' membership check became 'if is_deleted_file_path"
        "(path)', changing its own hash again."
    )
    for name in (
        "v8_1", "v8_2", "v8_2_1", "v8_2_2", "v8_3", "v8_4", "v8_5", "v8_6", "v9", "v9_1",
    )
}

STAGE41_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 41: the owner explicitly requested updates to the existing LG batch; preserve all jobs and source facts, add the blocked Sulpak candidate and recompute only variant-colour resolutions. The exact pre-change SQLite backup and row comparison are in the Stage 41 report.",
}
STAGE42_CODE_MIGRATION: dict[str, str] = {
    "product_tool/adapters/lg.py": "Stage 42: identify the full LG article from the main KZ/RU PDP sales-code fields on saved official pages, not URL text or related items.",
    "product_tool/adapters/sulpak.py": "Stage 42: explain the persisted S3WER challenge as the reason P12ED was never requested.",
    "product_tool/lg_batch.py": "Stage 42: show the precise Sulpak host-stop evidence and the unverified base-model Russian PDF in card and Excel readiness.",
    "product_tool/resolution.py": "Stage 42: label facts from exact official LG PDPs as full-article evidence and retain official/dealer conflicts for review.",
}
for _path, _reason in STAGE42_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason
STAGE42_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 42: only two owner-selected LG cards in batch ae3d2cb381744ba8a811e54231233254 were updated offline from saved evidence; a consistent pre-change backup and table comparison are in the Stage 42 report.",
}
STAGE42_TEST_MIGRATION: dict[str, str] = {
    "tests/test_stage22_photos.py": "Stage 42: two saved RU PDPs print exact sales model plus suffix in their main structured fields; photo counts remain the same, but prior base-only expectations are superseded.",
}

STAGE43_CODE_MIGRATION: dict[str, str] = {
    "product_tool/adapters/lg.py": (
        "Stage 43: real LG site-search wired in as a bounded fallback for AFTER the sitemap lookup fails "
        "to reach full_sku (both LGAdapter.find_source and LGRUAdapter.find_source; per-component for a "
        "multi-unit kit article). It is opt-in (a new browser_search=None constructor parameter -- every "
        "existing caller that does not pass one gets today's sitemap-only behavior, byte for byte). A hit "
        "is discovery-only, handed to a new module-level helper, _augment_with_browser_search(), which "
        "fetches the candidate through the SAME plain-HTTP path used for a sitemap-found page and reads "
        "the candidate page's OWN printed sales code; it only ever APPENDS an evidence sentence (a match, "
        "a mismatch, or the search's own stop reason) and never changes match_level on its own -- exactly "
        "the project's existing rule that a URL/label proves nothing on its own (Stage 23)."
    ),
    "product_tool/worker.py": (
        "Stage 43: the LG adapter_factory/default_lg_adapters() tuple contract grew an optional 4th "
        "element (adapters.lg_browser_search.LGBrowserSearch); run_once() unpacks 2/3/4-tuples and closes "
        "it in a finally block after this job's LG-related work, so its browser subprocess (if one was "
        "ever opened) has a bounded, one-product lifetime. OFFICIAL_BUDGET_SECONDS raised 20->45 (shared "
        "by both LG regions' sitemap lookup AND, only for a row that needs it, the new site-search "
        "fallback; a row the sitemap already resolves to full_sku is unaffected)."
    ),
}
for _path, _reason in STAGE43_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

STAGE43_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": (
        "Stage 43: the owner's own test batch ae3d2cb381744ba8a811e54231233254 (12 rows) was re-run "
        "through the ordinary enqueue -> worker.run_once() -> card -> Excel path, live, with the new LG "
        "site-search fallback wired in. A pre-run SQLite backup and a full before/after table comparison "
        "(every row outside this batch's 12 products identical; other tables' row counts unchanged) are in "
        "the Stage 43 report."
    ),
}
STAGE46_CODE_MIGRATION: dict[str, str] = {
    "product_tool/worker.py": "Stage 46: load the saved official LG support API response alongside its rendered DOM for an existing observed support URL; background access stops remain unchanged, and support/manual identity cannot satisfy the final product-page status gate.",
}
for _path, _reason in STAGE46_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason
STAGE46_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 46: add one attended official LG support DOM/API snapshot and one content-checked Russian PDF to the existing P12ED card (product 4) in batch ae3d2cb381744ba8a811e54231233254; 15 products and 34 jobs remain, status needs_review and readiness not_ready. Dry-run on SQLite backup passed."
}
STAGE47_CODE_MIGRATION: dict[str, str] = {
    "product_tool/jobs.py": "Stage 47: record a failed/empty refresh while retaining the last content-confirmed source page and its facts/photos; a newly fetched mismatching page still replaces old evidence.",
    "product_tool/worker.py": "Stage 47: retain a verified LG manual when a retry of its unchanged source page is technically unreachable; pass support links printed by saved official product pages to the existing support adapter; distinguish confirmed support identity from missing product/spec/photo identity.",
    "product_tool/adapters/lg_support.py": "Stage 47: extract only observed product-specific KZ/RU support anchors from official product HTML as candidates, stripping fragments and keeping content verification in the existing adapter.",
    "product_tool/exporter.py": "Stage 47: use the imported full article as the display identifier when the optional product name is empty, including the documents and readiness sheets.",
    "product_tool/lg_batch.py": "Stage 47: describe unresolved official LG fact conflicts without falsely asserting every conflict is between KZ and RU.",
}
for _path, _reason in STAGE47_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason
STAGE47_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 47: append 17 completed jobs for only the existing 12 LG products in batch ae3d2cb381744ba8a811e54231233254 (12 initial runs and 5 targeted reruns); preserve product rows, existing facts/photos/manuals, and all prior jobs. One previously observed official PDF was rechecked; no other site request was made. See the Stage 47 before/after integrity audit."
}
STAGE48_CODE_MIGRATION: dict[str, str] = {
    "product_tool/adapters/common.py": "Stage 48: carry the observed specification section separately from label and value.",
    "product_tool/adapters/lg.py": "Stage 48: retain LG KZ/RU technical table headings before canonical mapping and deduplicate within sections only.",
    "product_tool/normalization.py": "Stage 48: distinguish component sections, plus-suffixed modes, net/package weight, Bluetooth version and availability, and equivalent regional values without changing quality gates.",
    "product_tool/resolution.py": "Stage 48: keep Cyrillic x-like letters in prose; normalize multiplication signs only in numeric dimension strings.",
    "product_tool/migrations.py": "Stage 48: additive job schema migration for per-fact section provenance.",
    "product_tool/jobs.py": "Stage 48: persist the extracted section with each normalized fact.",
}
for _path, _reason in STAGE48_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason
STAGE48_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 48: add section column and replay only seven LG products (7,8,9,10,11,12,14) in batch ae3d2cb381744ba8a811e54231233254 from saved Stage 47 product HTML; append seven terminal offline jobs. All product rows, source pages/snapshots, photos, documents and untargeted facts/results/jobs are unchanged. See Stage 48 integrity audit."
}
STAGE48_MARKERS_CODE_MIGRATION: dict[str, str] = {
    "product_tool/adapters/common.py": "Stage 48 marker addendum: carry explicit specification value-cell provenance with raw attributes.",
    "product_tool/adapters/lg.py": "Stage 48 marker addendum: preserve LG section, raw marker, and empty value cells before normalization.",
    "product_tool/normalization.py": "Stage 48 marker addendum: normalize presence, absence, unknown, marker vectors and versions by value-cell context without collapsing distinct concepts.",
    "product_tool/resolution.py": "Stage 48 marker addendum: keep unknown raw facts without treating them as conflicts or confirmed values.",
    "product_tool/display.py": "Stage 48 marker addendum: display unknown and ordered marker vectors accurately.",
    "product_tool/jobs.py": "Stage 48 marker addendum: persist value-cell provenance and prefer known facts over unknown facts from the same source.",
    "product_tool/migrations.py": "Stage 48 marker addendum: add nullable value_cell fact column without modifying existing evidence.",
}
for _path, _reason in STAGE48_MARKERS_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason
STAGE48_MARKERS_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 48 marker addendum: add value_cell column and replay only six affected LG rows (5,9,10,12,14,15) from saved official HTML in batch ae3d2cb381744ba8a811e54231233254; append six terminal offline jobs. Source snapshots, photos, documents, other products, and their evidence remain unchanged. See marker addendum integrity audit."
}
STAGE48_PROJECTION_CODE_MIGRATION: dict[str, str] = {
    "product_tool/attribute_projection.py": "Stage 48 output addendum: present a substantive version or port count in place of a linked presence marker while retaining independent raw evidence.",
    "product_tool/display.py": "Stage 48 output addendum: label Bluetooth, Wi-Fi and USB facts explicitly in the card and audit.",
    "product_tool/web.py": "Stage 48 output addendum: show projected final LG attributes in the ordinary card comparison.",
    "product_tool/exporter.py": "Stage 48 output addendum: use projected LG attributes on product sheets while retaining separate facts on the source-audit sheet.",
}
for _path, _reason in STAGE48_PROJECTION_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason
# Stage 49: model/suffix and support identity are evaluated from saved LG
# content; only affected rows of the existing 12-row batch are replayed.
STAGE49_CODE_MIGRATION: dict[str, str] = {
    "product_tool/adapters/lg.py": "Stage 49: compare the whole catalog article with structured main-PDP model+suffix fields, including a dot omitted by the catalog; URLs and image names remain candidates.",
    "product_tool/worker.py": "Stage 49: persist the printed code of the RU support page already fetched during the instruction stage; no extra request or change to discovery.",
    "product_tool/lg_batch.py": "Stage 49: explain that a checked Russian PDF can still lack a proven link to the exact variant.",
    "product_tool/exporter.py": "Stage 49: expose manual and photo identity separately from selected raw candidates in Excel.",
    "product_tool/web.py": "Stage 49: label manual and photo candidates whose exact-variant relation is unverified in the ordinary card.",
    "product_tool/templates/product.html": "Stage 49: show the per-document and per-photo identity label alongside saved evidence.",
}
for _path, _reason in STAGE49_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason
STAGE49_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 49: replay ON77 identity from existing KZ/RU snapshots, preserve P12ED support-only result, record two previously saved RU support-page printed codes for W4W8 and ON77, and append only three terminal offline jobs (10,12,15); no fetch attempt or source snapshot was added. See Stage 49 report and backup."
}
# Stage 50: presentation-only changes after the read-only audit of all
# twelve existing LG cards and the Stage 49 workbook. The working database,
# source registry, discovery, extraction and identity code were not changed.
STAGE50_CODE_MIGRATION: dict[str, str] = {
    "product_tool/lg_batch.py": "Stage 50: show every raw value and section for unresolved LG conflicts in the user-facing readiness summary.",
    "product_tool/exporter.py": "Stage 50: put only exact-variant-confirmed values on main LG product sheets, separate selected unconfirmed photos into a candidate sheet, and show all disputed raw values on the source-audit sheet.",
    "product_tool/templates/product.html": "Stage 50: distinguish selected photo candidates from confirmed photos, show concrete conflicts, and use plain job text while keeping technical events available on demand.",
}
for _path, _reason in STAGE50_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

# Stage 51.1: the ordinary DNS fallback shares the expiring access-stop
# lifecycle and keeps a 401/403/429 from being retried by the next job.
STAGE51_1_CODE_MIGRATION: dict[str, str] = {
    "product_tool/worker.py": "Stage 51.1: pass the job database directory's dns_fetch_log.json to the default DNS adapter; its known-URL fallback now honors active access-stops across jobs."
}
for _path, _reason in STAGE51_1_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

# Stage 52: idempotent shared-PDF persistence and content-based support
# matching on previously observed official pages; no source registry change.
STAGE52_CODE_MIGRATION: dict[str, str] = {
    "product_tool/jobs.py": "Stage 52: reuse a product document by direct URL across official sources and reruns, preserving its row and verified provenance instead of violating the unique constraint.",
    "product_tool/adapters/lg.py": "Stage 52: use the existing structured sales-code relation for the code printed on a searched official support candidate, including joined versus dotted format.",
    "product_tool/adapters/lg_support.py": "Stage 52: use that same relation on support-page content; URL and search label remain candidates only.",
    "product_tool/worker.py": "Stage 52: retain an exact official support page when a later manual lookup lands on a weaker sibling variant, and save the sibling as candidate audit evidence.",
}
for _path, _reason in STAGE52_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

STAGE52_1_CODE_MIGRATION: dict[str, str] = {
    "product_tool/web.py": "Stage 52.1: migrate legacy timed access-stop audit entries on production startup and label synthetic refusals in both source rows and historical job events.",
}
for _path, _reason in STAGE52_1_CODE_MIGRATION.items():
    PRODUCTION_CODE_MIGRATION[_path] = PRODUCTION_CODE_MIGRATION.get(_path, "") + " " + _reason

STAGE52_1_DATA_MIGRATION: dict[str, str] = {
    "data/batches.sqlite3": "Stage 52.1: one S40T (product 13) source-only production job through the actual runtime; preserve all other products and prior evidence. Access-stop history is in the adjacent ignored JSON log, not in SQLite. Integrity and foreign-key checks passed.",
}

STAGE53_MIGRATION: dict[str, str] = {
    'product_tool/adapters/lg_documents.py': 'Stage 53: allow image MIME types through the existing lossless policy transport for on-demand byte measurement.',
    'product_tool/display.py': 'Stage 53: retain semantic Latin LG labels and distinguish a synthetic 200 challenge from a real HTTP error.',
    'product_tool/exporter.py': 'Stage 53: unique semantic headings, clear manual status, truthful photo metadata columns, and conditional candidate sheet.',
    'product_tool/jobs.py': 'Stage 53: preserve verified photo metadata on source refresh and save it only against the exact stored URL.',
    'product_tool/lg_batch.py': 'Stage 53: show all raw sides of conflicts with region, section and identity scope; retained manual is not called lost.',
    'product_tool/migrations.py': 'Stage 53: additive photo metadata migration; old HTML dimension hints remain separate from measured pixels.',
    'product_tool/static/styles.css': 'Stage 53: readable image metadata beneath each card preview.',
    'product_tool/templates/product.html': 'Stage 53: manual status and support link, full conflict sides, and actual or unknown image measurements.',
    'product_tool/web.py': 'Stage 53: filtered product description and truthful manual/access messages; one-photo policy-aware inspection.',
    'product_tool/worker.py': 'Stage 53: retain verified manuals when a later fetch is inconclusive and report that retention.',
    'data/batches.sqlite3': 'Stage 53: additive photo metadata columns; one corrupted historic Sulpak evidence string restored from the saved 200 challenge log; two saved S3WER image URLs measured. All card/job/fact/document/photo row counts unchanged; integrity passed.',
}

STAGE53_UI_MIGRATION: dict[str, str] = {
    "product_tool/web.py": "Stage 53 UI completion: present existing facts by source section and category role; record a one-field manual_user_override while retaining official facts.",
    "product_tool/templates/product.html": "Stage 53 UI completion: grouped comparison and photo lightbox markup; no evidence or source selection changed.",
    "product_tool/static/styles.css": "Stage 53 UI completion: grouped attribute tables and accessible full-size photo dialog.",
}

STAGE53_1_MIGRATION: dict[str, str] = {
    "product_tool/templates/batch.html": "Stage 53.1: poll the existing read-only batch page while jobs are active, updating counters and per-row status without enqueuing anything.",
    "data/batches.sqlite3": "Stage 53.1: owner uploaded a new 12-row LG batch and the already embedded worker completed its 12 jobs before this diagnostic. No row was replayed or deleted in this stage; the current production bytes and integrity are pinned after a consistent backup.",
}


# Stage 54.1: bounded LG discovery fallback, cross-region evidence, and no downgrade.
STAGE54_1_MIGRATION: dict[str, str] = {
    "product_tool/adapters/lg.py": "Stage 54.1: Scan bounded regional support candidates past rejected identities and retain decisions.",
    "product_tool/census/browser_worker.py": "Stage 54.1: allow bounded Google search result links to official LG hosts and report blocked redirect hosts.",
    "product_tool/adapters/lg_support.py": "Stage 54.1: scan bounded support candidates past three rejected pages and trace exact identity decisions.",
    "product_tool/display.py": "Stage 54.1: Name cross-region official evidence in the user-visible source description.",
    "product_tool/exporter.py": "Stage 54.1: Include verified cross-region LG sources in the export audit.",
    "product_tool/jobs.py": "Stage 54.1: Preserve stronger exact evidence on weaker reruns and recognize cross-region official pages.",
    "product_tool/lg_batch.py": "Stage 54.1: Recognize a verified cross-region LG source in batch presentation.",
    "product_tool/resolution.py": "Stage 54.1: Give verified cross-region official LG facts the official source priority.",
    "product_tool/source_types.py": "Stage 54.1: Register cross-region official LG as a distinct source type.",
    "product_tool/worker.py": "Stage 54.1: Run bounded shared-browser search after regional misses and retain trace decisions.",
}

ALL_AUTHORIZED_CHANGES: dict[str, str] = {**PRODUCTION_CODE_MIGRATION, **TEST_FILE_MIGRATION, **STAGE41_DATA_MIGRATION, **STAGE42_DATA_MIGRATION, **STAGE42_TEST_MIGRATION, **STAGE43_DATA_MIGRATION, **STAGE46_DATA_MIGRATION, **STAGE47_DATA_MIGRATION, **STAGE48_DATA_MIGRATION, **STAGE48_MARKERS_DATA_MIGRATION, **STAGE49_DATA_MIGRATION, **STAGE52_1_DATA_MIGRATION, **STAGE53_MIGRATION, **STAGE53_UI_MIGRATION, **STAGE53_1_MIGRATION, **STAGE54_1_MIGRATION}


def is_authorized_change(path: str) -> bool:
    """True if `path` (repo-relative, forward slashes) is part of the one
    documented Stage 11.4/11.5 migration -- never true for anything else.

    NOTE: this alone is NOT the protection check -- see check_migrated_file()
    below. Membership here only says a path is *eligible* for the pinned-hash
    check; it does not itself excuse any particular content."""
    return path in ALL_AUTHORIZED_CHANGES


# Stage 12 hardening: being "in ALL_AUTHORIZED_CHANGES" used to mean "any
# current content is accepted, no further check" -- a real gap, since a
# later, UNRELATED accidental edit to e.g. worker.py would have been
# silently waved through by that alone. These 13 files' exact post-migration
# content is now pinned here, once, as of the date below. Every protection
# test below checks the pinned hash, not just set membership -- a file that
# is authorized-but-no-longer-matches-its-pin fails the test again, exactly
# like any other unauthorized change would.
PINNED_SHA256: dict[str, str] = {
    "product_tool/display.py": "283666e2d3b1ee4729fe6d7e4d3b0489d26192a20822b7c17923b1a13e25692e",
    "product_tool/jobs.py": "90647f0621163ab6a8a874ee16ff592067ef2d3b5ecf97390933295221870bff",
    "product_tool/worker.py": "9d6b7475f07acccb0e9b166e1b063ac2e02cc37fd4c20b86c9526a2b12473fd7",
    "product_tool/census/endpoint_probe.py": "6c9dd046fd5f583cefdcce1e0a75295bed224c188d39ca9ea163059520e284ee",
    "product_tool/census/runner.py": "cda9197ea67ebc42387fe67e7e7849f3ea9990df1aed008fedce7ff3ca7b30c7",
    "product_tool/census/runner_v2.py": "49b1368cc6dfde60669229229a60579046f0b6beef4ca63ecec545757ecac743",
    "product_tool/census/runner_v5.py": "d032d7391f1343327f0a086fb829a659d66c7d8086dbe5ec0c0cb73c07d25e52",
    "product_tool/census/runner_v71.py": "44c7328ad96debace038824e1b6e9bf95086f40054a1be426b4b37a76e682b3c",
    "product_tool/census/report_v71.py": "ae3a739b9bfc1c6385c3a9682781919d14c137521fae593d56c170fb5d35072a",
    "product_tool/census/report_v5_1.py": "1bcb346c04b8b3e6f1336beb6e6fcd6604f3fe5719a4c96ddc188fcb78527fbc",
    "product_tool/census/report_v6.py": "d5c4b4464a96a6a577504e5b0c393d836082f4f9edfe6c76a1e200c322bfe24a",
    "product_tool/census/report_v7.py": "fedd5b88b658d1e757081ae8a48b7e0bd061abb032e3d70e6e27bb32a3380b7e",
    "product_tool/census/structural_report_v8.py": "9d4357d08cac3cf51ebf8d355b348ffed465f269f07644389713e52fdb027873",
    "product_tool/config/source_catalog.v2.json": "9348c0abf5e8c3cdd335e4cd9eb106e5f734098b3251471593455b89bcccb129",
    "product_tool/resolution.py": "70a125ba97e8b76cd3826590f29b2a4bbf29b00e9f47976e03e783e2a925c333",
    "product_tool/adapters/lg.py": "06e9b3098e6cb219f80b41434f330446d595d8325ba0c8f76c662c3a43a11b18",
    "product_tool/normalization.py": "25da9608ab7dcc1e6d1c8cb470c67ae70897d330556c4a72379bfad536939a5e",
    "product_tool/exporter.py": "8368e1fad2b6c9fda56647ae36c9d5596e04e44fc886966b0ff755c12c4e3725",
    "docs/MULTI_DOMAIN_OFFICIAL_FALLBACK_V7.md": "a420f11ca0831e938aaa8a61da7b31bb8bf06935b65f8d30b6b6c7aedcfb113f",
    "docs/SOURCE_CENSUS.md": "f78e5afdadc283834f06a24d931341003e3a51b79dbd6775352c9089fab0aabf",
    "tests/test_structural_census_v8_1.py": "2f2ad0dece37da3c4e86aee4853eafc54d68dcddfdd31725e36e7c794c5ceef2",
    "tests/test_structural_census_v8_2.py": "f1238638272529f7c1a57a7242d72ce6a0bd1d673a7eb9e8c0df32e1d2500bed",
    "tests/test_structural_census_v8_2_1.py": "25f9a9bf838db3dfd0791b13ed72e2e8381a2ee06dac8c034a84cc57221ccaf6",
    "tests/test_structural_census_v8_2_2.py": "08c8ed5a01ab01dd3ca15144c9afdeee9fff19c973d8e4cbb7e3daf3cda0b2f7",
    "tests/test_structural_census_v8_3.py": "21ed55ef422ddc09b31bc7eb71bd16ad337c15851680462e37bb313cea551477",
    "tests/test_structural_census_v8_4.py": "6f90f7b12c49e95f41b89b3bb73b9bfed7131f2eb60918a7346dfa3e2bf82e00",
    "tests/test_structural_census_v8_5.py": "7cbd7b6a3f288144c47f7d5dfc08b939275bc5889bc22383b11684053c56cf52",
    "tests/test_structural_census_v8_6.py": "c0bc25be1b698340cf8b4d2d8840348a27520cd8a81bb55ebb7e47fd3cc2fcc0",
    "tests/test_structural_census_v9.py": "2a503177f3b30406ad46205f2e9eaff00bec9ac5b48a1cd5d4881d431cc2bc8d",
    "tests/test_structural_census_v9_1.py": "715971a04fa6194e556c689fb92ad16feca1ff8ec989fab7e835c3bba6d71830",
}


# Exact Stage 36 post-migration bytes for every changed existing application file.
STAGE36_PINNED_SHA256 = {
    'product_tool/worker.py': '104c5c6dbee60be3df44c004d8c61fd532ccb89e14eb26d0aef07df5a0ce6a44',
    'product_tool/jobs.py': 'e06d78e837c096bb16435c92c135200488e008e8b311f24168e812d0dbd4cfc2',
    'product_tool/exporter.py': '2d871195b569967231a17331fe7aa80448295afc59a7ac33f1985398745fbf46',
    'product_tool/resolution.py': '909681b888fd3e63616f376e9b821d701b5a1a96b1bf6eaa650c64539b32f54c',
    'product_tool/display.py': 'd0c3d133cde39cf5ef9cb7cabbf5bd2a57f1583a4979c5dba81b1a60ee8b1dce',
    'product_tool/web.py': '927f66bfb3efd842cfed83d36621b8360c9be8970f6a55f13f2349ed7c6a2714',
    'product_tool/templates/product.html': 'bf55d0572f6f1e14c28dacdf882771a0e7a3d90c30283a406a6687a0e2194251',
    'product_tool/source_types.py': 'fa6dbe7a520fc8edf07542c41d8915e0c5ca20da2d242d55abe74dc54cbdbd97',
    'product_tool/config/coverage_planner.v1.json': 'ff6e986c59da939655af11cb489d1fc0d1711b79117072f397f2c3bb71f87794',
}
PINNED_SHA256.update(STAGE36_PINNED_SHA256)
STAGE37_PINNED_SHA256 = {
    'product_tool/exporter.py': 'b16e10780aa30ee9812fa8a2e84aae54d36cf49c699b0feb6aa6e147d4aea9e5',
    'product_tool/jobs.py': '989d5bf0811131776755dcf44ea36d048192a4c622e92990bc1ad80d4995d483',
    'product_tool/templates/batch.html': '1e327bf00283ac1f247420f06c217cd7d4a8dddcc8b3dfb4965ff4586770f722',
    'product_tool/templates/product.html': '9dc875a0c5b3bc51813ca36c71fa840d758f1ba9f188dbc0f4b7fa5ba781707a',
    'product_tool/web.py': '3d5414eae4db980f3655b21ccb597b895dfd46be70e99252ec7138bc775d783d',
    'product_tool/worker.py': '8f7b7f0c4d0984c2b1bfa3ee4086fceb3c52590b9f3da800a8c4cdfb8b9dd70d',
}
PINNED_SHA256.update(STAGE37_PINNED_SHA256)

STAGE38_PINNED_SHA256: dict[str, str] = {
    "product_tool/web.py": "ffa0392f0c29ad512b2e53a798fbc8dd5eb26c47bb170cdcbc8af75524de0156",
    "product_tool/templates/batch.html": "a8f30d979d80d398839fd174d84539bb3cab2c73084fda41cf1d1ab548c872b5",
    "product_tool/templates/product.html": "13c55756d622649bdf668cc1445c6f2ca7f2d0895ab8fcdd418492a705a2620a",
    "product_tool/lg_batch.py": "c51560eb2e2189bbeca92dc913c24e74c4071d4360f1c7211108d8f465ab76fe",
}
PINNED_SHA256.update(STAGE38_PINNED_SHA256)

STAGE39_PINNED_SHA256: dict[str, str] = {
    "product_tool/importer.py": "9bef5bc9985cf45d24e72678c2bf6720362ea88822dcccf38baa37ccaedc3a26",
    "product_tool/adapters/lg.py": "768be9096053f752a37c5587a1b56c2412ce3ab8d6075b575875a9444839b63e",
    "product_tool/worker.py": "fd04b3f73cfef5cf6322559f109d086bb70c45f40d628f32df0d96180153bb6f",
    "product_tool/jobs.py": "5edd29e5ec5f7da2e74e9b32e7bd719f3d46e734ffa01a80842417d0d7b77efc",
}
PINNED_SHA256.update(STAGE39_PINNED_SHA256)

STAGE40_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/sulpak.py": "8f579b8a983b364a50456a4f64d27d921c2402dc538576d21bc595b56e80e15d",
}
PINNED_SHA256.update(STAGE40_PINNED_SHA256)

STAGE41_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/sulpak.py": "970fdd1751710d914c5d5d7b3845910d6d6727f89bc127edd03672372f3b675f",
    "product_tool/adapters/supplier.py": "583f3d2bea283a3d1b5e1efcfddb3ea5f77125afbe6471616b2e4b0abcdcee7a",
    "product_tool/adapters/lg.py": "a36f60af8781bedb6995f701b3b4f6f8273dcaf3a5d855640f56c58feb8e2a15",
    "product_tool/resolution.py": "6d4ab51840508dcf4519e9e609bafebed0a0003ba065ed47a59fef03eb36d8b3",
    "product_tool/lg_batch.py": "f66c288219cc07d23dad9c8f91bc8b7d014eacd4cdd9954f35ae3a851d24fd35",
    "data/batches.sqlite3": "74ffa7a22520f576cdc85da5948430a5b86fd225107dfb36f616e8869a634638",
}
PINNED_SHA256.update(STAGE41_PINNED_SHA256)

STAGE42_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/lg.py": "203d83d2a6153929b176720e678188f48d025882bd3a1498c159058aaf49e424",
    "product_tool/adapters/sulpak.py": "a6f4332a2180d657836572ffe8abfa030c12330482c4dcccd151d80f76e397bf",
    "product_tool/lg_batch.py": "c47e420722792315e417b2322d016ad0a89bc95e60b60e147e9a2ee50f65636b",
    "product_tool/resolution.py": "1f5424e35ad1d5c4ddef0ad7f5e618d06f96071b9b6fa356315ec0ed47a43285",
    "data/batches.sqlite3": "b3a2f7855238270cce20faf796de6db16b0763d740b727f2a15df0348c72e7e2",
    "tests/test_stage22_photos.py": "56039bb52377f3cfa51898b507f655b250418caf295366f4fbeee4c69f4fc93b",
}
PINNED_SHA256.update(STAGE42_PINNED_SHA256)

STAGE43_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/lg.py": "edde39a5caa0ab755093948179cb9046eb670ef4a484b4b22c08bb40f7166b0f",
    "product_tool/worker.py": "717435336147f51d14b0d10724bd7b09be3469586239f4218d7b64683105d738",
    "data/batches.sqlite3": "45e67636c5be4df6ff9341b71f96c179f906c51233f32da6c5f2053e2fe4392d",
}
PINNED_SHA256.update(STAGE43_PINNED_SHA256)

# Stage 44: the existing P12ED row gains one offline-replayed observed LG
# support candidate and a corrected current job explanation. The saved HTML
# did not establish both kit components or a downloadable Russian manual.
STAGE44_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/lg.py": "2cb57773f42053ec09a4ad535fc8d4033e10fc2ab6160a167a21f32cc17020de",
    "product_tool/worker.py": "97d4f1f8eda149248523d8c9bce162aaa74c9a4ce63d23809284f80e2469aec6",
    "data/batches.sqlite3": "c8d4b209a518947af8e6b1a706dc68c7875d5eae5bd0cc63dd7ca9810dd40c43",
}
PINNED_SHA256.update(STAGE44_PINNED_SHA256)

# Stage 45: existing LG site-search hits and saved support snapshots share
# one support-verification step. The production database was not changed.
STAGE45_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/lg.py": "c5cbe4275c485a08242a464efed5edcedac04416adc7ba3e2641e3c27025ddca",
    "product_tool/worker.py": "423ab3830f07a454876c89f2680e36637cd61e20e8a7d5ed4a8ee916cd1a58a6",
}
PINNED_SHA256.update(STAGE45_PINNED_SHA256)

# Stage 46: user-assisted LG support capture and one verified document applied
# to the already loaded P12ED row; the earlier stage hashes are left intact.
STAGE46_PINNED_SHA256: dict[str, str] = {
    "product_tool/worker.py": "b8edf38f80e65d40c1c7ac4307680a4118fc2acd28c955ea010487c925a23aed",
    "data/batches.sqlite3": "3813d214044b87ffa9180537f315c164a1f854ade318aed6ab533d396ed42922",
}
PINNED_SHA256.update(STAGE46_PINNED_SHA256)

# Stage 47: all twelve existing LG rows were processed; current protected
# code and database bytes are pinned without changing earlier stage hashes.
STAGE47_PINNED_SHA256: dict[str, str] = {
    "product_tool/jobs.py": "c70bd6579b4f0d670930d376c266b04829485917be9e004e351da2300d346f3f",
    "product_tool/worker.py": "bfde98d8c0b9bd5ac06217682a3181acbd2507ac87e574fc0016bb82a7786594",
    "product_tool/adapters/lg_support.py": "0741321991ffd4930380bc2088beb4a5242f60fc13c6224e2140263bb9bd5596",
    "product_tool/exporter.py": "286989c693e89ec35b2e89be2829b8358fb6f629814c1fbe4f51a37bfaada309",
    "product_tool/lg_batch.py": "98a7b7da23c7961fb336fae67947de07e527f269aaf64d7be578c2163a5abe2d",
    "data/batches.sqlite3": "679189bf3474a323f23513c454593b4956f25d29969cb71116f0baca7b53f57c",
}
PINNED_SHA256.update(STAGE47_PINNED_SHA256)

# Stage 48: hashes of changed protected code and the offline-updated working database.
STAGE48_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/common.py": "abc6718b2926b5dacbecd10a8c422c40dd81070b6f44f1a5382253c49d3524aa",
    "product_tool/adapters/lg.py": "65692dd768c3477139e3f4c379a61c717d6b42e8110d02f649767b984ead4298",
    "product_tool/normalization.py": "d93dc49628206d9c7ca0ab84bc673949104aa0e5f404a006b0ca809d2e7e6002",
    "product_tool/resolution.py": "3c1bae04b572d15d9c5163de3529b4fc94d07cbe6bdf643b3206a6810345a64d",
    "product_tool/migrations.py": "690769da0014c2da7dfe3d49557f225317d378d444aa890a2f0bc991d9f8be24",
    "product_tool/jobs.py": "81c5ec46e90426b8920f32f08e51bcca6c02dacb80e4479308200d04b1837b40",
    "data/batches.sqlite3": "cd866d5a41842d52598ed4ef64177229a00878d296323b13f26c5840e07ca483"
}
PINNED_SHA256.update(STAGE48_PINNED_SHA256)

# Stage 48 marker addendum: preserve earlier migration records and pin the
# protected code/database bytes after the limited saved-page replay.
STAGE48_MARKERS_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/common.py": "46d7bbbf5171646bc6574928f751df54ae8ffb5fea459de7bc46c876610a0068",
    "product_tool/adapters/lg.py": "21045bcf647cf031e266a2131c22bc25a25dfde1de2ee75278a9411edcbd082e",
    "product_tool/normalization.py": "cb87283badfa65298628080632b93c9a3a675fec869d31b7c47f2208d19af829",
    "product_tool/resolution.py": "6c36dd33ce4bb38ad01773bef431db3391579946ae0ba2c93df6ac0a54cab391",
    "product_tool/display.py": "ab52ab7b2ecb389a68194e4802b08ba0547cafd04d110e0e5010f47b4742d81a",
    "product_tool/jobs.py": "a2f249b95ea811456ea51784f14db6eefab9d99572d31821f0b3aacefd3f4e2d",
    "product_tool/migrations.py": "25c7d474c4d2c10dcefc9357cf42d4cfa2a1bffc26819938d3c0926d74dcc35c",
    "data/batches.sqlite3": "8fa671efe7feb2794343af7fcdcc11a765736703c396f340436223dcfee51155",
}
PINNED_SHA256.update(STAGE48_MARKERS_PINNED_SHA256)

# Stage 48 output addendum: no production database or earlier report changed.
STAGE48_PROJECTION_PINNED_SHA256: dict[str, str] = {
    "product_tool/attribute_projection.py": "e958b0cb8f5fb8b02398be3b447aaefb769188d7ab8113f12cda2f2e1c6b5548",
    "product_tool/display.py": "95e8abc794c3279705f2867ca1bff687702cfdf9844930e83bcb7112c4bbe468",
    "product_tool/web.py": "522f8e6e698e9a93f8f88118edad0ca2d313b382f6ee5808501b706571f0401f",
    "product_tool/exporter.py": "22e352651bc7d13f4db526babb7e21492f6f41781cd31b0696792f2dffaf82e1",
}
PINNED_SHA256.update(STAGE48_PROJECTION_PINNED_SHA256)

# Stage 49: exact bytes after the limited identity replay and output labels.
STAGE49_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/lg.py": "4faffd036e09235fa9f0f1de74c5888cd345a66beb2a9d075de29b92c07551f4",
    "product_tool/worker.py": "d67ce5951b049bd98a5de3ce6c481a3b7cadba58063c08900c352f521e8f77e9",
    "product_tool/lg_batch.py": "9ede78c87b937fcaf33ec84242c277785e0ac046ceed4f4d5cd419ea5d8af5ba",
    "product_tool/exporter.py": "13ccf2dd76d4381d3daaed9607293b729ef852fdc668c80590505e81fe6745bb",
    "product_tool/web.py": "e16fb9edd8df75fb614f2ef6b7f4468ad1e086f3a5d0947fbd44141d57bbde42",
    "product_tool/templates/product.html": "0a39d85d89791897afb17c9cc79832241438cf7285a97ce9414002f05717cc70",
    "data/batches.sqlite3": "7abc181e610d0d49c3de74834f61b213cd4abeb16faea55bd1b57b679e4e4d18",
}
PINNED_SHA256.update(STAGE49_PINNED_SHA256)

# Stage 50: current protected-code bytes; older pins remain untouched.
STAGE50_PINNED_SHA256: dict[str, str] = {
    "product_tool/lg_batch.py": "a48695be1703294335dc9e6551a17d4027c9d23273c1090617fe7091021693de",
    "product_tool/exporter.py": "9e800be939e745374e7edb71ac0e54f6198db575573b584adbc5e8a23c5c306d",
    "product_tool/templates/product.html": "3880d35720cff6e2440da7f2245e2ba16b70538a02f6ed165069cd4245c8ba23",
}
PINNED_SHA256.update(STAGE50_PINNED_SHA256)

# Stage 51.1: exact protected worker bytes after the default DNS stop-log hookup.
STAGE51_1_PINNED_SHA256: dict[str, str] = {
    "product_tool/worker.py": "6ccc3d38315585e18db55cb2a497e5bf3fb384e04b9c73ddc34e9b6a664372d6",
}
PINNED_SHA256.update(STAGE51_1_PINNED_SHA256)


# Stage 52: exact protected bytes after the bounded quality fixes above.
STAGE52_PINNED_SHA256: dict[str, str] = {
    "product_tool/jobs.py": "f107a92ba07c70f950d39204ee83bfac137c65773248b5a194ce1f2705d9bf1c",
    "product_tool/worker.py": "0ea5186ce743a0c40dcea4a8fc47fe9edae27318b84b3568dc4482b49b533f34",
    "product_tool/adapters/lg.py": "859ce8d7303e3502aa8b4611e2d21b1ff00dfd3918ffc59ed8e9892e1d3b0fc6",
    "product_tool/adapters/lg_support.py": "1da9c2d39696956e579e6564c935aba952440da52c076303498d380b91c7a4dd",
}
PINNED_SHA256.update(STAGE52_PINNED_SHA256)

# Stage 52.1: exact protected UI bytes and the single-row production SQLite snapshot.
STAGE52_1_PINNED_SHA256: dict[str, str] = {
    "product_tool/web.py": "df896709e5ff60c8d425b6cc268708db4f77452f10572e4f11dbe3f659e3af85",
    "data/batches.sqlite3": "14c31793ece06bcf37186671885c35628bd28067a7df1770f77c595ec6512ac6",
}
PINNED_SHA256.update(STAGE52_1_PINNED_SHA256)


# Stage 53: exact bytes after the presentation and additive SQLite migration.
STAGE53_PINNED_SHA256: dict[str, str] = {
    'product_tool/adapters/lg_documents.py': '8168120dd7f7e3a7c93994965d1a7e731481a45ae008362d3a3a5cadd56a52d2',
    'product_tool/display.py': '14ff7a6842dbcfc0abeb973a97c7645d7e13a449418ae16e9e8347af5c1fd8b3',
    'product_tool/exporter.py': '814e494e54a32b40e6dcc936f97365aa2762c62a93dde4b8621eac24a7b7d791',
    'product_tool/jobs.py': '3e6d035dd4b48a087ab00a5fb59589ab99e094cb22efdbc3e2db342428326e4a',
    'product_tool/lg_batch.py': '37fb8b1dbc9e7e8b18a4d714904ffc2a7cc322da75c9fb173913514470e25a86',
    'product_tool/migrations.py': '16f97dbe341a03bf28b52f365225ca275f473aa169ef7c4bd930615f3ab54f8f',
    'product_tool/static/styles.css': '414b4e0a6b2a30bf46af84108a60a0c0b53cb7496677c9495a57c3a90deb2e17',
    'product_tool/templates/product.html': '567af93638e94314071f037ec9bef1d1bb94c97cdea5790fff2f3fc7b3fd3eed',
    'product_tool/web.py': 'bad509e4fc951558a24344616fffb7abcf1e567b1daebda0230f0913f1b21fa5',
    'product_tool/worker.py': 'fbe6f5d3898583b27192609f97af0234e302ed17cce54575196622991e422f70',
    'data/batches.sqlite3': '839fe7c3cbc57c4c118a44506a9ba36353be560cb24cf8948851171429ec5311',
}
PINNED_SHA256.update(STAGE53_PINNED_SHA256)

# Stage 53 UI completion: exact protected bytes; production SQLite is unchanged.
STAGE53_UI_PINNED_SHA256: dict[str, str] = {
    "product_tool/web.py": "51919b10aecbc5f5b5d41a58bff05d712fa3a588dee54e6d2aeac268f7d9e7c7",
    "product_tool/static/styles.css": "21a419d0b600010837b0199f95eacd47eb834c5b08f23cdf165ede1c3f2a33bb",
    "product_tool/templates/product.html": "f8265dbb783acc74bd37ccbf8cefb86c63929f63955555eca62c51acbf4acda2",
}
PINNED_SHA256.update(STAGE53_UI_PINNED_SHA256)

# Stage 53.1: live batch progress and the completed owner-created 12-job SQLite state.
STAGE53_1_PINNED_SHA256: dict[str, str] = {
    "product_tool/templates/batch.html": "a71cd1c1b0745b4c883bc7f8de457ea1c402e309e059dc4c2a4fbb0dc30118eb",
    "data/batches.sqlite3": "36c1b8156e2f781860566facde0f6cd14d133684e368764bb1cc9dba4636cfef",
}
PINNED_SHA256.update(STAGE53_1_PINNED_SHA256)

# Stage 54.1: exact bytes of the protected discovery and presentation files.
# The LG adapter pin includes the bounded Google fallback; the browser worker
# pin includes explicit HTTP 429 classification and its observed response URL.
# The worker pin includes the saved exact KZ/RU PDP gate that avoids an
# unnecessary Google fallback on a later transient source refresh.
STAGE54_1_PINNED_SHA256: dict[str, str] = {
    "product_tool/adapters/lg.py": "9c9dc1169ecf9c14e82e35f95cf67f78872ad006a5c4a980e9a767a3f784da88",
    "product_tool/census/browser_worker.py": "6b7e00218bafc80ac8f19df6e9f3fae2cee0617135d59fcbb63eafdf14ef0117",
    "product_tool/adapters/lg_support.py": "7b190aa236abc79886e8cca7422ceccdc47f9bf29868398652cd73e1bd8ffe28",
    "product_tool/display.py": "e50c90ea5c17b1fd9e245bfc2c8a429eaaacaf19c703c7ea2a8e741b63a91793",
    "product_tool/exporter.py": "ca474bff6dbd395c09df24d66f41260c1ac445ae11c75314890f1e21d7aaf999",
    "product_tool/jobs.py": "f5c2bb911b36b60736743efb49a2272e6d19fa4ead4eec8e3efa09fac294fc00",
    "product_tool/lg_batch.py": "692c1349b7a57956ca0ace495f4e085c59dd3b8a63084ed9c8350e7274753c4b",
    "product_tool/resolution.py": "1b119c3c01aec1e1781a688c4b9511f32bf1d6650b98e5dc6c41eaec29e24280",
    "product_tool/source_types.py": "80bf58f2f815ce4f43fa217ad2e5b5269b2aaec11ac99c8f1433a784486cdd21",
    "product_tool/worker.py": "0b51519d5c049e8786406a92726199badeed558166598ae10ca1bad54456428e",
}
PINNED_SHA256.update(STAGE54_1_PINNED_SHA256)

# Stage 54.2: the LG worker records an explicit exact KZ/RU provider skip and
# labels the sequential web-provider fallback without changing readiness gates.
STAGE54_2_PINNED_SHA256: dict[str, str] = {
    "product_tool/worker.py": "89a68c36fc6fc7141fa5b5e760ce6166c02f4e3aeef669422b3acafc44f77a6e",
    "product_tool/census/browser_worker.py": "dc5c444a0decd4b6da3a6891f60eacb1be688fb97061a02c5da3c179491c613f",
}
PINNED_SHA256.update(STAGE54_2_PINNED_SHA256)


# Stage 54.4: the worker inserts official LG sitemap discovery before web fallback.
STAGE54_4_PINNED_SHA256: dict[str, str] = {
    "product_tool/worker.py": "3ebb0e4d52a25b51db1aaf9ecd6c546c93f8d9f8f0327725f4bff03b31d455f4",
}
PINNED_SHA256.update(STAGE54_4_PINNED_SHA256)


# Stage 54.1: this database is the live application state, not a fixture.
# The Stage 53.1 digest remains an audit snapshot, while routine user uploads
# and worker jobs are validated by schema/integrity checks in test_live_db_invariants.
MUTABLE_RUNTIME_PATHS = frozenset({"data/batches.sqlite3"})


def check_migrated_file(path: str, actual_sha256: str) -> tuple[bool, str]:
    """Verify pinned files by SHA-256; validate live SQLite by invariants.

    The old database digest remains in the migration audit, while routine
    product uploads and job processing are expected to change its bytes.
    Returns (ok, message).
    """
    if path not in ALL_AUTHORIZED_CHANGES:
        return False, f"{path!r} is not part of the authorized Stage 11.4/11.5/12 migration."
    if path in MUTABLE_RUNTIME_PATHS:
        return True, f"{path!r} is mutable runtime state; verify schema and integrity separately."
    expected = PINNED_SHA256.get(path)
    if not expected:
        return False, f"{path!r} is listed as authorized but has no pinned post-migration hash recorded."
    if actual_sha256 != expected:
        return False, (
            f"{path!r} no longer matches its pinned post-migration hash "
            f"(expected {expected}, got {actual_sha256}) -- this is a NEW, "
            f"undocumented change made on top of the authorized migration, "
            f"and is not itself authorized just because the file was touched before."
        )
    return True, f"{path!r} matches its pinned post-migration hash."
