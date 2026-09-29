import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_5')

URL = "https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/"
MANUAL_URL = "https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf"
MANUAL_FINAL_URL = "https://downloadcenter.samsung.com/content/UM/201907/20190723164117830/MS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf"
IMAGE_URL = "https://images.samsung.com/is/image/samsung/kz-ru-ms23k3614akbw-ms23k3614ak-bw-frontblack-190178091?$1164_776_PNG$"

specs_completeness = {
    "schema_version": "stage8_5_specs_completeness.v1",
    "source": "Stage 8.4 evidence.json + this stage's broader re-scan (specs_recheck.json) of the same already-confirmed product page",
    "confirmed_with_evidence": [
        {"field": "usable_cavity_volume", "value": "23 л", "evidence": "Label 'Полезный объем рабочей камеры' + value '23 л' found together in body text; independently corroborated by <title>, JSON-LD name, and the catalog row's own alt-name field."},
        {"field": "power_consumption_microwave", "value": "1150 Вт", "evidence": "Label 'Потребляемая мощность (микроволны)' + value '1150 Вт' found together in body text."},
        {"field": "output_power_microwave", "value": "800 Вт", "evidence": "Label 'Выходная мощность (микроволны)' + value '800 Вт' found together in body text."},
        {"field": "color", "value": "Черный (Black)", "evidence": "HTML <title> tag."},
        {"field": "oven_type", "value": "Соло (Solo, no grill/convection)", "evidence": "<title> tag text '...Микроволновая печь Соло...' and URL category path /microwave-ovens/solo/."},
    ],
    "labels_found_but_value_not_confirmed": [
        {"field": "weight", "label_seen": "Вес / Вес нетто / Вес (в упаковке)", "status": "label_present_value_not_found_in_static_text"},
        {"field": "product_dimensions", "label_seen": "Размеры изделия (ШxВxГ)", "status": "label_present_value_not_found_in_static_text"},
        {"field": "turntable_dimensions", "label_seen": "Размеры вращающегося столика", "status": "label_present_value_not_found_in_static_text"},
        {"field": "control_type", "label_seen": "Тип управления / Интуитивное управление / Функции управления", "status": "label_present_value_not_found_in_static_text"},
        {"field": "auto_programs", "label_seen": "Автопрограммы", "status": "label_present_value_not_found_in_static_text"},
        {"field": "power_levels_count", "label_seen": "Кол-во уровней мощности", "status": "label_present_value_not_found_in_static_text"},
        {"field": "defrost_modes", "label_seen": "Разморозка (авто/быстрая/сенсорная), Авторазморозка (вес)/Разморозка (время)", "status": "label_present_value_not_found_in_static_text"},
        {"field": "sound_toggle", "label_seen": "Звук Включен/Выключен", "status": "label_present_value_not_found_in_static_text"},
    ],
    "interpretation": (
        "A second, broader text scan of the same product page found the LABEL text for 8 additional characteristics (weight, dimensions, "
        "turntable size, control type, auto-programs, power levels, defrost modes, sound toggle) but no adjacent value for any of them in "
        "the static HTML response. This is consistent with this whole investigation's repeated finding (Buds3 FE in Stage 8.3, this same "
        "page in Stage 8.4) that Samsung's full characteristics/specifications panel renders client-side: the label shell appears to be "
        "present statically while the populated values are injected by JavaScript. Per instructions, no value is invented for these fields "
        "-- they are listed here explicitly as unknown, not silently omitted."
    ),
    "important_characteristics_still_unknown": [
        "Physical weight (net and packaged)",
        "Physical dimensions (width x height x depth)",
        "Turntable diameter",
        "Control type / interface (mechanical dial vs. touch/electronic)",
        "Number of auto-programs and power levels",
        "Full defrost mode list",
    ],
}
json.dump(specs_completeness, open(OUT / 'specs_completeness.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

image_verification = {
    "schema_version": "stage8_5_image_verification.v1",
    "image_url": IMAGE_URL,
    "belongs_to_this_model": {
        "status": "confirmed",
        "evidence": [
            "The URL was advertised via the product page's own responsive srcset (Stage 8.4), not guessed or invented.",
            "The URL's own filename encodes the exact model code twice ('ms23k3614akbw' and 'ms23k3614ak-bw') and the confirmed color ('frontblack') -- on-page-linked, not an isolated/unrelated asset URL.",
        ],
    },
    "fit_for_card_use": {
        "status": "confirmed",
        "evidence": "Live fetch this stage: HTTP 200, Content-Type: image/png, magic bytes 89 50 4E 47 0D 0A 1A 0A (valid PNG header), 491,012 bytes read, NOT truncated (well under the 1.5MB cap) -- a genuine, complete, undamaged image file, not a broken link or placeholder.",
    },
    "resolution_selected": "1164x776 PNG, the larger of two explicitly advertised srcset widths (624x468 and 1164x776 of the same asset id 190178091) -- per the project's existing 'largest advertised candidate' rule.",
}
json.dump(image_verification, open(OUT / 'image_verification.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

card = {
    "schema_version": "stage8_5_card.v1",
    "item": "Samsung MS23K3614AK/BW (microwave oven, Solo)",
    "catalog_row": {
        "seller_article": "MS23K3614AK/BW",
        "catalog_name": "Микроволновая печь MS23K3614AK/BW",
        "catalog_alt_name": "Микроволновая печь MS23K3614AK/BW, 23 л | Микроволновая печь Samsung MS23K3614AK/BW",
    },
    "fields": {
        "brand": {"value": "Samsung", "status": "confirmed", "url": URL, "evidence": "JSON-LD Product.brand.name = 'Samsung'"},
        "model_name": {"value": "23 Л Микроволновая печь Соло БИО-Керамическое покрытие", "status": "confirmed", "url": URL, "evidence": "JSON-LD Product.name + <title> tag"},
        "manufacturer_model_code": {"value": "MS23K3614AK/BW", "status": "confirmed", "url": URL, "evidence": "JSON-LD Product.sku, exact match to catalog seller_article (independent source) and to the manual URL's ModelName parameter (independent source, linkage-only)"},
        "color": {"value": "Черный (Black)", "status": "confirmed", "url": URL, "evidence": "HTML <title> tag, not URL text"},
        "volume": {"value": "23 л", "status": "confirmed", "url": URL, "evidence": "Body text label+value, corroborated by title/JSON-LD/catalog alt-name"},
        "power_consumption": {"value": "1150 Вт", "status": "confirmed", "url": URL, "evidence": "Body text label+value"},
        "output_power": {"value": "800 Вт", "status": "confirmed", "url": URL, "evidence": "Body text label+value"},
        "official_image": {"value": IMAGE_URL, "status": "confirmed", "url": IMAGE_URL, "evidence": "Advertised srcset on product page, model+color in filename, live-verified as a real 491KB PNG this stage"},
        "instruction_manual": {
            "value": MANUAL_FINAL_URL,
            "status": "official_pdf_candidate_content_language_not_confirmed",
            "url": MANUAL_URL,
            "final_url": MANUAL_FINAL_URL,
            "evidence": "Reachable, first-party, genuine PDF (magic bytes confirmed) and linked to this model via the URL's own ModelName parameter (linkage evidence, not content evidence). Content/language NOT confirmed: the file exceeds the 1.5MB fetch cap, and the truncated download's cross-reference table, page tree and /Info metadata dictionary are unrecoverable, so no text could be extracted -- see pdf_content_verification.json for the full diagnosis.",
        },
    },
    "identity_result": "exact_variant",
    "identity_result_reasoning": "Model code confirmed via 3 independent sources (JSON-LD sku, exact catalog article match, manual URL ModelName parameter) and color confirmed via on-page <title> text (not URL). This exceeds the exact_model bar and satisfies exact_variant.",
    "manual_confirmed_by_content": False,
    "manual_confirmed_by_content_note": "Reachability and first-party linkage are confirmed; document content (that it is genuinely this model's user manual, page-by-page) is NOT confirmed, due to the truncation described above -- not due to absence of a plausible manual.",
    "russian_language_confirmed": False,
    "russian_language_confirmed_note": "The manual's filename lists 'RU' first among RU-UK-KK-UZ, and the download request itself used CDSite=UNI_KZ_RU -- both first-party but both metadata, not content. No Russian (or any other) text was extracted from the PDF itself, so Russian-language availability is not confirmed by content.",
    "specifications_status": "partial -- 3 confirmed values (volume, 2 power figures) plus color and oven type; 6 additional characteristics have a confirmed label but no confirmed value (see specs_completeness.json)",
    "missing_characteristics": [
        "Physical weight (net and packaged)",
        "Physical dimensions (WxHxD)",
        "Turntable diameter",
        "Control type/interface",
        "Auto-program and power-level counts",
        "Full defrost mode list",
    ],
    "export_readiness": {
        "status": "partially_ready",
        "ready_fields": ["brand", "model_name", "manufacturer_model_code", "color", "volume", "power_consumption", "output_power", "official_image"],
        "blocking_or_flagged_gaps": [
            "Instruction manual content/language not confirmed (candidate only) -- should be flagged to a human reviewer or re-attempted with a larger fetch allowance before being presented as a verified manual, not silently upgraded to 'confirmed'.",
            "6 physical/control characteristics have no confirmed value.",
        ],
        "recommendation": "Card CAN be exported now for the confirmed fields, with the manual and the 6 missing characteristics explicitly marked as open gaps -- not blocked entirely, but not silently presented as complete either.",
    },
}
json.dump(card, open(OUT / 'card.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

print('wrote specs_completeness.json, image_verification.json, card.json')
