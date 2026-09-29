import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_4')

candidate_selection = {
    "schema_version": "stage8_4_candidate_selection.v1",
    "excluded_models": ["Galaxy S20 FE", "Galaxy Z Fold3", "N5300 (Samsung TV)"],
    "excluded_models_reason": "Explicitly out of scope per instructions -- no request or catalog lookup this stage mentions any of the three.",
    "category_rule_applied": "Selection rule: smartphones/tablets/wearables require verifiable evidence of currency (no arbitrary year threshold); home appliances ('бытовая техника') may be old models without further justification.",
    "category_chosen": "Микроволновые печи (microwave ovens) -- home appliances",
    "why_this_category": (
        "Choosing an appliance category sidesteps the harder 'is this a novelty' judgment entirely (the rule explicitly permits old appliance "
        "models), and Samsung's own site taxonomy already confirms microwave ovens sit under da-sitemap.xml (digital appliances), the same "
        "branch already established in Stage 8.2.1/8.3 as distinct from TVs/audio and requiring its own Product page fixture before being "
        "treated as pilot-ready. This choice both respects the selection rule cleanly and extends real evidence coverage to a category that had "
        "none yet."
    ),
    "novelty_evidence_required": False,
    "novelty_evidence_reasoning": "Not required for this category under the stated rule (appliances may be old). No currency/release-date claim is made about this model, and none is needed.",
    "discovery_method": (
        "Fully offline: Stage 8.2.1's da-sitemap.xml link index (reports/source_census_2026-09-22_stage8_2_1/link_index/samsung_da_sitemap.json, "
        "300 links, already fetched in a prior stage) was checked for a 'microwave-ovens' segment (37 links found there). Those links were then "
        "cross-referenced offline against the catalog's 58 Samsung 'Микроволновые печи' rows by exact model-code match (case/slash-insensitive). "
        "Exactly one clean, unambiguous match was found: catalog article 'MS23K3614AK/BW' against sitemap URL "
        ".../microwave-ovens/solo/ms23k3614akbw/ -- zero new requests were needed to find this candidate."
    ),
    "candidate": {
        "catalog_brand": "Samsung",
        "catalog_category": "Микроволновые печи",
        "seller_article": "MS23K3614AK/BW",
        "catalog_name": "Микроволновая печь MS23K3614AK/BW",
        "catalog_alt_names": "Микроволновая печь MS23K3614AK/BW, 23 л | Микроволновая печь Samsung MS23K3614AK/BW",
        "wb_articles": "111651674; 289550151; 312920006; 445326594; 657983161",
        "row_repeat_count": 5,
    },
    "ambiguous_categories_avoided": (
        "Tablets (Планшеты, 39 catalog rows) and the wearables the catalog has no further entries for beyond the already-excluded Buds "
        "family were NOT chosen for this pilot, specifically because they would require the harder, evidence-based novelty judgment this "
        "stage's instructions caution against guessing at -- an appliance candidate was preferred to keep the selection unambiguous."
    ),
}
json.dump(candidate_selection, open(OUT / 'candidate_selection.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote candidate_selection.json')
