import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_4')

URL = "https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/"
MANUAL_URL = "https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf"
MANUAL_FINAL_URL = "https://downloadcenter.samsung.com/content/UM/201907/20190723164117830/MS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf"

evidence = {
    "schema_version": "stage8_4_evidence.v1",
    "item": "Samsung MS23K3614AK/BW (microwave oven, Solo)",
    "product_page_url": URL,
    "page_type": "Product page (JSON-LD Product confirmed, is_product_page=true) -- distinct source type from the separate downloadcenter.samsung.com document source below.",
    "canonical_url": URL,
    "canonical_matches_fetched_url": True,
    "fields": {
        "brand": {
            "value": "Samsung",
            "status": "confirmed",
            "evidence": "JSON-LD Product.brand = {\"@type\":\"Brand\",\"name\":\"Samsung\"} -- a direct brand-name field this time, not just an @id reference.",
            "source": "JSON-LD script tag on the product page",
        },
        "consumer_model_name": {
            "value": "23 Л Микроволновая печь Соло БИО-Керамическое покрытие",
            "status": "confirmed",
            "evidence": "JSON-LD Product.name, independently corroborated by the HTML <title> tag = '23 Л Микроволновая печь Соло БИО-Керамическое покрытие, Черный | Samsung Казахстан'.",
            "source": "JSON-LD Product.name + <title> tag",
        },
        "manufacturer_model_code": {
            "value": "MS23K3614AK/BW",
            "status": "confirmed_and_catalog_matched",
            "evidence": "JSON-LD Product.sku = 'MS23K3614AK/BW', an EXACT character-for-character match to the working catalog's own seller_article field for this row (data/catalog_2026-09-21_filtered.xlsx). Independently corroborated a third way by the manual download URL's own ModelName=MS23K3614AK query parameter.",
            "source": "JSON-LD Product.sku + catalog row cross-check + manual URL query parameter",
        },
        "color": {
            "value": "Черный (Black)",
            "status": "confirmed",
            "evidence": "Appears in the HTML <title> tag ('...Соло БИО-Керамическое покрытие, Черный | ...'), not the URL slug.",
            "source": "HTML <title> tag",
        },
        "volume": {
            "value": "23 л (usable cavity volume)",
            "status": "confirmed",
            "evidence": "'23 л' / 'Полезный объем рабочей камеры: 23 л' found twice in visible body text, plus '23 Л' repeated in the <title> tag and JSON-LD name. Also matches the catalog row's OWN alternate name field ('Микроволновая печь MS23K3614AK/BW, 23 л') -- a fourth independent confirmation.",
            "source": "Visible body text + <title> + JSON-LD name + catalog alt-name field",
        },
        "power_specs": [
            {"field": "power_consumption_microwave", "value": "1150 Вт", "status": "confirmed", "evidence": "'Потребляемая мощность (микроволны)' label followed by '1150 Вт' in visible body text."},
            {"field": "output_power_microwave", "value": "800 Вт", "status": "confirmed", "evidence": "'Выходная мощность (микроволны)' label followed by '800 Вт' in visible body text."},
        ],
        "specifications_completeness": {
            "status": "partial",
            "reasoning": "Structural contract (Stage 8's inspect_structure) records specifications.dom_semantics and .json_paths as empty (no table/dl/details, no JSON-LD additionalProperty) -- same static-rendering limitation seen on every other Samsung category checked so far. However, direct full-text search of the same static response DID surface 3 concrete, labeled specs with real values and units (volume, input power, output power). A fully exhaustive specifications sheet (dimensions, weight, turntable diameter, control type, etc.) was not confirmed reachable statically and is not claimed.",
        },
        "official_image": {
            "value": "https://images.samsung.com/is/image/samsung/kz-ru-ms23k3614akbw-ms23k3614ak-bw-frontblack-190178091?$1164_776_PNG$",
            "status": "confirmed",
            "evidence": "DOM img/source[srcset] advertised two explicit width variants of asset 190178091: 624x468 and 1164x776. The larger explicitly advertised variant was selected, per the project's existing 'largest advertised srcset candidate' rule.",
            "source": "responsive srcset attribute on the product page",
            "secondary_image_note": "JSON-LD Product.image separately references a different, smaller 'thumb' asset (id 190178092); the srcset gallery image (190178091, larger) was preferred as the primary card image.",
        },
        "instruction_manual": {
            "value": MANUAL_FINAL_URL,
            "status": "confirmed_reachable_first_party",
            "url": MANUAL_URL,
            "final_url_after_redirect": MANUAL_FINAL_URL,
            "redirect_chain": [MANUAL_URL, MANUAL_FINAL_URL],
            "first_party": True,
            "first_party_evidence": "Both org.downloadcenter.samsung.com and its redirect target downloadcenter.samsung.com are samsung.com subdomains, directly linked from the already-verified product page (not invented, not guessed).",
            "content_verification": "Fetched and confirmed the response begins with the PDF magic bytes '%PDF-1.6' (1,431,426 bytes read, under the 1.5MB probe cap) -- this is a genuine, reachable PDF file, not a broken or placeholder link.",
            "document_type": "User Manual (UM)",
            "document_type_evidence": "The link's own query parameter CDCttType=UM is Samsung's own document-type code (as opposed to, e.g., a delivery-terms or marketing PDF) -- this is first-party structured evidence, not an inferred guess from the filename alone.",
            "model_linkage_evidence": "The link's own ModelName=MS23K3614AK query parameter exactly matches this product's manufacturer model code (matching the JSON-LD sku's model portion) -- direct first-party evidence of model linkage, stronger than the generic 'a[href:pdf]' structural signal alone.",
            "language": "Multi-language file whose name lists RU-UK-KK-UZ (Russian, Ukrainian, Kazakh, Uzbek), Russian listed first -- matches the project's stated language priority (Russian first). This is inferred from Samsung's own filename convention and the CDSite=UNI_KZ_RU site parameter, NOT from opening/parsing the PDF's internal text -- the PDF's actual internal-page language was not verified beyond this first-party filename/query-parameter evidence, since no PDF text-extraction capability exists in the current pipeline and building one was out of this stage's scope.",
        },
    },
    "requests_used_for_this_item": 3,
    "requests_detail": [
        "Fetch 1: product page URL -- extracted JSON-LD (brand/name/sku/image), <title>, canonical, PDF links, srcset image candidates, and spec body text in a single pass (learning from Stage 8.3's need for 2 passes, this stage captured everything needed in one fetch).",
        "Fetch 2: manual URL with an initially too-narrow allowed_hosts -- rejected as a regional_redirect because the real redirect target (downloadcenter.samsung.com, without the 'org.' prefix) wasn't yet in the allow-list. No content was retrieved on this attempt; recorded honestly rather than hidden.",
        "Fetch 3: manual URL retried with the already-OBSERVED redirect target host added to allowed_hosts (not a new/invented domain -- taken directly from fetch 2's own redirect_chain) -- confirmed a real PDF via magic-byte check.",
    ],
}
json.dump(evidence, open(OUT / 'evidence.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

card_summary = {
    "schema_version": "stage8_4_card_summary.v1",
    "pilot_scope": "1 catalog-matched item: Samsung MS23K3614AK/BW microwave oven. Galaxy Buds3 FE has no catalog row (see buds3fe_catalog_check.json) and is not re-worked here. S20 FE / Z Fold3 / N5300 not revisited.",
    "items": [
        {
            "item": "Samsung MS23K3614AK/BW (microwave oven)",
            "catalog_identity": "Exact match: seller_article 'MS23K3614AK/BW', catalog name 'Микроволновая печь MS23K3614AK/BW', alt name includes '23 л' -- independently confirmed by the official page's own volume spec.",
            "official_url": URL,
            "page_type": "Product page (JSON-LD Product confirmed)",
            "model_variant_status": "exact_variant",
            "model_variant_status_reasoning": "Model code (MS23K3614AK/BW) confirmed via JSON-LD sku, exactly matching the catalog row AND the manual's ModelName parameter (3 independent sources). Color (Black/Черный) confirmed via on-page <title> text, not URL. Both model and the variant-defining color field are independently on-page confirmed.",
            "specifications": "Partial: volume (23 l), input power (1150 W), output power (800 W) confirmed via body text with labels and units. No exhaustive spec sheet reached.",
            "images": "1 official image confirmed: 1164x776 PNG, images.samsung.com, largest explicitly advertised srcset candidate.",
            "instruction_manual": "Found and confirmed reachable: a genuine, first-party User Manual PDF (Samsung's own CDCttType=UM code), model-linked via the URL's own ModelName parameter, confirmed as real PDF content via magic-byte check.",
            "instruction_language": "Multi-language filename listing RU-UK-KK-UZ, Russian first -- inferred from Samsung's own filename/query-parameter convention, not from parsing the PDF's internal text (no PDF text-extraction capability in the current pipeline).",
            "evidence_reference": "evidence.json#fields",
            "gaps": [
                "No exhaustive specifications table (dimensions, weight, turntable size, control type not confirmed)",
                "Manual's internal-page language not verified by opening/parsing the PDF itself, only by first-party filename/query-parameter evidence",
                "Regional suffix meaning in the sku (the 'BW' portion) not independently decoded beyond its presence in the sku/catalog fields",
            ],
            "conflicts": [],
            "card_export_readiness": "mostly_ready -- identity (exact_variant, catalog-matched), one official image, a partial-but-real spec set, and a confirmed-reachable model-linked manual are all evidence-backed and export-ready. Only spec completeness and manual-language depth remain open, non-blocking gaps.",
        },
    ],
    "buds3fe_status": {
        "item": "Galaxy Buds3 FE",
        "catalog_identity": "No matching row found in data/catalog_2026-09-21_filtered.xlsx (offline check, see buds3fe_catalog_check.json).",
        "disposition": "Stage 8.3's evidence stands unchanged as a verified official-source fixture (exact_variant identity, 1 image, no manual found) without a catalog-linked card. No new requests were made for this item this stage.",
    },
}
json.dump(card_summary, open(OUT / 'card_summary.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

documents = {
    "schema_version": "stage8_4_documents.v1",
    "documents_found_and_relevant": [
        {
            "item": "Samsung MS23K3614AK/BW",
            "url": MANUAL_URL,
            "final_url": MANUAL_FINAL_URL,
            "first_party": True,
            "title": "User Manual (Samsung's own CDCttType=UM code; filename MS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf)",
            "document_type": "User Manual",
            "language": "RU-UK-KK-UZ per filename (Russian first) -- filename/query-parameter evidence only, PDF internal text not parsed",
            "model_or_family": "MS23K3614AK/BW (exact -- ModelName query parameter matches the product's own sku)",
            "date_or_version": "Path segment '201907' in the VPath parameter suggests a July 2019 document version; not independently confirmed beyond this URL path evidence",
            "discovery_method": "Found directly on the already-verified product page (a[href] matching .pdf pattern)",
            "evidence_of_model_linkage": "URL query parameter ModelName=MS23K3614AK matches the product's JSON-LD sku exactly",
        }
    ],
    "documents_found_but_excluded": [
        {
            "url": "https://images.samsung.com/is/content/samsung/assets/in/info/installation/Delivery-Service-TnC.pdf",
            "reason_excluded": "Same generic delivery-terms document already seen on the Galaxy Buds3 FE page (Stage 8.3) -- not model-specific, not a manual.",
        }
    ],
    "note": "Unlike Stage 8.3 (no manual found for Galaxy Buds3 FE), this item's manual was found, confirmed reachable, and confirmed as real PDF content. Per instructions, 'instruction not found' is never conflated with 'instruction does not exist' -- here an instruction WAS found, so no such caveat applies to this item; it still applies to Galaxy Buds3 FE (Stage 8.3) and is not restated as a new finding here.",
}
json.dump(documents, open(OUT / 'documents.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

print('wrote evidence.json, card_summary.json, documents.json')
