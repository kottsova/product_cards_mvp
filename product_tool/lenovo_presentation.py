"""Russian Lenovo projection; raw labels and values stay in shared facts."""
import re
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
 'Packaging Weight':'Вес с упаковкой, кг','Dimensions (WxDxH)':'Габариты товара',
 'Display Size':'Диагональ экрана','View Area':'Размер видимой области','Panel':'Тип матрицы','Backlight':'Подсветка',
 'Aspect Ratio':'Соотношение сторон','Resolution':'Разрешение экрана','Pixel Pitch':'Шаг пикселя','Dot / Pixel Per Inch':'Плотность пикселей',
 'View Angle (H / V)':'Угол обзора по горизонтали и вертикали','Response Time':'Время отклика','Color Support':'Количество цветов',
 'Refresh Rate':'Частота обновления','Brightness':'Яркость','Contrast Ratio':'Контрастность','Color Gamut':'Цветовой охват',
 'Screen Surface Treatment':'Покрытие экрана','Curvature':'Кривизна экрана','Microphone':'Микрофон','Speakers':'Динамики',
 'Power Consumption (Typical / Maximum)':'Потребляемая мощность, типичная и максимальная','Power Adapter':'Адаптер питания',
 'Stand':'Подставка','Case Color':'Цвет корпуса','Case Material':'Материал корпуса','Side Bezel Width':'Ширина рамки',
 'Mounting':'Крепление','Rear Ports':'Задние разъёмы','Front Ports':'Передние разъёмы','In the Box':'Комплектация',
 'Environmental Certification':'Экологические сертификаты','Ergonomic Certification':'Эргономические сертификаты',
 'Green Certifications':'Экологические сертификаты','Other Certifications':'Другие сертификаты','Sync Technology':'Технология синхронизации',
 'Special Features':'Дополнительные возможности','Memory Slots':'Слоты памяти','Storage Slot':'Разъём накопителя',
 'Optical':'Оптический привод','Audio Chip':'Аудиокодек','Ethernet':'Проводная сеть','Card Reader':'Картридер','Touchpad':'Тачпад',
 'Touchscreen':'Сенсорный экран','Fingerprint Reader':'Сканер отпечатка пальца','Security Chip':'Модуль безопасности',
 'Physical Locks':'Физические замки','Kensington Cable Lock':'Замок Kensington','Other Security':'Дополнительные средства защиты',
 'Chassis Intrusion Switch':'Датчик вскрытия корпуса','Power Supply':'Блок питания','Mouse':'Мышь',
 'Expansion Slots':'Слоты расширения','Chipset':'Чипсет','Bundled Accessories':'Аксессуары в комплекте',
 'Bundled Software':'ПО в комплекте','Included Upgrade':'Включённое обновление','Pen':'Стилус','Sensors':'Датчики',
 'Location Services':'Определение местоположения','Vibration Motor':'Вибромотор','VoiceCall':'Голосовые вызовы',
 'SIM Card':'SIM-карта','Smart Card Reader':'Считыватель смарт-карт','WWAN':'Мобильная связь','NPU':'Нейронный процессор',
 'AI PC Category':'Категория AI PC','Color Calibration':'Калибровка цвета','Screen-to-Body Ratio':'Соотношение экрана и корпуса',
 'Surface Treatment':'Покрытие корпуса','Mil-Spec Test':'Испытания MIL-STD','System Management':'Управление системой',
 'Docking':'Док-станция','Monitor Cable':'Кабель монитора','Dust Filter':'Пылевой фильтр','Adapter Cage':'Крепление адаптера',
 'Toolless Chassis Screw':'Винт корпуса без инструмента','IO Box':'Модуль разъёмов','Optional Front Ports (configured)':'Дополнительные передние разъёмы конфигурации',
 'Optional Rear Ports (configured)':'Дополнительные задние разъёмы конфигурации','ThinkCentre M Series Support':'Совместимость с ThinkCentre M'}
LABELS={k.casefold():v for k,v in LABELS.items()}

def label(raw):
    return LABELS.get(raw.casefold(),raw)

def section(raw):
    name=raw.casefold()
    if any(x in name for x in ('dimension','weight','габарит','вес')):return 'Габариты и вес'
    return {'configuration':'Конфигурация','':'Конфигурация','performance':'Производительность','design':'Конструкция',
            'connectivity':'Подключение','accessories':'Комплектация','certifications':'Сертификация',
            'security & privacy':'Безопасность и конфиденциальность','software':'Программное обеспечение','manageability':'Управление'}.get(name,raw)

def project(rows):
    result=[]
    for original in rows:
        row={**original,'lenovo_presentation':True}
        raw=(row.get('sources',{}).get('lenovo_psref') or row.get('sources',{}).get('lenovo_support') or {}).get('raw_name') or next(iter(row.get('raw_names',[])),row['display_name'])
        row['display_name']=label(raw)
        selected=(row.get('resolved') or {}).get('selected_source')
        selected_fact=row.get('sources',{}).get(selected,{})
        row['section_name']=section(selected_fact.get('section',''))
        row=lg_presentation.normalize_measure(row)
        dimension_row=row
        if 'dimensions' in raw.lower() and selected=='lenovo_psref':
            value=selected_fact.get('raw_value','')
            metric=re.fullmatch(r'\s*(\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?\s*mm)\s*(?:\([^)]*(?:inch|inches)[^)]*\))?\s*',value,re.I)
            if metric:dimension_row={**row,'normalized_name':'package_dimensions' if 'packaging' in raw.lower() else 'product_dimensions','sources':{**row['sources'],selected:{**selected_fact,'raw_value':metric[1]}}}
        derived=lg_presentation.split_dimensions(dimension_row)
        if derived:
            for item in derived:
                item['derived_from']=row['normalized_name']
                for key,fact in item['sources'].items():fact['raw_value']=row['sources'][key]['raw_value']
        if derived:result.extend({**x,'lenovo_presentation':True} for x in derived)
        else:result.append(row)
    return result

VERDICTS={'not_ready':'Не готова','export_ready_with_gaps':'Готова с пробелами','export_ready':'Готова'}
GAPS={'exact_configuration_not_resolved':'Точная конфигурация не подтверждена','exact_specifications_missing':'Нет подтверждённых характеристик','exact_gallery_not_confirmed':'Связь фото с конфигурацией не подтверждена','verified_gallery_not_selected':'Подтверждённое фото не выбрано','russian_user_guide_not_verified':'Русское руководство пользователя не проверено','unresolved_conflicts':'Есть неразрешённые расхождения'}
SCOPES={'family_model':'Модель/серия','family_option':'Возможность серии','conditional_configuration':'Зависит от конфигурации','unknown':'Связь не установлена','exact_mtm':'Точный MTM','exact_part_number':'Точный артикул'}

def gap_labels(readiness):
    return [GAPS.get(g,g) for g in readiness['gaps']]
