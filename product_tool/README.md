# Импортёр Excel

`importer.py` читает `.xlsx` без изменения файла и выводит JSON с брендом, кодом поиска, категорией, номером исходной строки и признаками, требующими подтверждения. Он не запускает парсер сайтов.

Установка и проверки из корня проекта:

```powershell
python -m pip install -r .\product_tool\requirements.txt
python -m unittest discover -s tests -v
```

Предпросмотр локального файла:

```powershell
python -m product_tool.importer 'C:\путь\к\товарам.xlsx'
```

Для ручного сопоставления доступны `--sheet`, `--header-row`, `--brand-col`, `--code-col`, `--fallback-col`, `--name-col` и `--category-col`. Номера колонок считаются с 1; `--header-row 0` указывает на книгу без заголовков. Код продавца и запасная модель сохраняются раздельно, если они отличаются.
