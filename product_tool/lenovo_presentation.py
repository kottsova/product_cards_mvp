"""Russian Lenovo projection; raw labels and values stay in shared facts."""
from . import lg_presentation
LABELS={
 'Processor':'Процессор','Memory':'Оперативная память','Operating System':'Операционная система',
 'Hard Drive':'Накопитель','Graphics':'Видеокарта','Monitor':'Дисплей','Display':'Дисплей','Ports':'Разъёмы',
 'Wireless Network':'Беспроводные интерфейсы','Wired Network':'Проводная сеть','Camera':'Камера',
 'Form Factor':'Форм-фактор','Battery':'Аккумулятор','Keyboard':'Клавиатура','Color':'Цвет',
 'Dimensions':'Габариты товара','Weight':'Вес товара, кг','Net Weight':'Вес товара, кг',
 'Included Accessories':'Комплектация','Storage':'Накопитель','RAM':'Оперативная память',
 'CPU':'Процессор','GPU':'Видеокарта','WLAN + Bluetooth':'Беспроводные интерфейсы',
 'Standard Ports':'Разъёмы','Optional Ports (configured)':'Разъёмы дополнительной конфигурации',
 'Product Dimensions (WxDxH)':'Габариты товара','Packaging Dimensions (WxDxH)':'Габариты упаковки',
 'Packaging Weight':'Вес с упаковкой, кг','Dimensions (WxDxH)':'Габариты товара'}
LABELS={k.casefold():v for k,v in LABELS.items()}

def label(raw):
    return LABELS.get(raw.casefold(),raw)

def section(raw):
    name=raw.casefold()
    if any(x in name for x in ('dimension','weight','габарит','вес')):return 'Габариты и вес'
    return 'Конфигурация' if name in {'configuration',''} else raw

def project(rows):
    result=[]
    for original in rows:
        row={**original,'lenovo_presentation':True}
        raw=(row.get('sources',{}).get('lenovo_support') or {}).get('raw_name') or next(iter(row.get('raw_names',[])),row['display_name'])
        row['display_name']=label(raw)
        row=lg_presentation.normalize_measure(row)
        derived=lg_presentation.split_dimensions(row)
        if derived:result.extend({**x,'lenovo_presentation':True} for x in derived)
        else:result.append(row)
    return result

VERDICTS={'not_ready':'Не готова','export_ready_with_gaps':'Готова с пробелами','export_ready':'Готова'}
GAPS={'exact_configuration_not_resolved':'Точная конфигурация не подтверждена','exact_specifications_missing':'Нет подтверждённых характеристик','exact_gallery_not_confirmed':'Связь фото с конфигурацией не подтверждена','russian_user_guide_not_verified':'Русское руководство пользователя не проверено','unresolved_conflicts':'Есть неразрешённые расхождения'}
SCOPES={'family_model':'Модель/серия','family_option':'Возможность серии','conditional_configuration':'Зависит от конфигурации','unknown':'Связь не установлена','exact_mtm':'Точный MTM','exact_part_number':'Точный артикул'}

def gap_labels(readiness):
    return [GAPS.get(g,g) for g in readiness['gaps']]
