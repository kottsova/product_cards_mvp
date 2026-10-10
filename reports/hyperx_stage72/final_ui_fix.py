"""Scoped replacement of legacy LG captions on HyperX cards."""
from pathlib import Path
p=Path('product_tool/templates/product.html');text=p.read_bytes().decode('utf8')
pairs=[
 ("'Только у модели/серии Lenovo' if lenovo_card else","'Общие характеристики модели HyperX' if hyperx_card else 'Только у модели/серии Lenovo' if lenovo_card else"),
 ('{{ counts.official_base_only }}',"{{ hyperx_evidence.accepted_specs|selectattr('scope','equalto','model')|list|length if hyperx_card else counts.official_base_only }}"),
 ('{{ jbl_card.confirmed_specs if jbl_card else counts.supplier_confirmed }}','{{ hyperx_card.confirmed_specs if hyperx_card else jbl_card.confirmed_specs if jbl_card else counts.supplier_confirmed }}'),
 ("'Подтверждено для точной модели JBL' if jbl_card else","'Подтверждено для HyperX' if hyperx_card else 'Подтверждено для точной модели JBL' if jbl_card else"),
 ("{% elif s.match_level == 'full_sku' %}","{% elif s.source_key == 'hyperx' and s.match_level == 'exact_variant' %}Полный SKU HyperX{% elif s.source_key == 'hyperx' and s.match_level == 'model_confirmed' %}Точная модель HyperX{% elif s.match_level == 'full_sku' %}"),
 ('{{ r.options }}',"{% for key,value in r.options.items() %}{{ {'Color':'Цвет','Layout':'Раскладка','Switch':'Переключатели'}.get(key,key) }}: {{ value }}{% if not loop.last %}; {% endif %}{% endfor %}"),
]
for old,new in pairs:
 assert text.count(old)==1,(old,text.count(old))
 text=text.replace(old,new)
p.write_bytes(text.encode('utf8'))
