"""Apple's two evidence levels. Registry entries identify models, never order SKUs."""
import re
from bs4 import BeautifulSoup
from .adapters.common import SourceDocument, RawAttribute, clean_text

MODELS = {
 'iphone16': ('iPhone 16', '121029', 'iphone', 'iphone'),
 'iphone15pro': ('iPhone 15 Pro', '111829', 'iphone', 'iphone'),
 'ipada16': ('iPad (A16)', '122240', 'ipad', 'ipad'),
 'air13m4': ('MacBook Air (13-inch, M4, 2025)', '122209', 'mac', 'macbook-air'),
 'pro14m4': ('MacBook Pro (14-inch, M4, 2024)', '121552', 'mac', 'macbook-pro'),
 'watch10': ('Apple Watch Series 10', '121202', 'watch', 'watch'),
 'airpods4anc': ('AirPods 4 with Active Noise Cancellation', '121204', 'airpods', 'airpods'),
}

def plain(s):
 return clean_text(s).replace('\u2011','-').replace('\u2010','-').replace('\u2013','-').replace('\u2014','-').casefold()

def identify(title):
 t=plain(title)
 if re.search(r'iphone 16(?!\s*(?:pro|plus|e)\b)\b',t):return 'iphone16'
 if re.search(r'iphone 15 pro(?!\s*max)\b',t):return 'iphone15pro'
 if 'ipad' in t and 'a16' in t:return 'ipada16'
 if 'macbook air' in t and '13-inch' in t and 'm4' in t:return 'air13m4'
 if 'macbook pro' in t and '14-inch' in t and re.search(r'\bm4\b(?!\s*(?:pro|max))',t):return 'pro14m4'
 if 'watch' in t and 'series 10' in t:return 'watch10'
 if 'airpods 4' in t and ('noise cancellation' in t or ' anc' in t):return 'airpods4anc'
 return ''

def classification(name,category):
 """Scope of an admitted canonical field; conditional values still require routing."""
 n=plain(name)
 sensitive=('storage','memory','color','region','condition','size','cellular','accessories','gpu') if category=='mac' else ('storage','memory','color','region','condition','size','cellular','accessories')
 return 'configuration-sensitive' if n in sensitive or (category=='watch' and n in {'dimensions','weight','display_resolution'}) or (category=='ipad' and n=='weight') else 'model-stable'

def sections(html):
 b=BeautifulSoup(html,'html.parser');out=[]
 for h in b.select('h3.gb-header'):
  sec=clean_text(h.get_text(' ',strip=True));sec=re.sub(r'\s*\d+$','',sec)
  values=[]
  for p in h.parent.select('p.gb-paragraph'):
   p=BeautifulSoup(str(p),'html.parser');[x.decompose() for x in p.select('sup')]
   text=clean_text(p.get_text(' ',strip=True))
   if text and not text.startswith('Learn more'):values.append(text)
  out.append((sec,values,h.parent))
 return b,out

def parse_model(html,url,key,configuration):
 from .adapters.apple import official
 title,_,cat,_=MODELS[key];b,groups=sections(html)
 found=clean_text(b.h1.get_text(' ',strip=True)) if b.h1 else ''
 doc=SourceDocument('apple_model','Apple Tech Specs',url,found_model=found,html=html)
 audit={'url':url,'model_key':key,'raw_specs':[],'candidates':[],'admitted':[]}
 if not official(url) or 'tech specs' not in plain(found) or identify(found)!=key:
  doc.error='Tech Specs model/generation mismatch';return doc,audit
 doc.match_level='model_confirmed';doc.evidence='Exact model/generation; configuration options excluded and size/connectivity scopes checked'
 return append_qualified_sections(doc,audit,groups,cat,configuration)

def append_qualified_sections(doc,audit,groups,cat,configuration):
 """Shared section semantics after caller has proven its own source identity."""
 def add(name,value,sec,scope='model-stable',origin=None):
  from .attribute_lineage import text_key
  origins=[origin] if origin is not None else [v for v in values if text_key(v) in text_key(value)]
  doc.attributes.append(RawAttribute(name,value,section=sec,value_cell=True));audit['admitted'].append({'name':name,'value':value,'scope':scope,'section':sec,'raw_rows':[dict(section=source_sec,raw_label=source_sec,raw_value=v) for v in origins]})
 def candidate(sec,value,reason):audit['candidates'].append(dict(section=source_sec,raw_label=source_sec,value=value,reason=reason))
 for source_sec,values,node in groups:
  sec=source_sec.replace('\u2011','-').replace('\u2010','-')
  sec={'External Buttons and Connectors':'Buttons and Connectors','Hardware and Buttons':'Buttons and Connectors','Environmental Requirements':'Operating Requirements','Mobile and Wireless':'Cellular and Wireless','Intelligent Assistant':'Siri','Splash, Water and Dust Resistant':'Splash, Water, and Dust Resistant'}.get(sec,sec)
  for value in values:audit['raw_specs'].append(dict(section=source_sec,raw_label=source_sec,value=value))
  if sec in {'Finish','Capacity','Memory','Storage','In the Box','Configure to Order'}:
   for v in values:candidate(sec,v,'configuration-sensitive family option')
   continue
  if sec=='Size and Weight':
   if cat=='airpods':
    for v in values:candidate(sec,v,'Earbud/case component dimensions require separate routing')
    continue
   active='';material=plain(configuration.get('material',''));connectivity=configuration.get('connectivity','');size=configuration.get('case_size','')
   for v in values:
    t=plain(v)
    if cat=='watch' and re.fullmatch(r'\d+mm',t):active=t;continue
    if cat=='ipad' and t in {'wi-fi models','wi-fi + cellular models'}:active=t;continue
    if cat=='watch' and (not size or active!=size+'mm'):candidate(sec,v,'other/unresolved case size');continue
    if cat=='ipad' and active and ((active=='wi-fi models' and connectivity!='Wi-Fi') or (active=='wi-fi + cellular models' and connectivity!='Wi-Fi + Cellular')):candidate(sec,v,'other/unresolved connectivity');continue
    if cat=='watch' and t.startswith('weight'):
     allowed=('aluminum, gps)' in t and material=='aluminum' and connectivity=='GPS') or ('aluminum, gps + cellular)' in t and material=='aluminum' and connectivity=='GPS + Cellular') or ('titanium)' in t and material=='titanium')
     if not allowed:candidate(sec,v,'other/unresolved material or connectivity');continue
    m=re.search(r'(height|width|depth|weight).*?:\s*(.*)',t)
    if m:
     metric=re.search(r'([\d.]+)\s*(mm|cm|grams|kg)',m[2])
     if metric:
      n=float(metric[1]);unit=metric[2];val=n*10 if unit=='cm' else n/1000 if unit=='grams' else n
      label={'height':'Высота товара, мм','width':'Ширина товара, мм','depth':'Глубина товара, мм','weight':'Вес товара, кг'}[m[1]]
      add(label,str(val),sec,'configuration-sensitive' if cat in {'watch','ipad'} else 'model-stable',origin=v)
    elif cat=='watch' and 'pixels' in t:add('Разрешение экрана',v,sec,'configuration-sensitive')
    elif cat=='watch' and re.search(r'\d+\s+sq\s+mm\s+display area',t):add('Площадь экрана, мм²',v,sec,'configuration-sensitive')
    elif cat=='watch' and re.match(r'fits\s+\d',t):add('Обхват запястья, мм',v,sec,'configuration-sensitive')
   continue
  if sec in {'Power and Battery','Battery and Power','Power and Battery Life','Battery'}:
   battery_context=''
   for v in values:
    t=plain(v);labels=[]
    if cat=='airpods' and 'airpods' in t:battery_context='с кейсом' if 'case' in t else 'один заряд'
    if 'cellular' in t and configuration.get('connectivity')!='Wi-Fi + Cellular':candidate(sec,v,'Cellular runtime not applicable to Wi-Fi configuration');continue
    if 'hours' in t:
     if 'minutes for' in t:labels=['Быстрая зарядка: '+('мониторинг сна' if 'sleep' in t else 'обычный режим')]
     elif 'low power' in t:labels=['Время работы в режиме энергосбережения']
     elif cat=='watch' and 'normal use' in t:labels=['Время работы в обычном режиме']
     elif 'stream' in t:labels=['Время потокового воспроизведения видео']
     else:
      if 'video' in t:labels.append('Время воспроизведения видео')
      if 'web' in t:labels.append('Время работы через мобильную сеть' if 'cellular' in t else 'Время работы в интернете по Wi-Fi' if cat=='ipad' else 'Время беспроводной работы в интернете')
      if 'audio' in t:labels.append('Время воспроизведения аудио')
      if cat=='airpods' and 'listening' in t:labels=['Воспроизведение аудио: '+battery_context+(' с ANC' if 'enabled' in t else ' без ANC')]
    elif 'watt-hour' in t:labels=['Энергия аккумулятора, Вт·ч']
    elif 'charge' in t and 'minutes' in t:labels=['Быстрая зарядка до '+(re.search(r'\d+%',t)[0] if re.search(r'\d+%',t) else 'указанного уровня')]
    elif 'fast-charge capable' in t:labels=['Поддержка быстрой зарядки']
    if labels:
     for label in labels:add(label,v,sec)
    else:candidate(sec,v,'power/accessory metadata')
   continue
  if sec=='Chip':
   for v in values:
    t=plain(v)
    if 'configurable' in t or re.search(r'\d+-core gpu.*\d+-core gpu',t) or (cat=='mac' and 'gpu' in t):candidate(sec,v,'GPU configuration requires exact order override');continue
    if re.search(r'(?:a\d+|m\d+|h\d+|s\d+)\s*(?:chip|sip)|apple\s*m\d+\s*chip',t):add('Процессор',v,sec)
    elif 'cpu' in t:add('Ядра CPU',v,sec)
    elif 'gpu' in t:add('Ядра GPU',v,sec)
    elif 'neural' in t:add('Neural Engine',v,sec)
    elif 'ray tracing' in t:add('Трассировка лучей',v,sec)
    elif 'memory bandwidth' in t:add('Пропускная способность памяти процессора',v,sec)
    elif t=='media engine':add('Медиадвижок',v,sec)
    elif 'hardware-accelerated' in t:add('Аппаратные видеокодеки',v,sec)
    elif 'prores' in t and ('encode' in t or 'decode' in t):add('Обработка ProRes',v,sec)
    elif 'av1 decode' in t:add('Декодирование AV1',v,sec)
    elif 'video decode engine' in t:add('Модуль декодирования видео',v,sec)
    elif 'video encode engine' in t:add('Модуль кодирования видео',v,sec)
    else:candidate(sec,v,'chip metadata')
   continue
  if sec=='Display':
   optional=False;technologies=[]
   for v in values:
    t=plain(v)
    if 'configurable' in t:optional=True
    if optional or re.search(r'optional|sold separately|depending',t):candidate(sec,v,'Display configuration option; continuation scope retained');continue
    if t in {'color','refresh rates','xdr (extreme dynamic range)'}:candidate(sec,v,'Section/subsection heading, not a separate value');continue
    if t.endswith('display') or t in {'wide-angle oled','led backlit multi-touch display with ips technology'}:technologies.append(v);continue
    diagonal=re.search(r'(\d+(?:\.\d+)?)[ -]*inch',t)
    resolution=re.search(r'(\d+)\s*-?by-?\s*(\d+)[ -]+(?:native |pixel )?resolution',t)
    density=re.search(r'(\d+)\s+(?:pixels per inch|ppi)\b',t)
    if diagonal:add('Диагональ экрана, дюймы',diagonal[1],sec,origin=v)
    if resolution:add('Разрешение экрана',resolution[1]+' x '+resolution[2]+' пикселей',sec,origin=v)
    if density:add('Плотность пикселей, ppi',density[1],sec,origin=v)
    if diagonal or resolution or density:continue
    if 'contrast ratio' in t:add('Контрастность',v,sec)
    elif 'brightness' in t:
     mode='XDR' if 'xdr brightness' in t else 'SDR' if 'sdr brightness' in t else 'экрана'
     limit=' (минимальная)' if re.search(r'\bminimum\b',t) else ' (максимальная)' if re.search(r'\bmaximum\b|\bmaximun\b|\bup to\b',t) else ''
     add('Яркость '+mode+limit,v,sec)
    elif 'colors' in t:add('Количество отображаемых цветов',v,sec)
    elif re.search(r'wide colou?r',t):add('Цветовой охват',v,sec)
    elif 'true tone' in t:add('True Tone',v,sec)
    elif 'promotion' in t:add('Адаптивная частота ProMotion (заявленная)',v,sec)
    elif 'fixed refresh rates' in t:add('Поддерживаемые фиксированные частоты обновления',v,sec)
    elif t in {'dynamic island','haptic touch','fingerprint-resistant oleophobic coating','antireflective coating','fully laminated display','apple pencil hover'}:
     label={'dynamic island':'Dynamic Island','haptic touch':'Haptic Touch','fingerprint-resistant oleophobic coating':'Олеофобное покрытие','antireflective coating':'Антибликовое покрытие','fully laminated display':'Полная ламинация дисплея','apple pencil hover':'Apple Pencil hover'}[t]
     add(label,v,sec)
    elif t.startswith('supports apple pencil'):add('Поддержка Apple Pencil',v,sec)
    elif t.startswith('support for display of multiple languages'):add('Одновременное отображение нескольких языков',v,sec)
    elif re.search(r'pair and charge',t):candidate(sec,v,'Support/setup instructions, not a standalone display specification')
    elif re.search(r'aluminum cases|titanium cases',t):candidate(sec,v,'Glass material depends on exact case material configuration')
    elif re.search(r'brighter when viewed at an angle',t):candidate(sec,v,'Promotional relative brightness without a stable measured mode')
    else:candidate(sec,v,'Display field not yet canonically mapped')
   if technologies:add('Технология экрана','; '.join(technologies),sec)
   continue
  if sec=='Acoustic Performance':
   # Noise table explicitly reports a tested configuration, not every order.
   for v in values:candidate(sec,v,'Configuration-specific acoustic test table; exact tested CPU/GPU/RAM/SSD relation not qualified')
   continue
  if sec=='Durability':
   for v in values:
    if re.search(r'water resistance|dust resistance',plain(v)):add('Водостойкость' if 'water' in plain(v) else 'Защита от пыли',v,'Защита от воды и пыли')
    else:candidate(sec,v,'Durability prose without an explicit technical protection claim')
   continue
  if sec=='Charging Case':
   for v in values:
    if plain(v).startswith('works with'):add('Зарядка кейса',v,'Кейс')
    elif 'speaker' in plain(v):add('Динамик кейса для Find My',v,'Кейс')
    else:candidate(sec,v,'Case component statement without a stable field meaning')
   continue
  if sec.endswith(' and the Environment'):
   safe=[]
   for v in values:
    t=plain(v)
    if re.match(r'see\b|learn more\b',t):candidate(sec,v,'support/help reference; no independent product attribute')
    elif re.search(r'designed to|commitment|progress toward|business-as-usual|carbon neutral|environmental impact|zero waste program|manufacturing electricity|assembly sites',t):candidate(sec,v,'marketing/company process, not a device technical field')
    elif not re.search(r'\d|free\b|exceeds|energy star|epeat',t):candidate(sec,v,'subsection heading; preserved in raw evidence')
    else:safe.append(v)
   if safe:add('Материалы и экологические характеристики','; '.join(safe),'Материалы и экологические характеристики')
   continue
  if sec in {'Material and Finish','SIM Card','Apple Pay'}:
   for v in values:candidate(sec,v,'Color/material/SIM/payment regional or configuration relation not established')
   continue
  if sec=='Display Support, Video Support and Camera':
   active='';safe=[]
   for v in values:
    if 'Thunderbolt 5' in v:active='other'
    if 'Thunderbolt 4' in v or 'HDMI digital' in v:active='model'
    if active=='other':candidate(sec,v,'Transport-specific subsection not qualified for exact model')
    else:safe.append(v)
   if safe:add('Подключение внешних дисплеев и видеокамера','; '.join(safe),'Подключение дисплеев')
   continue
  labels={'Camera':'Основная камера','TrueDepth Camera':'Фронтальная камера','Front Camera':'Фронтальная камера','Sensors':'Датчики','Charging and Expansion':'Разъёмы и зарядка','MagSafe':'MagSafe','MagSafe and Wireless Charging':'MagSafe и беспроводная зарядка','Audio Technology':'Аудиотехнологии','Face ID':'Face ID','Touch ID':'Touch ID','Dust, Sweat, and Water Resistant':'Защита от пыли и воды','Splash, Water, and Dust Resistant':'Защита от пыли и воды','Water and Dust Resistance':'Защита от пыли и воды'}
  if sec in {'Wireless','Cellular and Wireless','Connectivity'}:
   radio_model=''
   for v in values:
    if re.match(r'^model\s+a\d+',plain(v)):radio_model=v
    # Existing model-level Wi-Fi/Bluetooth policy is retained. A radio band
    # subsection does not demonstrate a regional difference in these fields.
    if re.search(r'wi.fi\s*\d',plain(v)):add('Wi-Fi',v,sec);continue
    if re.search(r'^bluetooth\s*\d',plain(v)):add('Bluetooth',v,sec);continue
    if radio_model:
     candidate(sec,v,'Explicit radio hardware model subsection; requested hardware/region relation not established');continue
    if re.search(r'wi.fi\s*\d',plain(v)):add('Wi-Fi',v,sec)
    elif re.search(r'^bluetooth\s*\d',plain(v)):add('Bluetooth',v,sec)
    elif plain(v)=='simultaneous dual band':add('Двухдиапазонный Wi-Fi',v,sec)
    else:candidate(sec,v,'regional/connectivity feature requires explicit scope')
  elif sec in labels:
   admitted=[]
   for v in values:
    if re.search(r'optional|configurable|depending|aluminum|titanium|sold separately',plain(v)):candidate(sec,v,'variant/accessory conditional statement')
    else:admitted.append(v)
   if admitted:add(labels[sec],'; '.join(admitted),sec)
  else:
   useful={'Video Playback':'Воспроизведение видео','Audio Playback':'Воспроизведение аудио','Keyboard and Trackpad':'Клавиатура и тачпад','Audio':'Аудиосистема','Operating Requirements':'Условия эксплуатации','Operating System':'Операционная система','Accessibility':'Специальные возможности','Built-in Apps':'Встроенные приложения','Apple Intelligence':'Apple Intelligence','Siri':'Siri','Controls':'Элементы управления','Buttons and Connectors':'Кнопки и разъёмы','Video Recording':'Видеосъёмка','Video Calling':'Видеозвонки','Audio Calling':'Аудиозвонки','TV and Video':'Вывод видео','Location':'Определение местоположения','Health and Wellness':'Функции здоровья','Features':'Особенности модели','Safety':'Функции безопасности','Peace of Mind':'Функции безопасности','Workouts and Activity':'Тренировки и активность','Languages':'Поддерживаемые языки и средства ввода','System Requirements':'Системные требования','Compatibility':'Совместимость','Mail Attachment Support':'Форматы вложений почты','Rating for Hearing Aids':'Совместимость со слуховыми аппаратами','Audio/Video Calling':'Аудио- и видеозвонки','Live Translation':'Live Translation'}
   useful.update({'Speakers':'Динамики','Microphones':'Микрофон'})
   if sec in useful:
    admitted=[]
    for v in values:
     if re.search(r'user guide|learn more|most advanced|most powerful|strongest privacy|designed to|features include:|accessibility features help|optional|sold separately|depending|regional|not available in all|u\.s\. only|national parks|\bcellular connectivity\b',plain(v)):
      candidate(sec,v,'Support/marketing or conditional statement; retained raw')
     elif sec=='Keyboard and Trackpad' and ('U.S.' in v or 'ISO' in v):candidate(sec,v,'Explicit layout variation; exact layout relation not qualified')
     else:admitted.append(v)
    if admitted:add(useful[sec],'; '.join(admitted),sec)
   elif sec=='Display Support':
    active='';safe=[]
    for v in values:
     if 'Thunderbolt 5' in v:active='other';candidate(sec,v,'Transport-specific subsection not present in exact M4 port specs');continue
     if 'HDMI digital' in v or 'Thunderbolt 4 digital' in v:active='model'
     if active=='other':candidate(sec,v,'Transport-specific subsection not qualified for exact model');continue
     safe.append(v)
    if safe:add('Подключение внешних дисплеев','; '.join(safe),sec)
   else:
    for v in values:candidate(sec,v,'feature not yet canonically mapped')
 return doc,audit
