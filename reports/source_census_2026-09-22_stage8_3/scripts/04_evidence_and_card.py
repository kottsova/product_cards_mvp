import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_3')

URL = "https://www.samsung.com/kz_ru/audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/"

evidence = {
    "schema_version": "stage8_3_evidence.v1",
    "item": "Galaxy Buds3 FE (Samsung)",
    "product_page_url": URL,
    "page_type": "Product page (JSON-LD Product object confirmed, is_product_page=true) -- NOT a support/listing page. Kept as a distinct source type from any support.samsung.com/support-path evidence.",
    "canonical_url": URL,
    "canonical_matches_fetched_url": True,
    "fields": {
        "brand": {
            "value": "Samsung",
            "status": "confirmed",
            "evidence": "JSON-LD Product.brand.@id = 'https://www.samsung.com/kz_ru/#brand-galaxy' and Product.manufacturer.@id = 'https://www.samsung.com/#org', both first-party samsung.com identifiers.",
            "source": "JSON-LD script tag on the product page",
        },
        "family_name": {
            "value": "Galaxy Buds",
            "status": "confirmed",
            "evidence": "URL path segment /audio-sound/galaxy-buds/ (category tree) plus JSON-LD Product.name prefix 'Galaxy Buds3 FE'.",
            "source": "Page URL structure + JSON-LD",
        },
        "consumer_model_name": {
            "value": "Galaxy Buds3 FE",
            "status": "confirmed",
            "evidence": "JSON-LD Product.name = 'Galaxy Buds3 FE'; independently corroborated by the HTML <title> tag = 'Galaxy Buds3 FE | Черный | Samsung Казахстан'. Two independent on-page sources, not URL text.",
            "source": "JSON-LD Product.name + <title> tag",
        },
        "manufacturer_model_code": {
            "value": "SM-R420NZKACIS",
            "status": "confirmed",
            "evidence": "JSON-LD Product.sku = 'SM-R420NZKACIS'. The SM-R4xx prefix matches Samsung's publicly known Galaxy Buds numbering convention (e.g. SM-R400 = Buds FE, SM-R510 = Buds2 Pro), corroborating this is a genuine manufacturer code, not an arbitrary internal catalog SKU -- though this specific cross-check against Samsung's full official code registry was not independently re-verified beyond the pattern match.",
            "source": "JSON-LD Product.sku",
        },
        "regional_suffix": {
            "value": "KACIS",
            "status": "confirmed_present_meaning_not_independently_verified",
            "evidence": "Trailing segment of the JSON-LD sku value. Consistent with Samsung's general regional-suffix pattern (seen elsewhere in this project's evidence, e.g. catalog articles ending 'SKZ'), but this stage did not independently confirm what 'KACIS' specifically denotes (e.g. exact market/channel) beyond it being part of the on-page sku field.",
            "source": "JSON-LD Product.sku (suffix)",
        },
        "color": {
            "value": "Черный (Black)",
            "status": "confirmed",
            "evidence": "Appears in the HTML <title> tag ('...| Черный | ...') and repeated multiple times in the visible page body text ('Черный'), independent of the URL slug. Per instructions, the URL slug alone ('...-black-...') was NOT used as evidence; only the on-page title/body text occurrences were counted.",
            "source": "HTML <title> tag + visible body text (2+ independent occurrences)",
        },
        "storage": {
            "value": None,
            "status": "not_applicable",
            "evidence": "Galaxy Buds do not carry a user-selectable storage/memory variant; no storage field is expected or claimed.",
            "source": None,
        },
        "connectivity": {
            "value": "Bluetooth v5.4",
            "status": "confirmed",
            "evidence": "Two occurrences of 'Версия Bluetooth' / 'Bluetooth v5.4' found in the visible page body text.",
            "source": "Visible body text (plain HTML, not a structured table/dl/details element -- specifications.dom_semantics was empty in Stage 8.2's structural contract, meaning this text exists outside the patterns that census specifically looks for)",
        },
        "other_variant_or_spec_fields": [
            {
                "field": "water_dust_resistance",
                "value": "IP54",
                "status": "confirmed",
                "evidence": "'класс защиты от воды и пыли IP54' found in visible body text.",
            },
            {
                "field": "active_noise_cancellation",
                "value": "present (marketing description, no numeric spec)",
                "status": "confirmed_qualitative_only",
                "evidence": "'Активное шумоподавление минимизирует посторонние шумы' found in visible body text -- confirms the feature exists, but no dB or numeric ANC spec was found.",
            },
        ],
        "full_specifications_table": {
            "status": "insufficient",
            "reasoning": "Stage 8.2's structural contract already recorded specifications.dom_semantics as empty (no table/dl/details markup) and specifications.json_paths as empty (no JSON-LD additionalProperty). This stage's direct full-text search confirms individual spec facts exist as plain body text (Bluetooth version, IP rating, ANC), but found no comprehensive specifications table/list -- Samsung's full 'characteristics' tab is very likely rendered client-side, consistent with every other Samsung category checked in Stage 8.2.1/8.2.2. Card export can use the individually confirmed facts above but cannot claim a complete specifications set.",
        },
        "official_image": {
            "value": "https://images.samsung.com/is/image/samsung/p6pim/kz_ru/sm-r420nzkacis/gallery/kz-ru-galaxy-buds3-fe-sm-r420nzkacis-548910327?$1164_776_PNG$",
            "status": "confirmed",
            "evidence": "DOM img/source[srcset] on the product page advertised two explicit width variants of the same gallery asset (548910327): 624x468 and 1164x776. The larger explicitly advertised variant was selected, per the project's existing 'select the largest explicitly advertised srcset candidate' rule -- no CDN transform was invented.",
            "source": "responsive srcset attribute on the product page",
            "secondary_image_note": "JSON-LD Product.image separately references a DIFFERENT asset id (548910328, a 'thumb' rendition) -- both are legitimate first-party images.samsung.com URLs; the srcset gallery image (327, larger) was preferred as the primary card image over the JSON-LD thumb (328).",
        },
        "instruction_manual": {
            "value": None,
            "status": "not_found",
            "evidence": "The only PDF link found on the product page (https://images.samsung.com/is/content/samsung/assets/in/info/installation/Delivery-Service-TnC.pdf, anchor text 'Click here') is a delivery-service Terms & Conditions document -- first-party (images.samsung.com) but NOT model-specific and NOT a user manual. It is explicitly excluded from being reported as an instruction. No product manual/user guide link was found on this page within budget.",
            "support_route_note": "A further support-first search specifically for this model's manual was considered but not attempted: Stage 8.2.2 already exhaustively proved (5 independent route types, 6 requests) that the entire kz_ru support surface renders client-side regardless of the model searched. Spending further budget to re-prove the same wall for a different model was judged low-value and was not done.",
        },
        "documents_language_available": "none (no document found)",
    },
    "requests_used_for_this_item": 2,
    "requests_detail": [
        "Fetch 1: same product page URL -- extracted JSON-LD (name/sku/image) and the delivery-terms PDF link.",
        "Fetch 2: same product page URL, second pass -- extracted <title>, canonical link, color/connectivity/spec body text, and embedded-state script evidence (none found). Two passes were needed only because the census pipeline's raw HTML is never persisted between requests, so all extraction needs had to be identified up front or covered by a second pass.",
    ],
}
json.dump(evidence, open(OUT / 'evidence.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

card_summary = {
    "schema_version": "stage8_3_card_summary.v1",
    "pilot_scope": "Galaxy Buds3 FE only. TV (UE43N5300AUXCE) excluded per novelty rule -- see tv_selection_check.json. Galaxy S20 FE / Galaxy Z Fold3 (Stage 8.2.2) intentionally not revisited.",
    "items": [
        {
            "item": "Galaxy Buds3 FE",
            "catalog_identity": "No matching row in data/catalog_2026-09-21_filtered.xlsx (this item was reached via Samsung's own live sitemap, not derived from a specific seller catalog row -- consistent with Stage 8.2's own finding).",
            "official_url": URL,
            "page_type": "Product page (JSON-LD Product confirmed)",
            "model_variant_status": "exact_variant",
            "model_variant_status_reasoning": "Model name (Galaxy Buds3 FE) confirmed via 2 independent on-page sources (JSON-LD + <title>); manufacturer code (SM-R420NZKACIS) confirmed via JSON-LD sku; color (Черный/Black) confirmed via <title> + repeated body text, not URL alone. All three (model, code, variant-defining color) independently confirmed on-page -- satisfies exact_variant, not merely exact_model.",
            "specifications": "Partial: Bluetooth v5.4, IP54 water/dust resistance, active noise cancellation (qualitative) confirmed via body text. No comprehensive specifications table reached (likely client-rendered).",
            "images": "1 official image confirmed: 1164x776 PNG, images.samsung.com, largest explicitly advertised srcset candidate.",
            "instruction_manual": "Not found. Only a non-model-specific delivery-terms PDF was found and explicitly excluded.",
            "instruction_language": "n/a (no document found)",
            "evidence_reference": "evidence.json#items[Galaxy Buds3 FE]",
            "gaps": [
                "No full specifications table (client-rendered, out of current pipeline's static-HTTP capability)",
                "No official instruction/manual document",
                "No corresponding row in the working seller catalog -- this card cannot be linked to a specific customer SKU",
                "Regional suffix 'KACIS' meaning not independently verified beyond its presence in the sku field",
            ],
            "conflicts": [],
            "card_export_readiness": "partially_ready -- identity, one official image and a partial spec set are export-ready with full evidence; specifications completeness and instructions are open gaps that block a fully complete card.",
        },
        {
            "item": "Samsung TV (UE43N5300AUXCE)",
            "catalog_identity": "n/a -- excluded before identity work began",
            "official_url": "https://www.samsung.com/kz_ru/tvs/full-hd-tv/n5300-43-inch-full-hd-smart-tv-ue43n5300auxce/",
            "page_type": "Product page (JSON-LD Product confirmed in Stage 8.2) -- verification not extended in this stage",
            "model_variant_status": "not_evaluated",
            "specifications": "not_evaluated",
            "images": "not_evaluated",
            "instruction_manual": "not_evaluated",
            "instruction_language": "not_evaluated",
            "evidence_reference": "tv_selection_check.json",
            "gaps": ["excluded from pilot before any card-building work: see tv_selection_check.json for full reasoning"],
            "conflicts": [],
            "card_export_readiness": "excluded_from_pilot",
        },
    ],
}
json.dump(card_summary, open(OUT / 'card_summary.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

documents = {
    "schema_version": "stage8_3_documents.v1",
    "documents_found_and_relevant": [],
    "documents_found_but_excluded": [
        {
            "url": "https://images.samsung.com/is/content/samsung/assets/in/info/installation/Delivery-Service-TnC.pdf",
            "final_url": "https://images.samsung.com/is/content/samsung/assets/in/info/installation/Delivery-Service-TnC.pdf",
            "first_party": True,
            "first_party_evidence": "images.samsung.com is Samsung's own CDN, used elsewhere in this project's evidence for official product imagery (see evidence.json official_image field).",
            "title": "Delivery Service Terms & Conditions (inferred from filename; anchor text was generic 'Click here')",
            "document_type": "delivery/legal terms, not a product manual",
            "language": "unknown_do_not_infer_from_locale (per existing project rule; not opened to check)",
            "model_or_family": "none -- generic delivery terms, not associated with Galaxy Buds3 FE or any specific model",
            "date_or_version": "not available (document was not opened)",
            "discovery_method": "found directly on the Galaxy Buds3 FE product page (a[href] matching .pdf pattern)",
            "evidence_of_model_linkage": "none -- excluded specifically because there is no evidence connecting this document to the model",
            "reason_excluded": "Not a product manual/instruction and not model-specific; reported here for completeness/transparency, not counted as a found instruction.",
        }
    ],
    "note": "No official instruction manual was found for Galaxy Buds3 FE within this stage's budget. See evidence.json's instruction_manual field for the support-route reasoning.",
}
json.dump(documents, open(OUT / 'documents.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

print('wrote evidence.json, card_summary.json, documents.json')
