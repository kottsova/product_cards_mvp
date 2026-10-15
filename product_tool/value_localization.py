"""Conservative Russian display terms. Raw/normalized evidence remains unchanged."""
import re

PHRASES={
 'Enabled by TrueDepth technology in the Center Stage front camera':'Работает с технологией TrueDepth во фронтальной камере Center Stage',
 'Hearing Aid Compatible':'Совместим со слуховыми аппаратами',
 'Support for display of multiple languages and characters simultaneously':'Одновременное отображение нескольких языков и символов',
 'Fingerprint-resistant oleophobic coating':'Олеофобное покрытие, устойчивое к отпечаткам пальцев',
 'Hardware-accelerated ray tracing':'Аппаратная трассировка лучей',
 'ProMotion technology with adaptive refresh rates':'Технология ProMotion с адаптивной частотой обновления',
 'contrast ratio (typical)':'контрастность (типичная)',
 'Wide color (P3)':'Широкий цветовой охват (P3)',
 'with 2x2 MIMO':'с 2x2 MIMO',
 'Dual 16-core Neural Engine':'Двойной 16-ядерный Neural Engine',
 'Super Retina XDR display':'Дисплей Super Retina XDR',
 'all-screen OLED display':'полноэкранный OLED-дисплей','Always-On display':'Постоянно включённый дисплей','HDR display':'Дисплей HDR',
 'inch (diagonal)':'дюйма (диагональ)',
 'Rated IP68':'Степень защиты IP68','maximum depth of':'максимальная глубина','meters':'м',
 'under IEC standard':'по стандарту IEC','for mirroring, photos, and video out to':'для дублирования экрана, фото и вывода видео на',
 'AirPlay-enabled smart TV':'смарт-телевизор с AirPlay','2nd generation':'2-го поколения',
 'Silver':'Серебристый','Black':'Чёрный','White':'Белый',
 'Barometer':'Барометр','High dynamic range gyro':'Гироскоп с широким динамическим диапазоном',
 'High-g accelerometer':'Акселерометр высоких ускорений','Proximity sensor':'Датчик приближения','Dual ambient light sensors':'Двойные датчики освещённости',
 'LiDAR Scanner':'Сканер LiDAR','Digital compass':'Цифровой компас','Cellular':'Сотовая связь','iBeacon microlocation':'Микролокация iBeacon',
 'Precision dual-frequency GPS':'Высокоточный двухчастотный GPS',
 'Volume up/down':'Увеличение/уменьшение громкости','Action button':'Кнопка действия','Side button':'Боковая кнопка',
 'Built-in stereo speaker':'Встроенный стереодинамик','Built-in microphones':'Встроенные микрофоны','Built-in microphone':'Встроенный микрофон','USB-C connector':'Разъём USB-C',
 'Emergency SOS via satellite':'Экстренный вызов SOS через спутник','Crash Detection':'Обнаружение аварий',
 'Roadside Assistance via satellite':'Помощь на дороге через спутник','Messages via satellite':'Сообщения через спутник','Find My via satellite':'Локатор через спутник',
 'Camera controls: Exposure, Depth, Zoom, Cameras, Styles, Tone':'Управление камерой: экспозиция, глубина, масштаб, камеры, стили, тон',
 'with MagSafe Charger':'с зарядным устройством MagSafe',
 'MagSafe Charger':'зарядным устройством MagSafe',
 'with USB-C charging cable':'с кабелем USB-C',
 'and':'и','or':'или',
 'Video playback (streamed)':'Потоковое воспроизведение видео','Video playback':'Воспроизведение видео',
 'Audio playback':'Воспроизведение аудио','Fast-charge capable':'Поддержка быстрой зарядки',
 'FaceTime audio':'Аудиозвонки FaceTime','Voice over LTE':'Звонки через LTE','Wi-Fi calling':'Звонки по Wi-Fi',
 'Screen sharing':'Демонстрация экрана','Spatial Audio playback':'Воспроизведение пространственного аудио','Spatial Audio':'Пространственное аудио',
 'Voice Isolation':'Изоляция голоса','Wide Spectrum microphone modes':'Режим широкого спектра микрофона',
 'Internet access':'Доступ к интернету','required for some features':'требуется для некоторых функций',
 'Syncing to a Mac or PC requires':'Для синхронизации с Mac или ПК требуется',
 'free download from':'бесплатная загрузка с','using the Finder':'с использованием Finder','using iTunes':'с использованием iTunes',
 'or later':'или новее','through':'до','Supported formats include':'Поддерживаемые форматы',
 'User-configurable maximum volume limit':'Настраиваемое ограничение максимальной громкости',
 'when using':'при использовании','paired with':'совместно с','charging cable':'кабелем зарядки',
 'both available separately':'оба приобретаются отдельно','available separately':'приобретается отдельно',
 'with Adjustable Voltage Supply':'с поддержкой Adjustable Voltage Supply',
 'adapter or higher':'адаптером или более мощным','adapter':'адаптер',
 'charger':'зарядное устройство','charge in':'заряд за','around':'около','up to':'до','or higher':'или выше',
 'hours':'ч','hour':'ч','minutes':'мин','minute':'мин',
}

def localize(value):
    value=str(value or '').replace('\u2011','-').replace('\u2010','-')
    # Bind this relation before a longer accessory phrase consumes its "with".
    value=re.sub(r'\bpaired with\b','совместно с',value,flags=re.I)
    value=re.sub(r'\bwith (\d+(?:\.\d+)?)W adapter or higher\b',r'с адаптером мощностью не менее \1 Вт',value,flags=re.I)
    value=re.sub(r'\b(\d+(?:\.\d+)?)W-capable adapter or higher\b',r'адаптера мощностью не менее \1 Вт',value,flags=re.I)
    value=re.sub(r'\b(\d+)-core CPU with (\d+) super cores and (\d+) efficiency cores\b',r'\1-ядерный CPU: \2 суперъядра и \3 энергоэффективных ядра',value,flags=re.I)
    value=re.sub(r'\b(\d+)-core GPU with Neural Accelerators\b',r'\1-ядерный GPU с нейронными ускорителями',value,flags=re.I)
    value=re.sub(r'^([\w -]+) chip$',r'Чип \1',value)
    for source,target in sorted(PHRASES.items(),key=lambda pair:len(pair[0]),reverse=True):
        value=re.sub(r'(?<![A-Za-z])'+re.escape(source)+r'(?![A-Za-z])',target,value,flags=re.I)
    value=re.sub(r'(\d(?:[\d.,]*))\s*W\b',r'\1 Вт',value,flags=re.I)
    return value

def semantic_display(value,unit):
    prefixes={'up_to=':'До ','approx=':'Около ','at_least=':'Не менее '}
    prefix=''
    for key,label in prefixes.items():
        if value.startswith(key):prefix=label;value=value[len(key):];break
    if unit=='bool':return 'Да' if value=='true' else 'Нет' if value=='false' else 'Не указано'
    shown={'W':'Вт','min':'мин','%':'%','Gbit/s':'Гбит/с','nit':'нит'}.get(unit,unit)
    return prefix+localize(value)+(' '+shown if shown else '')

def content_classification(label,section,value):
    title=(str(label)+' '+str(section)).casefold()
    if re.search(r'system requirements|compatibility|системные требования|совместимость',title):return 'compatibility'
    if re.match(r'\s*(?:learn more|see (?:the )?user guide|download (?:the )?manual|contact support)\b',str(value),re.I):return 'support_prose'
    return 'product_attribute'
