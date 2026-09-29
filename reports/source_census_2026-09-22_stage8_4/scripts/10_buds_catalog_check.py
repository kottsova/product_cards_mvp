import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_4')

buds_catalog_check = {
    "schema_version": "stage8_4_buds3fe_catalog_check.v1",
    "purpose": "Offline-only check of data/catalog_2026-09-21_filtered.xlsx for a Galaxy Buds3 FE row, before deciding what (if any) targeted requests are needed for that item.",
    "catalog_read_only": True,
    "search_terms_used": ["sm-r420", "r420nzkacis", "r420n", "buds3 fe", "buds 3 fe", "buds3fe", "бадс3 fe", "бадс 3 fe"],
    "search_scope": "Товары sheet: Бренд, Артикул продавца, Наименование, Альтернативные наименования columns, case-insensitive, ё normalized to е",
    "false_positive_noted": "A naive substring search for 'r420' alone also matches unrelated article codes such as Xiaomi's 'BHR4208GL' (contains 'r420' as a coincidental substring); the precise search used here requires the fuller 'sm-r420' or 'r420nzkacis'/'r420n' forms specifically to avoid this kind of false match, and no Xiaomi/other-brand row was treated as a Samsung Buds3 FE candidate.",
    "result": "no_match_found",
    "closest_existing_samsung_audio_rows": [
        {"seller_article": "SM-R177NLVACISSM-R177NLVACIS", "name": "Беспроводные наушники Galaxy Buds2"},
        {"seller_article": "SM-R177NZGACISSM-R177NZGACIS", "name": "Беспроводные наушники Galaxy Buds2"},
        {"seller_article": "SM-R177NZWACISSM-R177NZWACIS", "name": "Беспроводные наушники Galaxy Buds2"},
    ],
    "closest_rows_not_used_as_substitute": "Per instructions, an exact match is never replaced by a similar model. Galaxy Buds2 (SM-R177N...) is a different, older product than Galaxy Buds3 FE (SM-R420N...) and was not treated as a match, a substitute, or evidence for the Buds3 FE card.",
    "consequence": "No catalog row exists for Galaxy Buds3 FE. Per instructions, Stage 8.3's evidence stands as a verified OFFICIAL SOURCE fixture (Samsung's own product page, exact_variant identity, confirmed image, confirmed absence of an instruction manual on that page) without a corresponding catalog-linked card. No gap-closing requests were made for this item this stage -- there is no catalog variant to reconcile gaps against, and Stage 8.3's own evidence already answered every field this stage would have checked (identity, one image, partial specs, manual absence).",
}
json.dump(buds_catalog_check, open(OUT / 'buds3fe_catalog_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote buds3fe_catalog_check.json')
