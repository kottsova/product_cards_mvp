# HyperX: один запрос по 27 строкам

Из 38 строк, у которых адаптер HyperX есть, а URL был неизвестен, **11 получили точный URL** (в рабочей карте), по **27** точной официальной страницы не нашлось. Ссылки не угадывались: страницы брались только из сохранённых ссылок на hyperx.com и из sitemap, объявленного в `robots.txt`; строка принималась, только если `sku` страницы равен коду каталога и название совпало по модели.

Ответьте, пожалуйста, по каждому пункту одной строкой: **URL**, «нет такой страницы на hyperx.com» или «оставить как есть».

## A. Страница модели найдена, вариант каталога на ней есть, но нет ссылки на этот вариант (7 строк)

Код каталога числится вариантом на странице, а JSON-LD и ссылки страницы ведут на вариант по умолчанию. Адрес именно этого варианта нигде не наблюдался, строить `?variant=…` самому я не стал.

**Нужно:** точные ссылки на варианты **или** ваше разрешение проверить варианты по идентификаторам из данных самой страницы (не более 7 запросов к hyperx.com, тот же policy-aware fetch, остановка при первом 403/429).

| Артикул | Название в каталоге | Страница | sku варианта по умолчанию |
|---|---|---|---|
| 727A8AA | Наушники игровые проводные с микрофоном Cloud III | /products/hyperx-cloud-iii-wired-gaming-headset | 9W1Q4AA |
| 727A9AA | Наушники игровые проводные с микрофоном Cloud III | /products/hyperx-cloud-iii-wired-gaming-headset | 9W1Q4AA |
| A59YZAA | Наушники игровые беспроводные с микрофоном Cloud III S | /products/hyperx-cloud-iii-s-wireless-gaming-headset | DF7E9AA |
| A59Z0AA | Наушники игровые беспроводные с микрофоном Cloud III S | /products/hyperx-cloud-iii-s-wireless-gaming-headset | DF7E9AA |
| AJ0T1AA | Наушники игровые беспроводные с микрофоном Cloud Jet Black | /products/hyperx-cloud-jet-wireless-gaming-headset | AM7A0AA |
| B5VC5AA | Игровые беспроводные наушники с микрофоном Cloud Flight 2 | /products/hyperx-cloud-flight-2-wireless-gaming-headset | B5VC4AA |
| BS7C1AA | Наушники игровые проводные с микрофоном Cloud III | /products/hyperx-cloud-iii-wired-gaming-headset | 9W1Q4AA |

## B. Страница найдена, но её sku другой — вариант каталога не подтверждён (11 строк)

Кода каталога на странице нет: это другой вариант, регион или поколение. Такая страница не принимается как точная.

**B1. Клавиатуры (RU), 6 строк.** Каталог: коды `…AX#ACB` / `…AA` (RU), на hyperx.com найдена только US-раскладка (`…#ABA`). Базовый код у части строк отличается, так что это не только суффикс. **Нужно:** ссылка на RU-страницу, если она существует, либо «нет такой страницы».

| Артикул | Название в каталоге | Найдена страница | sku страницы |
|---|---|---|---|
| 4P4F5AX#ACB | Клавиатура проводная Alloy Core RGB (RU) | /products/hyperx-alloy-core-rgb-gaming-keyboard | 4P4F5AA#ABA |
| 4P4F6AX#ACB | Клавиатура проводная Alloy Origins Red (RU) | /products/hyperx-alloy-origins-mechanical-gaming-keyboard | 4P5N9AA#ABA |
| 4P5D6AX#ACB | Проводная клавиатура Alloy Origins 65 (HyperX Red) (RU) | /products/hyperx-alloy-origins-65 | 56R64AA#ABA |
| 4P5N0AA | Проводная клавиатура Alloy Origins 60 (HyperX Red) (RU) | /products/hyperx-alloy-origins-60-mechanical-gaming-keyboard | 4P5N4AA#ABA |
| 572Y6AA#ACB | Клавиатура проводная Alloy Origins 60 Pink (RU) | /products/hyperx-alloy-origins-60-mechanical-gaming-keyboard | 4P5N4AA#ABA |
| 639N3AA | Проводная клавиатура Alloy Origins (HyperX Red) (RU) | /products/hyperx-alloy-origins-mechanical-gaming-keyboard | 4P5N9AA#ABA |

**B2. Прочие, 5 строк.** **Нужно:** ссылка на страницу именно этого варианта или «нет такой страницы».

| Артикул | Название в каталоге | Найдена страница | sku страницы |
|---|---|---|---|
| 4Z7X5AA | Коврик для мыши Pulsefire Mat XL | /products/hyperx-pulsefire-mat-gaming-mouse-pad-xl | 572Y5AA |
| 872V1AA | Микрофон для пк игровой QuadCast 2 Black | /products/hyperx-quadcast-2-s-usb-microphone | 9A273AA |
| 4P5L2AA | Игровые проводные наушники с микрофоном Cloud Alpha S Black | /products/hyperx-cloud-alpha-s | 4P5L3AA |
| 6H9B5AA | Наушники игровые проводные с микрофоном Cloud Stinger 2 Core для PS | /products/hyperx-cloud-stinger-2-core-wired-gaming-headset | 683L9AA |
| 77Z45AA | Игровые беспроводные наушники с микрофоном Cloud III Wireless | /products/hyperx-cloud-iii-wireless-gaming-headset | 77Z46AA |

## C. Страницы нет в наблюдённых источниках (8 строк)

В sitemap (253 товара) и в сохранённых ссылках нет страницы, где были бы все модельные токены названия.

**Нужно:** URL, если товар есть на hyperx.com, либо «нет на hyperx.com».

| Артикул | Категория | Название в каталоге |
|---|---|---|
| 75X30AA | Web-камеры | Web-камера Vision S |
| 639N7AA#ACB | Клавиатуры | Клавиатура проводная Alloy Origins PBT TKL Red (RU) |
| 4Z7X3AA | Коврики для мыши | Коврик для мыши Pulsefire Mat M |
| 4Z7X4AA | Коврики для мыши | Коврик для мыши компьютерной Pulsefire Mat (L) |
| 4Z7X6AA | Коврики для мыши | Коврик для мыши Pulsefire Mat XXL |
| 4P5E2AA | Микрофоны | Микрофон для пк игровой DuoCast |
| 4P5P8AA | Микрофоны | Микрофон для пк игровой SoloCast Black |
| 519T2AA | Микрофоны | Микрофон для пк игровой SoloCast White |

## D. Не товар hyperx.com (1 строка)

| Артикул | Название в каталоге |
|---|---|
| 00000031048 | Модуль памяти Kingston HyperX Fury HX434C16FB3/8 |

Это модуль памяти Kingston под брендом HYPERX; сайт hyperx.com — магазин игровой периферии. **Решение нужно:** перенести под Kingston, отправить на ручную проверку или оставить как есть.
