# Lenovo Stage 60 official source structure

## 1. Official sources and identity

### Takeaway
PSREF has distinct product/platform and model-detail routes. A requested MTM in a URL is not identity evidence: rendered source data must identify that MTM. Lenovo Support exposes exact model data in embedded JSON; support content can provide exact configuration evidence independently of its help articles.

### Cited Findings
- Baseline support HTML contains `ds_productinfo.Model=21ML005BUS`, `IDs=[21ML005BUS]`, matching model title and configuration table in `Body`. CPU is Core Ultra 5 135U vPro, memory16GB DDR5-5600, storage512GB G4 Perf, OS Windows11Pro English, camera5MP RGB+IR, graphicsIntel Graphics, display14WUXGA. Exact relation is supported by payload, not merely pathname. ImageSrc is a generic laptops-and-netbooks category image, unsuitable for exact gallery confirmation. Countries includes US, CA and Latin-American codes: region suffix alone must not define an exclusive sales country. — [Support](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-t-series-laptops/thinkpad-t14-gen-5-type-21ml-21mm/21ml/21ml005bus)
- Official catalog associates `ThinkPad T14 Gen 5 Type 21ML 21MM` with machine-type children21ML and21MM. The downloaded catalog contains machine types rather than an exact21ML005BUS configuration leaf. — [Official catalog](https://pcsupport.lenovo.com/api/products/us/en.js)
- Exact detail JS reads URL parameterM and requests `/api/model/Info/GetInfoByKey` withModelCode and `/api/model/Info/SpecData` withmodel_code; separate photo/document routes useProductKey. Product routes therefore are not interchangeable with model routes. — [Observed detail implementation](https://psref.lenovo.com/assets/detail-DHRNokao.js)
- PSREF footer describes a specification-query platform; actual availability is referred to store/local sales. — [Observed shared implementation](https://psref.lenovo.com/assets/CountryDialog-famm9a-E.js)

### Inferences
- Suggested identity relations: exact_mtm from matching payloadModel/IDs; machine_type from official catalog; family_model and generation from product/platform sources; regional_variant requires source metadata. Different complete MTMs remain distinct even if first4characters match.
- No separate configuration solver is proved necessary by this baseline: exactSupportBody already contains concrete facts. A shared source adapter plus evidence scope can preserve the boundary. Batch evidence must determine generality.

### Gaps
- PSREF exact API response could not be retrieved. Public anonymous-token issuancePOST `/api/home/auth/issue` returned403, as did unauthenticated detail APIs. Saved response is HTML, not JSON; do not count an exact PSREF success.
- Storefront request redirects to a family product in coordinator snapshot; not exact confirmation. CTO uniqueness/configuration semantics are not independently proven here.

## 2. PSREF configuration risks

### Takeaway
The family PDF is an official source of platform options, not the installed configuration of21ML005BUS. Exact SupportBody has fewer facts and has a ports conflict with the family PDF.

### Cited Findings
- Family PDF lists eight processors, six panels, multiple storage/camera/battery/color/network options. Optional ports depend on model; adapter offerings depend on country. Weight depends on color/battery and is approximate; dimensions may vary. None proves this MTM's selection. — [PSREF family PDF](https://psref.lenovo.com/syspool/Sys/PDF/ThinkPad/ThinkPad_T14_Gen_5_Intel/ThinkPad_T14_Gen_5_Intel_Spec.pdf)
- ExactSupportBody saysHDMI2.0b; family PDF specifiesHDMI2.1. Preserve as conflicting observations instead of silently overwriting the exact source. — [Support](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-t-series-laptops/thinkpad-t14-gen-5-type-21ml-21mm/21ml/21ml005bus); [PDF](https://psref.lenovo.com/syspool/Sys/PDF/ThinkPad/ThinkPad_T14_Gen_5_Intel/ThinkPad_T14_Gen_5_Intel_Spec.pdf)

### Inferences
- Family options, starting weights, and possible displays must remain candidates/metadata. Exact display14WUXGA does not prove panel brightness, gamut, touch, or refresh rate.
- A family gallery can show multiple colors/optional ports. Exact photographs require configuration/color relation; generic category image must be rejected.

### Gaps
- Exact PSREF configuration and photo payload remain inaccessible from tested environment. No XHR payload was fabricated.

## 3. Discovery endpoints and manuals

### Takeaway
Official public scripts expose catalog and manuals endpoints that can fit the existing discovery/extraction flow. User Guide and Hardware Maintenance Manual are explicitly separate document types; Russian language availability in a selector is only a candidate until actual content is fetched.

### Cited Findings
- SupportHTML loads catalog `/api/products/us/en.js`; documentation UI requests `/{country}/{language}/api/v4/contents/productmultlanguagelist?pids={productId}&types=Manual,SG&countries={country}&language={language}`. Other content usesproductcontentslist; fullsearch is underapi/v4/search/fullsearch. These are observed routes, not verified successful payloads. — [Documentation JS](https://pcsupport.lenovo.com/esv4/psp-documentation/app-983e57c667.min.js); [Catalog](https://pcsupport.lenovo.com/api/products/us/en.js)
- Documentation entry separates User Guide, Setup Guide, Hardware Maintenance Manual, Safety & Warranty Guide, Compliance Info. Guide covers multiple models and warns illustrations/features vary. Russian appears in language choices, but retrieved page reportsPDF FAILED. — [User Guide](https://support.lenovo.com/fr/fr/documentation/SG10265)
- Repair page relates machine types21MC/21MD/21ME/21MF/21ML/21MM and links HMM/removal procedures; it is service content rather than product-description material. — [Repair article](https://support.lenovo.com/au/en/solutions/ht516591)
- Store robots is available and provides crawler directives; no sitemap-derived exact model relation was established. — [robots.txt](https://www.lenovo.com/robots.txt)
- Auth JS exposes anonymous issuance route and stores Bearer token; shared Axios baseURL is empty. HTTP403 prevented verification of modelJSON, not a demonstrated absence of an MTM. — [Auth JS](https://psref.lenovo.com/assets/auth-CmCWbT8o.js); [Axios implementation](https://psref.lenovo.com/assets/CountryDialog-famm9a-E.js)

### Inferences
- Classify manuals by document title/type; family relation is valid for guides but cannot confirm exact installed components. Russian status here is `Не проверена`, because selecting an available language or seeingFAILED does not verify actualRU manual.
- EmbeddedSupportBody can be parsed as exact specification table while excluding drivers, warranty lookup, repair procedures and troubleshooting from description.

### Gaps
- No verified sitemap payload, JSON-LD exact product payload or exact gallery was found in this subtask. Support fullsearch product-ID return and manuals payload still require execution validation; paths are observed only.
- Raw artifacts: reports/lenovo_stage60/{detail-DHRNokao,product-CudnOyFq,CountryDialog-famm9a-E,auth-CmCWbT8o,utils-BKwSidg9,support_catalog,support_search,support_docs}.js. No tokens are stored. psref_info/spec response files hold403HTML; extensionjson on the first failed response does not make it JSON.
