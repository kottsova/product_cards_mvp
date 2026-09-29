import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage9')

URL = "https://direct.playstation.com/en-us/buy-accessories/dualsense-wireless-controller-cosmic-red-for-ps5-pc-mac-mobile"
IMAGE_URL = "https://media.direct.playstation.com/is/image/sierialto/2025-dualsense-ps5-controller-cosmic-red-accessory-front?$Background_Large$"

identity_ambiguity = {
    "schema_version": "stage9_identity_ambiguity.v1",
    "finding": "Two distinct catalog rows both name the color 'Cosmic Red' for a DualSense controller, with DIFFERENT seller article/manufacturer codes.",
    "candidates": [
        {"seller_article": "CFI-ZCT1J 02", "name": "Геймпад DualSense для PS5 Cosmic Red", "note": "The row Stage 8.2 originally targeted for its search."},
        {"seller_article": "CFI-ZCT1W_cosmic_red", "name": "Беспроводной геймпад DualSense Cosmic Red", "note": "Discovered by this stage's offline re-search; a genuinely different seller article for a same-named color."},
    ],
    "official_page_sku_found": "1000050734",
    "official_page_sku_interpretation": (
        "This is PS Direct's own internal US-webstore product ID (a generic numeric identifier), not a Sony manufacturer/regional part "
        "number. It shares no relationship with either candidate's CFI-ZCT1x code."
    ),
    "manufacturer_code_search_result": {
        "searched_for": ["CFI-ZCT1J", "CFI-ZCT1W", "any 'CFI-' pattern"],
        "found_in_microdata": False,
        "found_in_visible_body_text": False,
        "regex_scan_result": "Zero matches for the pattern 'CFI-[A-Z0-9]+' anywhere in the fetched page text.",
    },
    "consequence": (
        "The official page confirms brand, model name, and color (via a structured 'Color:' field) but exposes no manufacturer/regional "
        "code comparable to the catalog's CFI-ZCT1x scheme. This means: (a) neither candidate catalog row can be confirmed over the "
        "other from this page's evidence, and (b) per instructions, the two candidates are NOT collapsed into one by assuming they are "
        "interchangeable 'similar controllers' -- both are reported, unresolved, with the ambiguity stated plainly rather than picked "
        "arbitrarily."
    ),
    "which_row_this_report_treats_as_primary": "CFI-ZCT1J 02 (continuity with Stage 8.2's original search target), with CFI-ZCT1W_cosmic_red carried alongside as an unresolved alternate -- this is a continuity choice for reporting purposes only, not a confirmed disambiguation.",
}
json.dump(identity_ambiguity, open(OUT / 'identity_ambiguity.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

evidence = {
    "schema_version": "stage9_evidence.v1",
    "item": "PlayStation DualSense Wireless Controller, Cosmic Red",
    "product_page_url": URL,
    "page_type": "Product page (microdata Product confirmed, is_product_page=true) -- distinct from any support-page source type.",
    "canonical_url": URL,
    "canonical_matches_fetched_url": True,
    "fields": {
        "brand": {
            "value": "Sony / PlayStation",
            "status": "confirmed",
            "evidence": "Page includes an alt='Sony' logo image and 'PlayStation® (US)' in the <title> tag; official direct.playstation.com domain.",
            "source": "HTML <title> tag + logo alt text",
        },
        "model_name": {
            "value": "DualSense® Wireless Controller",
            "status": "confirmed",
            "evidence": "Microdata itemprop=name value: 'DualSense® Wireless Controller - Cosmic Red - For PS5, PC, MAC & Mobile', independently corroborated by the <title> tag.",
            "source": "Microdata itemprop=name + <title> tag",
        },
        "color": {
            "value": "Cosmic Red",
            "status": "confirmed_structured",
            "evidence": "A labeled 'Color:' field followed by the value 'Cosmic Red' was found in the page's visible content -- a structured label+value pair, not just a marketing-text mention (which is what Stage 8.2 had). This is stronger evidence than Stage 8.2's plain-text-only confirmation.",
            "source": "Visible body text, structured 'Color:' label",
        },
        "official_page_sku": {
            "value": "1000050734",
            "status": "confirmed_present_but_not_catalog_comparable",
            "evidence": "Microdata itemprop=sku value.",
            "source": "Microdata itemprop=sku",
            "caveat": "See identity_ambiguity.json -- this is PS Direct's own internal webstore ID, not a Sony manufacturer/regional code comparable to the catalog's CFI-ZCT1x scheme.",
        },
        "manufacturer_regional_code": {
            "value": None,
            "status": "not_found",
            "evidence": "Explicit search (microdata scan + regex for the 'CFI-' pattern across the full page text) found zero occurrences of either candidate catalog code (CFI-ZCT1J, CFI-ZCT1W) or any CFI-prefixed string at all.",
            "source": None,
        },
        "specifications": {
            "status": "partial_qualitative_only",
            "confirmed_features": [
                {"feature": "haptic_feedback", "evidence": "'bringing gaming worlds to life with haptic feedback and adaptive triggers' in body text."},
                {"feature": "adaptive_triggers", "evidence": "Same sentence as above."},
                {"feature": "built_in_battery_usb_c", "evidence": "'charge and play with a built-in battery and USB-C port' in body text."},
                {"feature": "bluetooth_wireless", "evidence": "Body text references pairing 'with the controller over Bluetooth®'."},
                {"feature": "firmware_updatable", "evidence": "Body text references updating 'PS5 system software and the wireless controller device software to the latest' version."},
                {"feature": "comparison_claim", "evidence": "'*Compared to DUALSHOCK®4 wireless controller' footnote present (marketing comparison, not a numeric spec)."},
            ],
            "not_confirmed": [
                "Exact battery capacity (mAh)",
                "Weight",
                "Dimensions",
                "Charging time",
                "Battery life (hours)",
                "Bluetooth version number",
            ],
            "reasoning": "All confirmed features are qualitative marketing/feature descriptions with explicit textual evidence, not a structured specifications table (specifications.dom_semantics and .json_paths are both empty in the structural contract -- no table/dl/details or JSON-LD additionalProperty found).",
        },
        "official_image": {
            "value": IMAGE_URL,
            "status": "confirmed",
            "evidence": "DOM img/source[srcset] on the product page, alt text 'DualSense® Wireless Controller - Cosmic Red - For PS5, PC, MAC & Mobile' (model+color match, not URL-only). Named size tokens observed ($Thumbnail_Large$, $Background_Small$, $Background_Large$) rather than pixel-dimension srcset; $Background_Large$ was selected as the largest explicitly advertised named size, per the project's existing 'largest advertised candidate' principle applied to this site's own naming convention.",
            "source": "responsive srcset/alt attributes on the product page",
            "additional_images_available": "A second angle ('top-left-hero-2') was also found with the same naming convention, not selected as primary but available as a secondary image candidate.",
            "first_party_host": "media.direct.playstation.com (first-party PlayStation media CDN)",
        },
        "instruction_manual": {
            "value": None,
            "status": "not_found_in_checked_sources",
            "evidence": "No .pdf link was found anywhere on the product page (pdf_links_found is empty). The only /support/ links present are generic e-commerce policy pages (Klarna financing, FAQs, shipping/tracking, cancellations/refunds, products & subscriptions) -- none is a product manual or quick-start guide.",
            "source": None,
            "scope_note": "Per instructions, no broad brand search or additional host was opened to search further for a manual beyond this specific verified page and its own first-party links -- support.playstation.com and www.playstation.com were pre-declared as available hosts but were never contacted, since no link on this page pointed to either. This is recorded as 'not found in the sources actually checked', not as evidence the manual does not exist.",
        },
    },
    "requests_used_for_this_item": 1,
}
json.dump(evidence, open(OUT / 'evidence.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote identity_ambiguity.json, evidence.json')
