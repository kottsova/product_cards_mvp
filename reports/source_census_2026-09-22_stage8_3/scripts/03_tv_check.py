import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_3')

tv_check = {
    "schema_version": "stage8_3_tv_selection_check.v1",
    "candidate_url": "https://www.samsung.com/kz_ru/tvs/full-hd-tv/n5300-43-inch-full-hd-smart-tv-ue43n5300auxce/",
    "confirmed_in": "Stage 8.2 (product_page_fixture_result=verified)",
    "project_novelty_criterion_search": {
        "searched": ["product_tool/config/*.json", "docs/*.md", "reports/**/*.md (grep for новинк*)"],
        "result": "No project-defined 'novelty' / release-recency threshold exists anywhere in the repository.",
        "consequence_per_instructions": "Since no accepted project criterion is defined, this stage does NOT invent a novelty threshold and does NOT declare a disputed model 'new'. The TV is evaluated only against objective, directly observable evidence already on record.",
    },
    "objective_evidence_against_novelty": [
        {
            "signal": "URL category segment",
            "value": "/tvs/full-hd-tv/",
            "interpretation": "Samsung's own site taxonomy (vd-sitemap.xml, Stage 8.2.1) separates 'full-hd-tv' from its current premium tiers observed in the same sitemap: crystal-uhd, and (from the TV list sampled) oled/nanocell/lifestyle-tvs product lines. Full HD (1080p, non-4K) is Samsung's legacy/entry resolution tier; it is not how Samsung markets any current-generation (2024-2026) television.",
        },
        {
            "signal": "Model code prefix",
            "value": "UE43N5300AUXCE (model 'N5300')",
            "interpretation": "Samsung's own public TV model-year lettering convention places the 'N' prefix at the 2018 TV generation (contemporaries: NU7100, N5300, N4300 etc. were 2018-era Full HD/UHD lines). This is Samsung's own established public numbering scheme, not a threshold invented by this stage.",
        },
        {
            "signal": "Still present in the live b2c-sitemap.xml (Stage 8.2.1)",
            "value": "true",
            "interpretation": "Being listed in the current live catalog only shows the page is still reachable/sellable (e.g. as clearance/legacy stock in some markets); it does not by itself establish the model as a current release.",
        },
    ],
    "comparison_point": {
        "signal": "Galaxy Buds3 FE, by contrast",
        "note": "Found in the same live im-sitemap.xml audio-sound section; the same category page (Stage 8.2.1) also lists 'galaxy-buds4-pro' as a link, i.e. Buds3 FE sits one generation behind Samsung's newest buds line but within the actively-marketed current range -- unlike the TV, there is no premium/legacy tier split visible for it (Samsung is not simultaneously selling a materially newer Buds generation under a different quality tier the way it sells Crystal UHD/QLED/OLED above Full HD for TVs).",
    },
    "decision": "exclude_from_pilot",
    "reasoning": (
        "Per the selection rule (novelties only for smartphones/tablets/wearables; old models permitted only within home appliances), "
        "and per Samsung's own site taxonomy, this TV (a) is not a home appliance (Samsung's own da-sitemap.xml, i.e. digital appliances, "
        "is a separate branch from vd-sitemap.xml/TVs -- confirmed in Stage 8.2.1) and so does not qualify for the 'old models allowed' "
        "exemption, and (b) shows two independent, objective signals of being a legacy (2018) entry-tier model, not a current release. "
        "No project-defined novelty threshold exists to appeal to, so this determination rests on the objective evidence above, not an "
        "invented cutoff. Per the task's explicit fallback instruction, no further search for a replacement TV model was performed -- "
        "existing fixtures were checked (this file's 'no_other_fixture_found' section) and none qualify."
    ),
    "no_other_fixture_found": {
        "checked": [
            "reports/source_census_2026-09-22_stage8_2/product_page_fixtures.json (product_page_fixture_result=verified entries)",
            "reports/source_census_2026-09-22_stage8_2_1/product_page_fixtures.json (candidate only, not verified: Galaxy S25 Ultra, Galaxy S26 Ultra pages -- both is_product_page=false, no structured identity)",
            "reports/source_census_2026-09-22_stage8_2_2/ (no product pages at all -- support-only pages, all client-rendered)",
        ],
        "result": "Only two verified Samsung Product page fixtures exist in total: the excluded TV and Galaxy Buds3 FE. No substitute new-model fixture is available.",
    },
    "pilot_scope_consequence": "Pilot proceeds with Galaxy Buds3 FE only. This is a deliberate scope reduction, not a search failure.",
}
json.dump(tv_check, open(OUT / 'tv_selection_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote tv_selection_check.json')
