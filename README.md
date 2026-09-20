# Product Cards MVP

Внутренний инструмент для загрузки товаров из Excel и подготовки карточек. Сейчас в проекте есть автономный импортёр: он читает `.xlsx`, предлагает соответствие колонок и выводит предпросмотр бренда, кода и категории. Исходный файл не изменяется; поиск на сайтах пока не подключён.

## Структура

- `product_tool/importer.py` — чтение Excel и предпросмотр товаров.
- `product_tool/README.md` — параметры импортёра.
- `tests/` — автономные проверки на временных, созданных тестом книгах Excel.
- `docs/` — архитектура MVP и рабочие сценарии.

## Запуск в Windows PowerShell

Из корня проекта:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\product_tool\requirements.txt
python -m unittest discover -s tests -v
```

Предпросмотр своего файла:

```powershell
python -m product_tool.importer 'C:\путь\к\товарам.xlsx'
```

Если заголовки или колонки определены неверно, можно указать их вручную:

```powershell
python -m product_tool.importer 'C:\путь\к\товарам.xlsx' --sheet 'Товары' --header-row 2 --category-col 1 --brand-col 2 --name-col 3 --code-col 4 --fallback-col 5
```

Номера колонок начинаются с 1. `--header-row 0` означает файл без заголовков. В выводе `needs_confirmation: true` помечает строки, где важные поля извлечены из названия или не определены.

Реальные книги Excel, выгрузки, базы данных и секреты исключены из Git. Следующий этап — страница загрузки Excel и подтверждения предпросмотра.
