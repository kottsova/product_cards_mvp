"""Stage 10.2 -- final card: variant-specific vs line-wide fields separated,
manual search outcome (RU-first), and an explicit, corrected readiness
criterion. Built entirely from this stage's own saved artifacts."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10_2'
STAGE10 = ROOT / 'reports/source_census_2026-09-23_stage10'
STAGE10_1 = ROOT / 'reports/source_census_2026-09-23_stage10_1'

offline_row = json.loads((STAGE10 / 'offline_row_analysis.json').read_text(encoding='utf-8'))['selected_row']
reverif = json.loads((OUT / 'offline_reverification.json').read_text(encoding='utf-8'))
phase1 = json.loads((OUT / 'phase1_ru_sitemap_fetch.json').read_text(encoding='utf-8'))
phase2 = json.loads((OUT / 'phase2_ru_article_fetch.json').read_text(encoding='utf-8'))

PAGE_URL = 'https://www.xbox.com/en-US/consoles/xbox-series-s'

card = {
    'stage': '10.2',
    'scope': 'Completion of the bounded cycle for catalog row XXU-00015 (Xbox Series S, Carbon Black, 1TB)',
    'selected_catalog_row': offline_row,

    'variant_specific_fields_carbon_black_1tb': [
        {
            'field': 'Цвет/вариант', 'value': 'Carbon Black', 'url': PAGE_URL,
            'evidence': 'Purchase-option label "1TB All-Digital Carbon Black" (data-option="s-new"), confirmed live (uncommented) markup, plus JS hash-routing (#black1tb / #purchaseblack1tb) independently mapping to the same option.',
        },
        {
            'field': 'Объём накопителя', 'value': '1TB Custom NVMe SSD', 'url': PAGE_URL,
            'evidence': 'Explicit spec line "XBOX Series S Carbon Black: 1TB Custom NVME SSD", listed separately from the two Robot White lines (512GB and 1TB) in the same TECH SPECS block -- confirmed live, uncommented.',
        },
    ],
    'line_wide_fields_applies_to_all_series_s_skus': [
        {'field': 'Модельный ряд', 'value': 'Xbox Series S', 'url': PAGE_URL, 'evidence': 'Page title/URL and heading.'},
        {'field': 'Процессор (CPU)', 'value': '8x Cores @ 3.8 GHz (3.6 GHz w/SMT), Custom Zen 2', 'url': PAGE_URL, 'evidence': 'TECH SPECS section; not restated per color/capacity option.'},
        {'field': 'Графика (GPU)', 'value': '4 TFLOPS, 20 CUs @ 1.565 GHz, Custom RDNA 2', 'url': PAGE_URL, 'evidence': 'same section, same caveat'},
        {'field': 'Память', 'value': '10GB GDDR6, 128-bit bus (8GB @ 224GB/s + 2GB @ 56GB/s)', 'url': PAGE_URL, 'evidence': 'same section, same caveat'},
        {'field': 'Расширение памяти', 'value': 'Поддержка карт расширения 1TB для Series X|S; USB 3.1 внешний HDD', 'url': PAGE_URL, 'evidence': 'same section, same caveat'},
        {'field': 'Видео', 'value': 'До 1440p, до 120 FPS, HDMI 2.1 (ALLM, VRR, AMD FreeSync)', 'url': PAGE_URL, 'evidence': 'same section, same caveat'},
        {'field': 'Звук', 'value': 'L-PCM до 7.1, Dolby Digital 5.1, DTS 5.1, Dolby TrueHD с Atmos', 'url': PAGE_URL, 'evidence': 'same section, same caveat'},
        {'field': 'Порты/связь', 'value': '1x HDMI 2.1, 3x USB 3.1 Gen 1, Wi-Fi 802.11ac dual-band', 'url': PAGE_URL, 'evidence': 'same section, same caveat'},
        {
            'field': 'Габариты', 'value': '6.5 x 15.1 x 27.5 cm', 'url': PAGE_URL,
            'evidence': 'TECH SPECS section, appears exactly once for the whole line (unlike storage, never restated per option).',
            'caveat': 'Not demonstrated identical across color/capacity SKUs by the page itself; applied to the Carbon Black 1TB unit by physical-design inference only, not an explicit per-SKU statement. Do not present as a Carbon-Black-confirmed number without this caveat.',
        },
        {
            'field': 'Вес', 'value': '4.25 lbs (~1.93 kg)', 'url': PAGE_URL,
            'evidence': 'same section, same caveat as dimensions',
            'caveat': 'Same caveat as dimensions.',
        },
    ],

    'images': {
        'stage10_1_claim_status': 'RETRACTED',
        'correction': reverif['carbon_aware_images_correction']['correction'],
        'confirmed_carbon_black_specific_images_this_stage': 0,
        'total_image_video_assets_on_page': reverif['genuine_color_specific_image_search']['total_image_video_assets_on_page'],
        'note': 'The 3 "Carbon-Aware"-named assets remain valid, official, line-wide illustrations of an environmental/sustainability feature; they are simply not evidence of the Carbon Black color and must not be cited as such.',
    },

    'seller_article_handling': reverif['seller_article_handling'],

    'manual_search': {
        'route_used': (
            'support.xbox.com only (the role-confirmed support host). Checked the two already-'
            'found candidate hardware-setup articles in both Russian (checked first, per '
            'instruction) and English, using URLs confirmed present in support.xbox.com\'s own '
            'sitemaps -- never guessed by locale-substitution.'
        ),
        'russian_checked_first': True,
        'russian_result': {
            'urls': list(phase2['results'].keys()),
            'confirmed_present_in_ru_sitemap': True,
            'http_status': 200,
            'content_accessible': False,
            'reason': 'Bare client-rendered SPA shell (~2,897 bytes, <noscript>You need to enable JavaScript to run this app.</noscript>), identical architecture to the English version already found in Stage 10.1.',
        },
        'english_result': {
            'urls': [
                'https://support.xbox.com/en-US/help/hardware-network/console/unbox-xbox-series-xs-console',
                'https://support.xbox.com/en-US/help/hardware-network/getting-started-set-up/set-up-new-series-x-s',
            ],
            'source': 'Stage 10.1 (not re-fetched this stage; re-examined offline only)',
            'http_status': 200,
            'content_accessible': False,
            'reason': 'Same bare SPA shell architecture.',
        },
        'pdf_search_result': {
            'searched_in': ['www.xbox.com sitemap index + CMS chunk (Stage 10.1)', 'support.xbox.com en-US sitemap (Stage 10.1)', 'support.xbox.com ru-RU sitemap (this stage)', 'the confirmed console landing page body (this stage, offline re-read)'],
            'pdf_urls_found': 0,
            'document_cdn_host_found': False,
        },
        'language_confirmed': None,
        'model_applicability_confirmed': None,
        'status': 'not_confirmed_present_and_not_confirmed_absent',
        'explicit_statement': (
            'The instruction manual is NEITHER confirmed present NOR confirmed absent. Two '
            'real, live, on-topic candidate articles exist in both Russian and English '
            '(HTTP 200, correct URLs, plausibly-applicable titles referencing Series X|S '
            'unboxing and setup), but their content cannot be read without executing '
            'JavaScript, which remains out of scope for this stage. This is a structural '
            'access gap, not a statement that no manual exists. A generic Xbox article is '
            'never labeled a "Series S manual" here because no content was actually read to '
            'confirm applicability -- per instructions, only content-confirmed applicability '
            'would justify that label, and none was obtained.'
        ),
    },

    'five_point_export_readiness_criterion': {
        'criterion_1_brand_model_confirmed_by_official_source': {'pass': True, 'detail': 'Unchanged from Stage 10.1: brand and model confirmed on www.xbox.com.'},
        'criterion_2_catalog_row_linked_to_confirmed_variant': {'pass': True, 'detail': 'Unchanged: linked by model+capacity+color descriptive consistency (color and storage are both confirmed live, variant-specific evidence, independent of the retracted images).'},
        'criterion_3_official_matched_image_confirmed': {
            'pass': False,
            'detail': 'CORRECTED from Stage 10.1 (which incorrectly marked this passed). The 3 images cited there depict an unrelated sustainability feature, not the Carbon Black color. No genuine color-specific image was found this stage. This criterion now fails.',
        },
        'criterion_4_specifications_sufficient': {'pass': True, 'detail': 'Unchanged: detailed specs found, now explicitly separated into variant-specific (storage) and line-wide (everything else) with caveats.'},
        'criterion_5_manual_confirmed_present_or_absence_noted': {
            'pass': False,
            'detail': 'Still open, now confirmed exhausted for the one bounded document/support route in both Russian and English -- same structural JS blocker in both languages.',
        },
    },
    'export_readiness': 'not_ready',
    'export_readiness_reason': (
        'Two of five criteria fail: criterion 3 (image), corrected this stage from a false '
        '"pass" in Stage 10.1 to an honest "fail" after re-reading the actual caption text '
        'behind the "Carbon-Aware" filenames; and criterion 5 (manual), which remains a '
        'structural access gap rather than a data gap, now confirmed exhausted in both '
        'Russian and English within this stage\'s bounded route.'
    ),
    'what_is_already_exportable_with_evidence': (
        'Brand, exact model line, the Carbon Black color, the 1TB storage capacity (variant-'
        'specific), and a full line-wide technical specification set (CPU/GPU/memory/video/'
        'sound/ports, plus dimensions/weight with an explicit line-wide caveat) -- all with a '
        'URL and a stated evidence basis. This is a materially complete, honestly-caveated set '
        'of exportable fields even though the full card is not yet "ready" by the 5-point '
        'criterion.'
    ),
    'what_is_not_ready': (
        'The full card is not ready: no confirmed color-specific image exists, and the '
        'instruction manual\'s presence/language cannot yet be confirmed. Neither gap is '
        'described as a confirmed negative (no image exists at all; no manual exists at all) '
        '-- both are stated as unresolved within this stage\'s bounded, no-Chromium route.'
    ),
}

(OUT / 'card.json').write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding='utf-8')
print('export_readiness:', card['export_readiness'])
print('criteria pass:', [k for k, v in card['five_point_export_readiness_criterion'].items() if v['pass']])
