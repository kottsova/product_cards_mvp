import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_1')

comparison = {
    "schema_version": "stage8_2_1_samsung_template_comparison.v1",
    "pages_compared": {
        "tv": "https://www.samsung.com/kz_ru/tvs/full-hd-tv/n5300-43-inch-full-hd-smart-tv-ue43n5300auxce/ (Stage 8.2)",
        "audio_buds": "https://www.samsung.com/kz_ru/audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/ (Stage 8.2)",
        "smartphone_1": "https://www.samsung.com/kz_ru/smartphones/galaxy-s25-ultra/ (this stage)",
        "smartphone_2": "https://www.samsung.com/kz_ru/smartphones/galaxy-s26-ultra/buy/ (this stage)",
    },
    "layers": {
        "identity_storage": {
            "tv_and_audio": "JSON-LD Product object (.name + .sku), model_semantics=unverified_sku_meaning",
            "smartphone": "NONE -- zero JSON-LD Product objects, zero microdata Product nodes on either smartphone page",
            "same": False,
        },
        "specifications": {
            "tv_and_audio": "empty in static HTML (no additionalProperty, no DOM table/dl/details) -- same as most other reviewed families",
            "smartphone": "empty (nothing to compare -- no product object at all)",
            "same": "inconclusive (both empty, but for possibly different reasons: TV/audio have a product object with genuinely no specs field; smartphone has no product object to begin with)",
        },
        "media_layer": {
            "tv_and_audio": "JSON-LD .image + DOM responsive_srcset",
            "smartphone": "DOM responsive_srcset present (media.observed=true), but with NO accompanying JSON-LD .image path since there is no JSON-LD Product at all -- images are presumably decorative/hero-banner markup, not confirmed product photography",
            "same": False,
        },
        "embedded_state_and_json_ld": {
            "tv_and_audio": "generic_json_ld_product CMS engine confirmed; Adobe Experience Manager",
            "smartphone": "generic_json_ld_product NOT confirmed on either page; page still fingerprints as Adobe Experience Manager -- same backend platform, different frontend rendering behavior for this section",
            "same": False,
            "note": "Same CMS (Adobe Experience Manager) across all Samsung pages checked so far -- but per the project's own rule, CMS identity is never used to infer a shared adapter or template; the DATA CONTRACT differs sharply between the two sections despite the shared platform.",
        },
        "support_documents_route": {
            "tv_and_audio": "a[href:pdf] link + support_navigation=true confirmed on both pages (Stage 8.2 finding)",
            "smartphone": "no PDF link found on either smartphone page (support_navigation status not separately re-confirmed this stage since no product page verified)",
            "same": False,
        },
    },
    "responsive_srcset_media_picker_recheck": {
        "primitive": "responsive_srcset_media_picker (from Stage 8.1, reconfirmed on bosch_home/hyperx/samsung TV+buds in Stage 8.2)",
        "applies_to_samsung_smartphone_pages": False,
        "reasoning": "The DOM responsive_srcset marker IS present on both smartphone pages, but since is_product_page=false (no confirmed single Product), the srcset-bearing images cannot be attributed to confirmed product photography -- they may be hero/marketing banners. Per the same rule already applied to LG in Stage 8.2 (unverified pages don't count toward or against the primitive), this is recorded as not_applicable, not a confirmation and not a contradiction.",
    },
    "no_other_shared_primitive_expanded": "No new shared_primitive_candidate is declared from this single-family, single-stage evidence. The documents-candidate from Stage 8.2 (Samsung TV+buds) is neither strengthened nor weakened by this stage -- smartphones simply produced no comparable evidence either way.",
    "samsung_adapter_shape_conclusion": {
        "verdict": "separate_category_templates_within_one_family_orchestration",
        "reasoning": (
            "Samsung is one source_family with one official domain and one identity_semantics_resolver shape (sku-only, unverified_sku_meaning, confirmed on TV+buds), "
            "but at least two structurally distinct category-level page templates have now been observed under the same platform (Adobe Experience Manager): "
            "a JSON-LD-bearing template (TVs, audio-sound/mobile-accessories -- everything reached through the b2c-sitemap.xml XML catalog) and a client-side-rendered "
            "template with no static structured data at all (the /smartphones/ family/buy pages, reached only through first-party site navigation, not the sitemap). "
            "This does not justify one uniform Samsung family adapter that assumes JSON-LD everywhere, nor does it justify treating smartphones as an unrelated, "
            "fully separate brand -- discovery/orchestration (one official domain, one sitemap system, one identity-code convention) can stay shared, but the "
            "per-page extraction step needs a category-aware branch: a JSON-LD-based extractor for TV/audio/appliance/memory categories, and a distinct "
            "(likely embedded-state-dependent, out of current scope) extractor for smartphones specifically -- not a single common page-parsing template."
        ),
    },
}
json.dump(comparison, open(OUT / 'samsung_template_comparison.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote samsung_template_comparison.json')
