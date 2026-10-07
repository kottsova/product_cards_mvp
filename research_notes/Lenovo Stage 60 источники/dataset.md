# Lenovo Stage 60 independent dataset

## Какие модели зафиксированы?

### Takeaway
Зафиксированы ровно 10 реальных полных MTM/part numbers, исключая baseline 21ML005BUS. Выборка покрывает четыре серии ноутбуков, два монитора, desktop, tablet и два сложных regional SKU.

### Cited Findings
- 21KC0029MH — ThinkPad X1 Carbon Gen 12; laptop; регион: Netherlands. Риск: soldered memory; family weight/photo disclaimer. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/ThinkPad/ThinkPad_X1_Carbon_Gen_12?M=21KC0029MH)
- 21KG0004AT — ThinkBook 14 G6 IRL; laptop; регион: Austria. Риск: installed RAM versus max memory/storage support. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/ThinkBook/ThinkBook_14_G6_IRL?M=21KG0004AT)
- 83EM007FLK — IdeaPad Slim 3 15IRH8; laptop; регион: Sri Lanka. Риск: TN exact display versus family IPS/touch options; starting-at weight. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/IdeaPad_Slim_3_15IRH8?M=83EM007FLK)
- 83LY0066PB — Legion 5 15IRX10; laptop; регион: Poland. Риск: RTX 5050 exact versus family 5060/5070 options. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/Legion_5_15IRX10?M=83LY0066PB)
- 63A4ZAR1U1 — ThinkVision T27i-30 Monitor; monitor; регион: unverified. Риск: optional camera/accessories must not become included. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/thinkvision_t27i_30_monitor?M=63A4ZAR1U1)
- 62C1GAT6EU — ThinkVision P40w-20 Monitor; monitor; регион: Europe (EU suffix; country unverified). Риск: regional cable/bundle differences; exact page may require hydration. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/ThinkVision_P40w_20?M=62C1GAT6EU)
- 12E4S96402 — ThinkCentre M70q Gen 4; desktop; регион: unverified (Spanish OS; do not infer country). Риск: S-prefix configuration; full suffix 02 not ordinary country code. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/ThinkCentre_M70q_Gen_4?M=12E4S96402)
- ZACH0134PL — Tab P12; tablet; регион: Poland. Риск: bundled pen versus optional keyboard; platform TB code versus sales MTM. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/Lenovo_Tablets/Tab_P12?M=ZACH0134PL)
- 83EM00KVMX — IdeaPad Slim 3 15IRH8; laptop; регион: Nordics. Риск: complex regional SKU: MX suffix is Nordics in official metadata, not Mexico; different keyboard/display. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/IdeaPad_Slim_3_15IRH8?M=83EM00KVMX)
- 83LY00JCRK — Legion 5 15IRX10; laptop; регион: unverified (Russian OS; country must be read). Риск: regional RK suffix; RTX 5060 versus base sample RTX5050; cannot substitute MTM. — [Official PSREF Model detail](https://psref.lenovo.com/Detail/Legion_5_15IRX10?M=83LY00JCRK)

### Inferences
- Два дополнительных regional SKU той же IdeaPad/Legion family создают полезные отрицательные проверки: точный MTM должен сохранить другую конфигурацию, а похожая family page не должна подменять исходный MTM.

### Gaps
- Для указанных unverified регионов страна не установлена; язык OS и suffix не являются достаточным доказательством страны.

## Что доказывают источники?

### Takeaway
Каждый article подтвержден Model heading в официальном поисковом индексе PSREF. Самостоятельный direct open всех десяти страниц вернул 0 строк: это наблюдаемое ограничение web extraction, не доказательство отсутствия характеристик.

### Cited Findings
- IdeaPad 83EM007FLK: exact detail фиксирует TN display, 8GB RAM и Starting at 1.62 kg; platform Product перечисляет варианты IPS/touch/up to. — [Exact](https://psref.lenovo.com/Detail/IdeaPad_Slim_3_15IRH8?M=83EM007FLK); [Family](https://psref.lenovo.com/Product/IdeaPad_Slim_3_15IRH8)
- IdeaPad 83EM00KVMX: официальный Country/Region — Nordics, хотя suffix MX может спровоцировать ошибочный вывод Mexico. — [Exact](https://psref.lenovo.com/Detail/IdeaPad_Slim_3_15IRH8?M=83EM00KVMX)
- Legion 83LY0066PB имеет RTX5050; 83LY00JCRK — RTX5060 и Russian OS. — [PB](https://psref.lenovo.com/Detail/Legion_5_15IRX10?M=83LY0066PB); [RK](https://psref.lenovo.com/Detail/Legion_5_15IRX10?M=83LY00JCRK)

### Inferences
- PSREF exact detail пригоден для конфигурационных фактов при совпадении полного MTM, но отдельные maximum/starting-at/optional строки остаются capabilities или candidates.

### Gaps
- Product paths в JSON являются derived discovery candidates, не отдельно подтвержденными PDP. Support URLs и storefront PDP не выдумывались; должны быть найдены штатным discovery.

## Как сохраняется независимость выборки?

### Takeaway
Dataset фиксируется до запуска и не заменяется при network/extraction/identity gaps. Pipeline в рамках этого задания не запускался.

### Cited Findings
- PSREF предупреждает, что illustration images могут отличаться по цвету, портам, клавиатуре и аксессуарам между моделями. — [IdeaPad exact detail](https://psref.lenovo.com/Detail/IdeaPad_Slim_3_15IRH8?M=83EM007FLK)

### Inferences
- Детальные official research URLs сохраняются как audit metadata; использовать их как runtime model hardcode нельзя.

### Gaps
- Live pipeline outcomes здесь отсутствуют намеренно; coordinator проводит first-pass с frozen dataset.
