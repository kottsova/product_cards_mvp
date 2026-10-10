"""Russian labels for HyperX evidence; branded values and raw facts remain intact."""
import re
from . import lg_presentation

LABELS={
 'Driver':'Динамик','Form Factor':'Конструкция','Frequency Response':'Диапазон частот','Sensitivity':'Чувствительность','T.H.D':'Коэффициент гармонических искажений','Frame Type':'Материал каркаса','Ear Cushions':'Амбушюры','Element':'Тип капсюля','Polar Pattern':'Диаграмма направленности',
 'Boom Mic Element':'Тип выносного микрофона','Boom Mic Polar Pattern':'Направленность выносного микрофона','Boom Mic Sensitivity':'Чувствительность выносного микрофона','Built-In Mic Element':'Тип встроенного микрофона','Built-In Mic Polar Pattern':'Направленность встроенного микрофона','Built-In Mic Frequency Response':'Диапазон частот встроенного микрофона','Built-In Mic Sensitivity':'Чувствительность встроенного микрофона',
 'USB Specification':'Стандарт USB','Bit-Depth':'Разрядность','Audio Controls':'Управление звуком','Battery Life':'Автономность (заявленный максимум)','Charge Time':'Время зарядки','Bluetooth Version':'Версия Bluetooth','Wireless Range':'Дальность беспроводной связи','Supported Bluetooth Codecs':'Поддерживаемые кодеки Bluetooth','Supported Bluetooth Profiles':'Профили Bluetooth','Battery Type':'Тип аккумулятора',
 'Switch':'Переключатели','Actuation Point':'Точка срабатывания','Backlight':'Подсветка','Light Effects':'Эффекты подсветки','Onboard Memory':'Встроенная память','Polling Rate':'Частота опроса','Rollover':'Одновременное нажатие клавиш','Acceleration':'Ускорение','Game Mode':'Game Mode','OS Compatibility':'Совместимость с ОС','Connectivity':'Подключение','Compatibility':'Совместимость','Operation Style':'Тип срабатывания','Total Travel Distance':'Полный ход клавиши',
 'Shape':'Форма','Sensor':'Сенсор','Resolution':'Разрешение сенсора','DPI Presets':'Предустановки DPI','Speed':'Скорость отслеживания','Buttons':'Кнопки','Left / Right Button Switches':'Переключатели основных кнопок','Left / Right Button Durability':'Ресурс основных кнопок','Connection Type':'Тип подключения',
 'Width':'Ширина','Height':'Высота','Depth':'Глубина','Length':'Длина','Weight':'Вес (с сохранением состава измерения)','Cable Type':'Тип кабеля','Cable Length (imperial) and type':'Длина и тип кабеля','SNR':'Отношение сигнал/шум','Self-noise (RMS)':'Собственный шум (RMS)','Color':'Цвет','Layout':'Раскладка клавиатуры','SKU':'Коммерческий SKU',
}
SECTIONS={'Headphone Specifications':'Наушники','Microphone Specifications':'Микрофон','Microphone Specification':'Микрофон','Keyboard Specifications':'Клавиатура','Switch Specifications':'Переключатели','Mouse Specifications':'Мышь','Physical Specifications':'Габариты и вес','Connections and Features':'Подключение и функции','Battery Specifications':'Аккумулятор','Wireless Specifications':'Беспроводная связь','Variant configuration':'Конфигурация'}
GAPS={'model_identity_missing':'Модель не подтверждена','specifications_missing':'Недостаточно подтверждённых характеристик','gallery_missing':'Нет подтверждённого фото нужного варианта','configuration_unproven':'Коммерческий вариант не подтверждён','conflicts':'Есть конфликт фактов'}

def label(raw):
    if raw in LABELS:
        return LABELS[raw]
    base=raw.split(' (',1)[0];result=LABELS.get(base,base)
    if 'microphone' in raw.casefold():result+=' микрофона'
    elif ' (' in raw:
        context=raw.split(' (',1)[1].rstrip(')')
        context=re.sub(r'\s*#\d+','',context)
        result+=' ('+SECTIONS.get(context,context)+')'
    return result

def project(rows):
    for index,row in enumerate(rows):
        fact=row.get('sources',{}).get('hyperx',{})
        row['display_name']=label(fact.get('raw_name','') or row['display_name'])
        row['hyperx_presentation']=True
        row=lg_presentation.normalize_measure(row)
        rows[index]=row
        for value in [row.get('resolved') or {},*row.get('sources',{}).values()]:
            if value.get('display_value'):
                value['display_value']=re.sub(r'(?i)\bup[- ]to\s*','До ',value['display_value'])
                value['display_value']=re.sub(r'(?i)\bhours?\b','ч',value['display_value'])
                for brand in ('DTS Headphone:X','NGENUITY','HyperX Dual Chamber Drivers','HyperX Mechanical Switches','Rapid Trigger','Game Mode'):
                    value['display_value']=re.sub(re.escape(brand),brand,value['display_value'],flags=re.I)
    return rows
