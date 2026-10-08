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
 doc=SourceDocument('apple_model','Apple Tech Specs',url,found_model=found)
 audit={'url':url,'model_key':key,'raw_specs':[],'candidates':[],'admitted':[]}
 if not official(url) or 'tech specs' not in plain(found) or identify(found)!=key:
  doc.error='Tech Specs model/generation mismatch';return doc,audit
 doc.match_level='model_confirmed';doc.evidence='Exact model/generation; configuration options excluded and size/connectivity scopes checked'
 def add(name,value,sec,scope='model-stable'):
  doc.attributes.append(RawAttribute(name,value,section=sec,value_cell=True));audit['admitted'].append({'name':name,'value':value,'scope':scope,'section':sec})
 def candidate(sec,value,reason):audit['candidates'].append(dict(section=sec,raw_label=sec,value=value,reason=reason))
 for sec,values,node in groups:
  for value in values:audit['raw_specs'].append(dict(section=sec,raw_label=sec,value=value))
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
      add(label,str(val),sec,'configuration-sensitive' if cat in {'watch','ipad'} else 'model-stable')
    elif cat=='watch' and 'pixels' in t:add('Разрешение экрана',v,sec,'configuration-sensitive')
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
    else:candidate(sec,v,'chip metadata')
   continue
  labels={'Display':'Технологии экрана','Camera':'Основная камера','TrueDepth Camera':'Фронтальная камера','Front Camera':'Фронтальная камера','Sensors':'Датчики','Charging and Expansion':'Разъёмы и зарядка','MagSafe':'MagSafe','MagSafe and Wireless Charging':'MagSafe и беспроводная зарядка','Audio Technology':'Аудиотехнологии','Face ID':'Face ID','Touch ID':'Touch ID','Dust, Sweat, and Water Resistant':'Защита от пыли и воды','Splash, Water, and Dust Resistant':'Защита от пыли и воды','Water and Dust Resistance':'Защита от пыли и воды'}
  if sec in {'Wireless','Cellular and Wireless','Connectivity'}:
   for v in values:
    if re.search(r'wi.fi\s*\d',plain(v)):add('Wi-Fi',v,sec)
    elif re.search(r'^bluetooth\s*\d',plain(v)):add('Bluetooth',v,sec)
    else:candidate(sec,v,'regional/connectivity feature requires explicit scope')
  elif sec in labels:
   admitted=[]
   for v in values:
    if re.search(r'optional|configurable|depending|aluminum|titanium|sold separately',plain(v)):candidate(sec,v,'variant/accessory conditional statement')
    else:admitted.append(v)
   if admitted:add(labels[sec],'; '.join(admitted),sec)
  else:
   for v in values:candidate(sec,v,'feature not yet canonically mapped')
 return doc,audit
