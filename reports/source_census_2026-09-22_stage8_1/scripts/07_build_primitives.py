import json
from pathlib import Path

OUT = Path('reports/source_census_2026-09-22_stage8_1')

primitives = {
    "schema_version": "stage8_1_primitives.v1",
    "note": "Each primitive is a candidate for a small, reusable READER function only -- it extracts raw structural facts. None of these decide identity meaning, variant meaning, or exact_model status; that judgment stays source-specific per the existing architecture (ProductIdentity / identity verification). No entry here is production_ready.",
    "shared_primitive_candidate": [
        {
            "name": "json_ld_product_field_extractor",
            "layer": "identity (raw parse only, not semantics)",
            "already_implemented": True,
            "implementation": "product_tool/census/discovery.py:json_ld_products()",
            "evidence": "Already used uniformly by the structural census across all 127 Stage 8 profiles; independently confirmed in Stage 8.1 on xiaomi_global (3 pages), bosch_home (3 pages), hyperx (3 pages), dreame DE storefront (2 pages).",
            "constraints": [
                "Returns raw field values only (name, sku, mpn, gtin*, image, additionalProperty, ...).",
                "Never itself decides whether a field means exact model, variant, or is safe to trust -- that stays source-specific (model_semantics differs: explicit_manufacturer_or_model vs unverified_sku_meaning vs marketing_name_only, confirmed genuinely different per family in this stage).",
                "Does not fire when a page embeds multiple/ambiguous Product objects (dreame's global.dreametech.com storefront) -- falls back to insufficient_evidence, not a guess."
            ]
        },
        {
            "name": "additionalProperty_specification_reader",
            "layer": "specifications",
            "already_implemented": False,
            "evidence": "Confirmed stable on 2 independent families, >=2 verified product pages each, matching field shape: bosch_home (2 DE pages: .additionalProperty[].name/.value/.unitText) and hyperx (3 pages: .additionalProperty[].name/.value, no unitText). unitText is optional-not-required in the shared contract.",
            "not_shared_with": "xiaomi_global (confirmed empty, 3/3 pages) and dreame (confirmed empty, 1/1 live-verified page) -- the reader must return 'no spec objects found' for these, not synthesize specs from elsewhere.",
            "constraints": [
                "Reads schema.org PropertyValue name/value/unitText triples only; does not interpret units or merge duplicate names.",
                "Must not be assumed universal -- apply only where additionalProperty is actually present; treat absence as insufficient_evidence per source.",
                "Stays separate from the DOM accordion/dl fallback seen on hyperx, which is not yet cross-family confirmed (bosch_home showed no DOM spec markup in its sampled pages) and stays source_specific."
            ]
        },
        {
            "name": "responsive_srcset_media_picker",
            "layer": "media",
            "already_implemented": False,
            "evidence": "Confirmed stable on 2 independent families, >=2 verified pages each: bosch_home (2 DE pages) and hyperx (3 pages), both showing img/source[srcset] plus JSON-LD .image. Single-sample corroboration (not counted toward the 2-family/2-page bar) from xiaomi_global (3/3 pages, plus itemprop=image gallery), asus, delonghi, and nintendo (1 page each).",
            "not_shared_with": "dreame's live-verified DE page (x60), which exposed JSON-LD .image but no srcset/gallery DOM markup at all -- this family does not currently qualify and must not be assumed to.",
            "constraints": [
                "Selects the largest explicitly advertised width/density candidate, or ImageObject.contentUrl when no srcset exists.",
                "Never invents CDN transforms or constructs URLs not present in the markup (existing project-wide rule, re-confirmed here).",
                "Falls back to source-specific handling (or insufficient_evidence) when srcset/gallery markers are absent, as on dreame."
            ]
        },
        {
            "name": "sitemap_loc_parser",
            "layer": "discovery (protocol-level only)",
            "already_implemented": True,
            "implementation": "product_tool/census/discovery.py:parse_sitemap(), sitemap_strategy.py",
            "evidence": "XML sitemap / sitemap-index <loc> parsing is a public protocol, not a brand-specific structure; already used generically across the census independent of CMS. Re-confirmed as still valid and brand-agnostic in this stage; not itself sufficient to reach a product page (many Stage 8.2 candidates have a sitemap but no product URL confirmed yet).",
            "constraints": [
                "Classifies loc entries as product/category by URL path pattern only; does not itself verify the target is actually a product page (a fetch + inspect_structure() call still verifies that).",
                "Independent of CMS/platform -- this is why it is already shared, unlike CMS fingerprinting, which the project already correctly excludes from adapter-grouping decisions."
            ]
        }
    ],
    "custom_adapter_candidate": [
        {
            "name": "identity_semantics_resolver",
            "layer": "identity (semantic interpretation)",
            "families": ["xiaomi_global", "bosch_home", "dreame", "hyperx", "asus", "delonghi", "nintendo"],
            "reason": "model_semantics genuinely differs and was independently re-confirmed with fresh multi-page evidence in Stage 8.1: bosch_home alone shows explicit_manufacturer_or_model (gtin+mpn); hyperx/dreame/asus/nintendo show unverified_sku_meaning (sku/productID present but not verified as a manufacturer code); xiaomi_global/delonghi show marketing_name_only (no code field at all). Pooling any of these would violate the exact_variant/exact_model separation the project requires."
        },
        {
            "name": "discovery_navigation_router",
            "layer": "discovery",
            "families": ["xiaomi_global", "bosch_home", "dreame", "hyperx"],
            "reason": "Underlying markup and routing differ completely per family (Next.js/AEM path-prefix locale routing on bosch_home; Shopify collections+search on hyperx and dreame's DE storefront, but with a DIFFERENT and less reliable JSON-LD contract on dreame's global storefront; a custom React-like homepage on xiaomi_global). The shared category/navigation labels in the Stage 8 contract schema are the classifier's own fixed vocabulary, not evidence of shared underlying code -- explicitly not treated as such here."
        },
        {
            "name": "dom_accordion_dl_specification_fallback",
            "layer": "specifications (DOM fallback only)",
            "families": ["hyperx"],
            "reason": "Confirmed on hyperx (3/3 pages) but not cross-family confirmed: bosch_home's sampled pages exposed specs only via JSON-LD, never via DOM table/dl/details. One family's fixture-backed evidence is not enough to pool."
        }
    ],
    "insufficient_evidence": [
        {"family": "xiaomi_global", "layer": "identity", "reason": "Confirmed absent (not merely unsampled) across 3 independent pages -- a real finding, but not a usable contract."},
        {"family": "xiaomi_global", "layer": "specifications", "reason": "Confirmed absent across 3 independent pages."},
        {"family": "dreame", "layer": "specifications", "reason": "Confirmed absent on the one live-verified (non-sanitized) page; not observed on 3 other pages either."},
        {"family": "dreame", "layer": "identity (global.dreametech.com storefront specifically)", "reason": "JSON-LD Product not reliably present (is_product_page=false on both sampled live pages); the DE storefront's contract cannot be assumed to also apply to the global storefront."},
        {"family": "all 7 families reviewed", "layer": "documents", "reason": "Only one sample across all 7 families shows any document evidence at all (dreame's a2 snapshot), and even that is explicitly flagged unverified for model-linkage and language by the existing runner. No primitive, shared or custom, can be certified yet."},
        {"family": "asus, delonghi, nintendo (reference families)", "layer": "discovery, identity, specifications, documents", "reason": "Single sample each, out of Stage 8.1 scope for extension; kept as single-page reference points only, per the task's explicit instruction not to broaden research beyond the primary four families."}
    ],
    "blocked_manual_review": [
        {"family": "dreame", "profile": "dreame_us", "reason": "completeness_status=http_blocked carried over from Stage 8; not retried in Stage 8.1 (no new host contact after a block, per existing policy)."}
    ]
}

OUT.joinpath('primitives.v1.json').write_text(json.dumps(primitives, indent=2, ensure_ascii=False), encoding='utf-8')
print('wrote primitives.v1.json')
