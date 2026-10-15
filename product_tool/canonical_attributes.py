"""Shared presentation vocabulary; never changes source identity or fact resolution."""
from __future__ import annotations
import copy,re
from decimal import Decimal,InvalidOperation

# These labels/sections were observed in the frozen Stage 81 live source inventory.
LABELS={
 'Adaptive Triggers':'Адаптивные триггеры','Haptic Feedback':'Тактильная отдача','Eco Mode':'Экономичный режим',
 '1000Hz Ultrapolling':'Частота опроса Ultrapolling, 1000 Гц','Hyperesponse Button':'Кнопки Hyperesponse',
 'Party Kick Starter Sampler creator':'Создание семплов Party Kick Starter','Sleep Timer+':'Таймер сна Sleep Timer+',
 '4-in-1 Care Filter':'Фильтр 4-in-1 Care','Active Wear':'Программа для спортивной одежды',
 'Anti-Cliff':'Защита от падения','Auto Mode':'Автоматический режим',
 'Auto Source Switch':'Автоматическое переключение источника','Auto-Rotation Accessory Support':'Поддержка аксессуара автоматического поворота',
 'Bluetooth Audio':'Аудио по Bluetooth','Bluetooth ver. 4.0 (Rx/Tx)':'Bluetooth 4.0 (приём/передача)',
 'Burner - Left Front':'Передняя левая конфорка','Burner - Left Rear':'Задняя левая конфорка',
 'Burner - Right Front':'Передняя правая конфорка','Burner - Right Rear':'Задняя правая конфорка',
 'Cancel and Drain Button':'Кнопка отмены и слива','Cloudy Day':'Программа для пасмурного дня',
 'Copper Anti-bacterial Filter':'Медный антибактериальный фильтр','Deep Sleep':'Режим глубокого сна',
 'Energy Consumption':'Энергопотребление','Energy Grade (ERP)':'Класс энергоэффективности (ERP)',
 'Energy Grade (IEC)':'Класс энергоэффективности (IEC)','Fold Down Tines':'Складные держатели',
 'Foldable Cup Shelves':'Складные полки для чашек','Gross Weight (kg)':'Вес с упаковкой, кг',
 'HDMI (High Frame Rate)':'HDMI с высокой частотой кадров','HDMI Audio Return Channel':'Обратный аудиоканал HDMI',
 'HDMI In':'Вход HDMI','HDMI Out':'Выход HDMI','HVAC Type':'Тип климатической системы',
 'Intense Cold':'Программа для сильного холода','Net Weight (kg)':'Вес товара, кг',
 'Optical In':'Оптический вход','PM 1.0 Filter':'Фильтр PM 1.0','Pass-through':'Сквозная передача сигнала',
 'Pass-through (4K)':'Сквозная передача 4K','Power Level':'Уровень мощности','Power On/Off':'Включение и выключение',
 'Product Type II':'Тип товара (классификация II)','Refrigerant (Charging)(kg)':'Масса заправленного хладагента, кг',
 'Set Weight (kg)':'Вес товара, кг','Shirts':'Программа для рубашек','Slim':'Программа Slim',
 'Storage Memory':'Ёмкость памяти','Surround Sound':'Объёмный звук','Wash Performance':'Класс качества стирки',
 'Water Consumption per Cycle':'Расход воды за цикл','Wi-Fi Kit':'Комплект Wi-Fi','Wireless Subwoofer Included':'Беспроводной сабвуфер в комплекте',
 'Smart Things':'SmartThings',
 'AI Auto Game Mode':'Автоматический игровой режим с ИИ','Active Voice Amplifier':'Усиление голоса Active Voice Amplifier',
 'AI Motion Enhancer':'Улучшение движения AI Motion Enhancer','Adaptive Picture':'Адаптивное изображение',
 'Art Store':'Магазин произведений искусства Art Store','Auto HDR Remastering':'Преобразование в HDR',
 'Color Booster':'Улучшение цвета Color Booster','Dynamic Black EQ':'Динамический эквалайзер чёрного',
 'EyeComfort Mode':'Режим защиты зрения EyeComfort','HDR Brightness Optimizer':'Оптимизация яркости HDR',
 'Mini Map Zoom':'Увеличение мини-карты','Multi-View':'Мультиэкранный режим',
 'One Remote':'Единый пульт One Remote','Super Ultra Wide Game View':'Сверхширокий игровой режим',
 'Voice Enhance Mode':'Режим усиления голоса','SmartThings Hub / Matter Hub / IoT-Sensor Functionality / Quick Remote':'Хаб SmartThings и Matter, IoT-датчики и Quick Remote',
 'Accessory Compatibility':'Совместимость с аксессуарами','Additional Game Keys':'Дополнительные игровые клавиши',
 'Audio Pass-Through':'Сквозной аудиовыход','Backlighting':'Подсветка','Cable':'Кабель',
 'Dedicated Media Controls':'Отдельные мультимедийные элементы управления','Fully-Programmable Keys':'Полностью программируемые клавиши',
 'Key Feel':'Ощущение от нажатия клавиш','Key Roll-over':'Одновременное нажатие клавиш',
 'Keyboard Height':'Высота клавиатуры','Keyboard Size':'Формат клавиатуры','Max Sensitivity (DPI)':'Максимальная чувствительность, DPI',
 'Media Keys':'Мультимедийные клавиши','Onboard Memory':'Встроенная память','Passthrough':'Сквозное подключение',
 'Platform':'Платформа','Polling Rate / Interval':'Частота или интервал опроса','Product family':'Семейство товара',
 'Purpose':'Назначение','RGB Lighting':'RGB-подсветка','Scroll Wheel':'Колесо прокрутки',
 'Sensor Technology':'Технология сенсора','Size':'Размер','Switch Lifecycle':'Ресурс переключателей',
 'Switches / Keys':'Переключатели и клавиши','Tilt Scroll Wheel':'Наклонное колесо прокрутки',
 'EMC':'Электромагнитная совместимость (EMC)','TCO Certified':'Сертификация TCO','IP Control':'Управление по IP',
 'App Support':'Поддержка приложения','Artwork customization':'Настройка оформления','Audio':'Аудио','Audio output':'Аудиовыход',
 'Cable Length':'Длина кабеля','Camera':'Камера','Carry case':'Чехол для переноски','Chassis':'Корпус','Compatibility':'Совместимость',
 'Connection type':'Тип подключения','Controllers':'Контроллеры','Driver specifications':'Параметры динамика','Driver type':'Тип динамика',
 'Earcups':'Амбушюры','Earpads material':'Материал амбушюр','Game Mode':'Игровой режим','Home':'Домашний режим',
 'I/O Ports':'Порты ввода и вывода','Inner Earcup Diameter':'Внутренний диаметр амбушюры','Interchangeable Dpad':'Сменная крестовина',
 'Interchangeable Thumbsticks':'Сменные стики','Keyboard and Touchpad':'Клавиатура и тачпад',
 'Microphone Frequency Response':'Диапазон частот микрофона','Microphone Input':'Вход микрофона','Microphone Sensitivity (@1kHz)':'Чувствительность микрофона (1 кГц)',
 'Microphone Style':'Тип микрофона','Network and Communication':'Сеть и связь','Noise Cancelling':'Шумоподавление',
 'Other Controls':'Дополнительные элементы управления','Pick-up Pattern':'Диаграмма направленности','Power Supply':'Питание',
 'Quick Control Panel':'Панель быстрого управления','Screen Technology':'Технология экрана','Screen Type':'Тип экрана',
 'Software':'Программное обеспечение','Spatial Sound':'Пространственный звук','System requirement':'Системные требования',
 'Virtual Surround Encoding':'Кодирование виртуального объёмного звука','Volume Control':'Управление громкостью','Warranty':'Гарантия',
}
LABELS={k.casefold():v for k,v in LABELS.items()}
LABELS.update({'oval ear cushions':'Овальные амбушюры','sensitivity (@1 khz)':'Чувствительность (1 кГц)','signal-to-noise ratio':'Отношение сигнал/шум'})
LABELS.update({k.casefold():v for k,v in {'Noise level':'Уровень шума','Sound level':'Уровень шума','Operating noise':'Уровень шума','Operating temperature':'Рабочая температура','Operating Humidity':'Влажность при эксплуатации','Storage Temperature':'Температура хранения','Storage Humidity':'Влажность при хранении','Item Dimensions':'Габариты робота','Stand (Design)':'Конструкция подставки','Stand (Material)':'Материал подставки','Obstacle Crossing Height':'Высота преодолеваемых препятствий','CPU':'Процессор','GPU':'Графический процессор','Battery Life':'Время работы','Connectivity':'Подключение','Environmental Requirements':'Условия эксплуатации'}.items()})
SECTIONS={
 'Audio Calling':'Аудиозвонки','Buttons and Connectors':'Кнопки и разъёмы','Controls':'Управление',
 'Health and Wellness':'Здоровье','Location':'Определение местоположения','Video Calling':'Видеозвонки',
 'Video Recording':'Запись видео','Apple Intelligence':'Интеллектуальные функции','Siri':'Голосовой помощник Siri',
 'App Connectivity':'Подключение к приложениям','Battery and Power':'Аккумулятор и питание',
 'Power and Battery':'Аккумулятор и питание','Camera':'Камера','Front Camera':'Фронтальная камера',
 'Cellular and Wireless':'Мобильная и беспроводная связь','Charging and Expansion':'Разъёмы и зарядка',
 'Chip':'Процессор','Configuration':'Конфигурация','Display':'Экран','Memory':'Память',
 'Storage':'Накопитель','Sensors':'Датчики','Size and Weight':'Габариты и вес',
 'Splash, Water, and Dust Resistant':'Защита от воды и пыли','TrueDepth Camera':'Фронтальная камера TrueDepth',
 'Wireless':'Беспроводная связь','Hi-Resolution Audio':'Аудио высокого разрешения',
 'MagSafe and Wireless Charging':'MagSafe и беспроводная зарядка','Smart':'Умные функции',
 'Specifications':'Основные характеристики','General Specifications':'Основные характеристики',
 'FullSpecification':'Основные характеристики','Other':'Другие характеристики',
 'Connectivity':'Подключение','Headphone Specifications':'Наушники','Microphone Specifications':'Микрофон',
 'Headphones':'Наушники','Microphone':'Микрофон','Keyboard':'Клавиатура','Mouse':'Мышь',
 'Dimensions':'Габариты и вес','Weight':'Габариты и вес','Features':'Особенности модели',
 'Display Support':'Подключение дисплеев','Video Playback':'Воспроизведение видео',
 'Audio Playback':'Воспроизведение аудио','Keyboard and Trackpad':'Клавиатура и тачпад',
 'Audio':'Аудио','Operating Requirements':'Условия эксплуатации','Operating System':'Операционная система',
 'Accessibility':'Специальные возможности','Built-in Apps':'Встроенные приложения','Acoustic Performance':'Шум',
 'Audio Technology':'Аудиотехнологии','Battery':'Аккумулятор','Controller Specifications':'Контроллер',
 'Dust, Sweat, and Water Resistant':'Защита от пыли, пота и воды','Performace':'Производительность',
 'Power and Battery Life':'Питание и автономность','Face ID':'Распознавание лица Face ID','Touch ID':'Сканер отпечатка Touch ID',
 'MagSafe':'MagSafe и зарядка',
}
GROUP_ALIASES={
 'размеры':'Габариты и вес','вес':'Габариты и вес','размеры / вес':'Габариты и вес',
 'физические характеристики':'Габариты и вес','изображение (дисплей)':'Экран','дисплей':'Экран',
 'аудиоформат':'Аудио','звук':'Аудио','формат декодирования':'Аудио',
 'подключения':'Подключение','возможности подключения':'Подключение','интерфейс':'Интерфейсы',
 'умная технология':'Умные функции','умные технологии':'Умные функции','интеллектуальные функции':'Умные функции',
 'смарт-технология':'Умные функции','смарт функции':'Умные функции','смарт-технологии':'Умные функции',
 'общая информация':'Основные характеристики','общие сведения':'Основные характеристики','общие характеристики':'Основные характеристики',
 'общее':'Основные характеристики','обзор':'Основные характеристики','базовые характеристики':'Основные характеристики',
 'энергия':'Энергопотребление','потребление электроэнергии':'Энергопотребление',
 'телевещание':'Тюнеры','тюнер':'Тюнеры','тюнер / телевещание':'Тюнеры',
 'особенности':'Особенности модели','память/хранилище':'Память и накопитель',
 'габариты товара':'Габариты и вес','габариты':'Габариты и вес','упаковка':'Габариты и вес',
 'энергия — шкала и период источника':'Энергопотребление','прочие характеристики':'Другие характеристики',
}

def label_ru(label):
    text=' '.join(str(label or '').split())
    if re.match(r'^(?:Высота|Ширина|Глубина)\b',text,re.I):text=re.sub(r'\s*\((?:height|width|depth)\)$','',text,flags=re.I)
    return LABELS.get(text.casefold(),text)

def parent_group(section):
    text=' '.join(str(section or '').split())
    if re.match(r'Характеристики оборудования CFI-',text):text='Характеристики оборудования'
    if re.match(r'Оптический привод CFI-',text):text='Оптический привод'
    text=text[:1].upper()+text[1:].lower() if text.isupper() else text
    translated=next((v for k,v in SECTIONS.items() if k.casefold()==text.casefold()),text)
    return GROUP_ALIASES.get(translated.casefold(),translated) or 'Другие характеристики'

def color_result(product,rows,sources,evidence=None):
    """Color requires admitted configuration evidence; input hints stay separate."""
    values=[];proof=[]
    for row in rows:
        name=row['normalized_name'];r=row.get('resolved') or {}
        if name not in {'color','цвет','outcase_color','цвет_корпуса','colour','color__body','body_color'}:continue
        if r.get('conflict') or r.get('selected_unit') in {'bool','unknown'}:continue
        if not (r.get('full_sku_confirmed') or r.get('status')=='configuration_confirmed_official'):continue
        if r.get('display_value'):
            values.append(r['display_value']);proof.extend({'source':f.get('source_key'),'label':f.get('raw_name'),'raw_value':f.get('raw_value')} for f in row.get('sources',{}).values())
    ev=evidence or {};config=ev.get('configuration_fields',{})
    brand=product['brand'].strip().casefold();identity=ev.get('identity',{})
    if brand=='jbl' and identity.get('model_confirmed') and identity.get('color') and identity.get('requested_components',{}).get('color','').casefold()==identity['color'].casefold():
        values.append(identity['color']);proof.append({'source':next((s['url'] for s in sources if s['source_key']=='jbl'),''),'relation':'Official PDP selected color agrees with requested and returned model/color relation','reported_color':identity['color']})
    if brand=='razer' and identity.get('configuration_relation')=='configuration_confirmed':
        matches=[r for r in ev.get('retail_relations',[]) if r.get('model_confirmed') and r.get('requested_configuration_matches')]
        colors={r.get('options',{}).get('color','') for r in matches}
        if len(colors)==1 and '' not in colors:
            values.extend(colors);proof.extend({'source':r.get('source_url'),'retail_sku':r.get('retail_sku'),'options':r.get('options'),'relation':'Explicit official retail node matches requested configuration'} for r in matches)
    if product['brand'].strip().casefold()=='apple' and config.get('color') and ev.get('identity',{}).get('configuration') in {'exact_order_record','exact_order_sku','full_sku','exact_order_product'}:
        values.append(config['color']);proof.extend(p for p in ev.get('configuration_proofs',[]) if p.get('field')=='color')
    unique=list(dict.fromkeys(v.strip() for v in values if v.strip()))
    translations={'black':'Чёрный','white':'Белый','silver':'Серебристый','blue':'Синий','pink':'Розовый','red':'Красный','green':'Зелёный'}
    unique=list(dict.fromkeys(translations.get(v.casefold(),v) for v in unique))
    return {'value':unique[0] if len(unique)==1 else 'не подтверждён','confirmed':len(unique)==1,'proof':proof,'candidates':unique if len(unique)>1 else []}

def project(rows):
    """Localize labels and expose schema lineage without inventing missing values."""
    result=[]
    for original in rows:
        if any(re.fullmatch(r'(?i)safety and product resources|bar.?code|ean|штрих.?код',str(f.get('raw_name','')).strip()) for f in original.get('sources',{}).values()):continue
        row=copy.deepcopy(original);row['display_name']=label_ru(row.get('display_name',''))
        row['canonical_presentation']=True
        source=(row.get('sources') or {}).get((row.get('resolved') or {}).get('selected_source')) or next(iter((row.get('sources') or {}).values()),{})
        section=row.get('section_name') or source.get('section','')
        if row.get('jbl_presentation'):
            from .jbl_presentation import section as translate_section
            section=translate_section(section)
        elif row.get('lg_presentation'):
            from .lg_presentation import canonical_section
            section=canonical_section(section)
        elif row.get('hyperx_presentation'):
            from .hyperx_presentation import SECTIONS as known_sections
            section=known_sections.get(section,section)
        row['parent_group']=parent_group(section)
        from .semantic_decomposition import field_spec
        from .value_localization import content_classification,localize,semantic_display
        semantic=field_spec(row['normalized_name'])
        classification=content_classification(row['display_name'],section,source.get('raw_value',''))
        if classification=='support_prose':continue
        if classification=='compatibility':row['parent_group']='Совместимость и системные требования'
        if semantic:
            row['display_name']=semantic[0];row['parent_group']=semantic[1];row['canonical_role']=semantic[2];row['semantic_decomposition']=True
        component=re.match(r'^(Наушники|Микрофон):\s*(.+)$',row['display_name'])
        if component:
            row['parent_group']=component[1];row['display_name']=label_ru(component[2])
        if row['display_name']=='Чувствительность наушников':row['parent_group']='Наушники'
        component_quantity=bool(re.fullmatch(r'(?:Диапазон частот|Частотный диапазон|Чувствительность|Сопротивление)(?:\s*\([^)]*\))?',row['display_name']))
        if row['parent_group']=='Микрофон' and component_quantity:row['display_name']+=' микрофона'
        elif row['parent_group']=='Наушники' and component_quantity:row['display_name']+=' наушников'
        if re.search(r'^(?:ширина|высота|глубина|вес|масса|габарит|размеры\b)',row['display_name'],re.I):row['parent_group']='Габариты и вес'
        row['category_attribute_key']=row['parent_group']+' / '+row['display_name']
        from .attribute_lineage import technical_role
        if technical_role(row['display_name'],row['parent_group'])=='feature':row['canonical_role']='feature'
        resolved=row.get('resolved') or {}
        if semantic:
            semantic_value=resolved.get('selected_value','')
            if not resolved.get('selected_unit') and source:
                from .semantic_decomposition import decompose
                from .adapters.common import RawAttribute
                children=decompose(RawAttribute(source.get('raw_name',''),source.get('raw_value',''),source.get('section','')))
                original_child=next((c for c in children or [] if c.key==row['normalized_name'] and c.value.casefold()==semantic_value),None)
                if original_child:semantic_value=original_child.value
            row['resolved']={**resolved,'display_value':semantic_display(semantic_value,resolved.get('selected_unit','')) if semantic_value else resolved.get('display_value','')}
        elif resolved.get('selected_unit')=='' and resolved.get('status')!='manual' and source.get('raw_value') and not (row.get('refined_from') or row.get('derived_from')):
            shown=source['raw_value']
            shown=re.sub(r'\bXBOX\b','Xbox',shown)
            shown=re.sub(r'\bup to\b','До',shown,flags=re.I)
            for unit,replacement in (('hours?','ч'),('minutes?','мин'),('mm','мм'),('kg','кг'),('mAh','мА·ч'),('Wh','Вт·ч'),('MHz','МГц'),('GHz','ГГц'),('kHz','кГц'),('Hz','Гц'),('Mbps','Мбит/с'),('ml','мл'),('dB','дБ'),('Pa','Па')):
                shown=re.sub(r'(?<![A-Za-z])'+unit+r'(?![A-Za-z])',replacement,shown,flags=re.I)
            # Single-letter units need an explicit number, so prose and model
            # names containing L/W/G are not rewritten.
            shown=re.sub(r'(\d(?:[\d.,\s]*\d)?)\s*(g|W|L)\b',lambda m:m[1]+' '+{'g':'г','W':'Вт','L':'л'}[m[2]],shown)
            row['resolved']={**resolved,'display_value':localize(shown)}
        result.append(row)
    return result
