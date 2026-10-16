"""Interpret supplier titles. Every result is input evidence, never official identity.

Closed family grammars retain model qualifiers; unknown/multiple model codes stay
candidates. The original title/article are never edited or replaced in storage.
"""
import re

VERSION='title_v1'
BRANDS=('Samsung','Lenovo','Apple','LG','JBL','Xiaomi','Redmi','POCO','Dreame','Razer','HyperX','Electrolux','PlayStation','Xbox','Bosch')
CATEGORY_RULES=(
 (r'стиральн\w*\s+машин\w*\s+с\s+сушк|стирально[-\s]сушильн', 'Стирально-сушильная машина'),
 (r'робот[-\s]*пылесос|robot\s+(?:vacuum|cleaner)', 'Робот-пылесос'),
 (r'паровой\s+шкаф|\bstyler\b', 'Паровой шкаф'),
 (r'стиральн\w*\s+машин|washing machine', 'Стиральная машина'),
 (r'сушильн\w*\s+машин|tumble dryer', 'Сушильная машина'),
 (r'wet\s+and\s+dry\s+vacuum|моющ\w*\s+пылесос', 'Моющий пылесос'),
 (r'вертикальн\w*\s+пылесос|cordless\s+(?:stick\s+)?vacuum', 'Вертикальный пылесос'),
 (r'пылесос|\bvacuum\b', 'Пылесос'),
 (r'сплит[-\s]систем|кондиционер|air conditioner', 'Сплит-система'),
 (r'микроволнов\w*\s+печ|\bmicrowave\b', 'Микроволновая печь'),
 (r'холодильник|refrigerator', 'Холодильник'),
 (r'саундбар|soundbar', 'Саундбар'),
 (r'наушник|гарнитур|headphones?|headset|earbuds', 'Наушники'),
 (r'клавиатур|keyboard', 'Клавиатура'),
 (r'микрофон|microphone', 'Микрофон'),
 (r'игров\w*\s+мыш|\bmouse\b', 'Мышь'),
 (r'монитор|\bmonitor\b', 'Монитор'),
 (r'телевизор|television|\bTV\b', 'Телевизор'),
 (r'ноутбук|laptop|macbook', 'Ноутбук'),
 (r'air purifier|очистител\w*\s+воздуха','Очиститель воздуха'),
 (r'electric scooter|электросамокат','Электросамокат'),
 (r'smart band|фитнес[-\s]браслет','Фитнес-браслет'),
 (r'смартфон|smartphone|\biphone\b', 'Смартфон'),
 (r'планшет|\bipad\b|tablet', 'Планшет'),
 (r'умные часы|smartwatch|apple watch', 'Умные часы'),
 (r'аудиосистем|акустическ\w*\s+систем|bluetooth speaker', 'Аудиосистема'),
 (r'музыкальн\w*\s+центр', 'Музыкальный центр'),(r'микросистем', 'Микросистема'),
 (r'духовой\s+шкаф|\boven\b','Духовой шкаф'),
 (r'посудомоеч|dishwasher','Посудомоечная машина'),
 (r'playstation|xbox','Игровая консоль'),
)
COLORS={
 'black':'Black','черный':'Black','чёрный':'Black','white':'White','белый':'White',
 'silver':'Silver','серебристый':'Silver','серебряный':'Silver','blue':'Blue','синий':'Blue',
 'red':'Red','красный':'Red','green':'Green','зелёный':'Green','зеленый':'Green',
 'pink':'Pink','розовый':'Pink','purple':'Purple','фиолетовый':'Purple','quartz':'Quartz',
 'gray':'Gray','grey':'Gray','серый':'Gray','gold':'Gold','золотой':'Gold',
 'midnight':'Midnight','starlight':'Starlight','graphite':'Graphite','графитовый':'Graphite',
}

def clean(value):return ' '.join(str(value or '').replace('\u2011','-').split())
def brand_in_name(name):return next((b for b in BRANDS if re.search(r'(?<!\w)'+re.escape(b)+r'(?!\w)',name,re.I)),'')
def category_in_name(name):return next((label for pattern,label in CATEGORY_RULES if re.search(pattern,name,re.I)),'')
def structured(value):return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/#()+-]{2,}',value) and re.search(r'\d',value))

def interpret(name,brand='',article='',*,category='',explicit_model='',configuration=None):
 name=clean(name);article=clean(article);provided=clean(brand);named=brand_in_name(name);brand=provided or named
 result=dict(version=VERSION,original_name=name,supplier_article=article,brand=brand,
             fields={},configuration={},model='',model_candidates=[],warnings=[])
 def field(key,value,source='product_name',confidence='high',raw='',candidates=None):
  record=dict(value=value,source=source,confidence=confidence,raw=raw or value)
  if candidates:record['candidates']=candidates
  result['fields'][key]=record
  return record
 field('brand',brand,'brand_column' if provided else 'product_name' if named else 'missing','high' if brand else 'missing')
 if provided and named and provided.casefold()!=named.casefold():result['warnings'].append('Бренд в названии отличается от отдельной колонки; используется колонка бренда')
 cat=clean(category) or category_in_name(name)
 family=brand.casefold();title=re.sub(r'\[[^\]]*\]',' ',name)
 if not cat:
  if family in {'xiaomi','redmi','poco'} and re.match(r'(?:(?:Xiaomi|Redmi|POCO)\s+)?(?:Note\s+)?(?:\d+\w*|[A-Z]\d+)(?:\s|$)',title,re.I):cat='Смартфон'
  elif family=='dreame':
   if re.search(r'\bH\d+',title,re.I):cat='Моющий пылесос'
   elif re.search(r'\b(?:X|L|D)\d+',title,re.I):cat='Робот-пылесос'
   elif re.search(r'\b(?:Z|R|V)\d+',title,re.I):cat='Вертикальный пылесос'
  elif family=='jbl' and re.search(r'\b(?:Tune|Live|Wave|Tour)\b',title,re.I):cat='Наушники'
  elif family=='hyperx' and re.search(r'\bAlloy\b',title,re.I):cat='Клавиатура'
  elif family=='hyperx' and re.search(r'\bCloud\b',title,re.I):cat='Наушники'
  if not cat:
   for pattern,label in {
    'apple':((r'\bAirPods\b','Наушники'),),
    'jbl':((r'\bBar\b','Саундбар'),(r'\b(?:Go|Flip|Charge|Boombox|Xtreme|PartyBox|Clip)\b','Аудиосистема'),(r'\b(?:Quantum|Reflect|Endurance|Vibe)\b','Наушники')),
    'hyperx':((r'\bPulsefire\b','Мышь'),(r'\bQuadCast\b','Микрофон'),(r'\bClutch\b','Геймпад')),
    'razer':((r'\b(?:Huntsman|BlackWidow)\b','Клавиатура'),(r'\b(?:Barracuda|BlackShark)\b','Наушники'),(r'\bBlade\b','Ноутбук'),(r'\b(?:DeathAdder|Basilisk)\b','Мышь')),
   }.get(family,()):
    if re.search(pattern,title,re.I):cat=label;break
 field('category',cat,'category_column' if category else 'product_name','high' if cat else 'missing')
 keyboard=cat=='Клавиатура' or bool(re.search(r'\b(?:Alloy|Huntsman|BlackWidow)\b',title,re.I))
 spans=[]
 def hint(key,value,raw,span=None,source='product_name',confidence='high'):
  if key in result['configuration'] and result['configuration'][key]['value']!=value:
   previous=result['configuration'][key];values=list(dict.fromkeys(previous.get('candidates',[previous['value']])+[value]))
   result['configuration'][key]=dict(value='',candidates=values,source=source,confidence='ambiguous',raw=previous['raw']+'; '+raw)
  else:result['configuration'][key]=dict(value=value,source=source,confidence=confidence,raw=raw)
  if span:spans.append(span)
 # Existing bracket configuration is accepted as input syntax too; no supplier
 # has to create it. It is generated internally for legacy adapter interfaces.
 for match in re.finditer(r'\[([^\]]+)\]',name):
  for pair in match[1].split(';'):
   if '=' in pair:
    k,v=pair.split('=',1);k={'RAM':'ram','memory':'ram'}.get(k.strip(),k.strip())
    hint(k,clean(v),pair)
 memory=re.search(r'(?<!\d)(\d{1,3})\s*(?:GB|ГБ)?\s*[/+]\s*(\d{2,4})\s*(GB|ГБ|TB|ТБ)\b',title,re.I)
 if memory:
  hint('ram',memory[1]+'GB',memory[0],memory.span());hint('storage',memory[2]+('TB' if memory[3].upper() in {'TB','ТБ'} else 'GB'),memory[0])
 used_memory_labels=set()
 for match in re.finditer(r'(?<!\d)(\d+(?:[.,]\d+)?)\s*(GB|ГБ|TB|ТБ)\b',title,re.I):
  if memory and memory.start()<=match.start()<memory.end():continue
  before=title[:match.start()];after=title[match.end():]
  ram_label=r'(?:RAM|ОЗУ|DDR[345]|оперативн\w*(?:\s+памят\w*)?)'
  storage_label=r'(?:SSD|HDD|ROM|storage|накопител\w*|встроенн\w*\s+памят\w*)'
  labels=r'(?:(?P<ram>'+ram_label+r')|(?P<storage>'+storage_label+r'))'
  pre=re.search(r'\b'+labels+r'\s*[:=]?\s*$',before,re.I)
  post=re.match(r'\s*'+labels+r'\b',after,re.I)
  selected=None;offset=0
  if pre and pre.span(pre.lastgroup) not in used_memory_labels:selected=pre
  elif post:selected=post;offset=match.end()
  # A label belongs to one capacity. In "16GB RAM 512GB SSD", the RAM
  # token is consumed by 16GB, whereas "RAM 16GB SSD 512GB" uses prefixes.
  if selected:
   start,end=selected.span(selected.lastgroup);used_memory_labels.add((start+offset,end+offset))
  ram=bool(selected and selected.lastgroup=='ram')
  hint('ram' if ram else 'storage',match[1].replace(',','.')+('TB' if match[2].upper() in {'TB','ТБ'} else 'GB'),match[0],match.span())
 for match in re.finditer(r'(?<!\w)(\d+(?:[.,]\d+)?)\s*(mm|мм|inch|дюйм\w*|["″])(?!\w)',title,re.I):
  hint('size' if match[2].casefold() in {'mm','мм'} else 'screen_size',match[1].replace(',','.')+('mm' if match[2].casefold() in {'mm','мм'} else 'inch'),match[0],match.span())
 for match in re.finditer(r'(?<!\w)('+ '|'.join(map(re.escape,COLORS))+r')(?!\w)',title,re.I):
  if keyboard and match[1].casefold() in {'red','blue','green'}:
   hint('switch',match[1].title(),match[0],match.span(),confidence='medium');continue
  hint('color',COLORS[match[1].casefold()],match[0],match.span())
 for key,pattern in (
  ('layout',r'\b(?:RU|US|UK|ANSI|ISO|QWERTY|AZERTY)\b' if keyboard else r'(?!)'),
  ('region',r'\b(?:Global|EEA|EU|CN|JP)\b|(?:регион|region)\s*[:=-]?\s*(?:RU|US|UK)\b' if keyboard else r'\b(?:Global|EEA|EU|CN|JP|RU|US|UK)\b'),
  ('switch_type',r'\b(?:Linear|Clicky|Tactile|Optical)\b' if keyboard else r'(?!)'),
  ('connectivity',r'\b(?:wireless|wired|Bluetooth)\b|беспроводн\w*|проводн\w*'),
  ('edition',r'\b(?:Disc|Digital)(?:\s+Edition)?\b'),
  ('generation',r'\b(?:20[12]\d|Gen\s*\d+|\d+(?:st|nd|rd|th)\s+generation)\b'),
  ('bundle',r'\b(?:Complete|Bundle|Kit)\b|(?:комплект|набор)\b[^,;]*'),
  ('station',r'\b(?:with|с)\s+[^,;]*?(?:station|станци\w*)\b'),
 ):
  for match in re.finditer(pattern,title,re.I):
   hint(key,match[0],match[0],None if key=='generation' else match.span())
 # Preserve generation in the model: e.g. a 2022 headset is not its 2021 version.
 remainder=title
 for start,end in sorted(set(spans),reverse=True):remainder=remainder[:start]+' '* (end-start)+remainder[end:]
 remainder=clean(remainder).strip(' ,;()')
 remainder=re.sub(r'(?<!\w)(?:'+ '|'.join(map(re.escape,BRANDS))+r')(?!\w)',' ',remainder,flags=re.I)
 remainder=clean(remainder)
 model='';confidence='high';source='product_name'
 patterns={
  'apple':r'\b(?:iPhone\s*\d{1,2}[e]?(?:\s+(?:Pro\s+Max|Pro|Plus|Air))?|MacBook\s+(?:Air|Pro)(?:\s+\d{2})?(?:\s+M\d+(?:\s+(?:Pro|Max|Ultra))?)?|iPad\s*(?:Pro|Air|mini)?(?:\s+\d+(?:\.\d+)?)?(?:\s+M\d+)?|AirPods(?:\s+(?:Pro|Max))?(?:\s+\d+)?|Watch\s+(?:Series\s+\d+|Ultra(?:\s+\d+)?|SE(?:\s+\d+)?))\b',
  'xiaomi':r'\b(?:Xiaomi\s+)?(?:Redmi\s+|POCO\s+)?(?:Note\s+)?\d+\w*(?:\s+(?:Pro\+|Pro|Ultra|Plus|Lite|5G|4G|T))*\b',
  'redmi':r'\b(?:Note\s+)?\d+\w*(?:\s+(?:Pro\+|Pro|Plus|5G|4G))*\b',
  'poco':r'\b[A-Z]\d+(?:\s+(?:Pro|Ultra|5G))*\b',
  'dreame':r'\b(?:[A-Z]\d+[A-Z]?|Bot\s+[A-Z]\d+)(?:\s+(?:Pro|Ultra|Master|Plus|Heat|Mix))*\b',
  'jbl':r'\b(?:Tune|Live|Tour|Wave|Vibe|Quantum|Reflect|Endurance|Go|Flip|Charge|Boombox|Xtreme|PartyBox|Bar|Clip)\s*\d*[A-Za-z]*(?:\s+(?:\d+(?:\.\d+)?|TWS|NC|ANC|BT|Pro|Plus|Essential|Encore|Ultimate|Beam|Buds|Flex))*\b',
  'hyperx':r'\b(?:Alloy\s+(?:Origins|Rise|Core)(?:\s+(?:65|60|TKL|2|Mini))?|Cloud(?:\s+(?:Alpha|Stinger|Flight|III|II|Core|Mix|Wireless|2|3))*|Pulsefire\s+\w+(?:\s+\d+)?|QuadCast(?:\s+\d+)?|Clutch(?:\s+\w+)?)\b',
  'razer':r'\b(?:Huntsman\s+(?:Mini|V\d|TE)|Barracuda\s+X|BlackShark\s+V\d(?:\s+Pro)?|Blade\s+\d+|DeathAdder\s+V\d(?:\s+Pro)?|Basilisk\s+V\d(?:\s+Pro)?)(?:\s+20[12]\d)?\b',
  'playstation':r'\b(?:PlayStation\s*5|PS5)(?:\s+(?:Slim|Pro))?\b',
  'xbox':r'\b(?:Xbox\s+)?Series\s+[XS]\b',
 }
 # Brand tokens removed above are retained where part of an official marketing
 # model (Redmi/POCO/Xiaomi/PlayStation/Xbox), never required from the supplier.
 probe=remainder
 if family=='playstation':probe=remainder if re.search(r'\bPS5\b',remainder,re.I) else 'PlayStation '+remainder
 if family in {'xiaomi','redmi','poco'}:
  lineage=next((b for b in ('Redmi','POCO','Xiaomi') if re.search(r'\b'+b+r'\b',title,re.I)),brand)
  probe=re.sub(r'\b(?:Xiaomi|Redmi|POCO)\b',' ',remainder,flags=re.I)
 else:lineage=''
 if family in patterns:
  matches=[]
  if family in {'xiaomi','redmi','poco'}:
   matches=list(re.finditer(r'\b(?:Robot Vacuum|Vacuum Cleaner|Smart Band|Smart Air Purifier|Air Purifier|Electric Scooter|TV)\s+[A-Z0-9+]+(?:\s+(?:Max|Lite|Pro|Ultra|Plus|20\d\d))*\b',probe,re.I))
  if not matches:
   matches=list(re.finditer(patterns[family],probe,re.I))
   if family in {'xiaomi','redmi','poco'} and len(matches)>1:matches=[m for m in matches if not re.fullmatch(r'20[12]\d',m[0])]
  candidates=list(dict.fromkeys(clean(m[0]) for m in matches))
  if family in {'xiaomi','redmi','poco'}:candidates=[lineage+' '+c for c in candidates]
  if family=='apple':candidates=[re.sub(r'^Watch\b','Apple Watch',c) for c in candidates]
  if family=='xbox':candidates=['Xbox '+c if not c.lower().startswith('xbox') else c for c in candidates]
  if family in {'hyperx','razer'}:
   year=re.search(r'\b20[12]\d\b',title)
   if year:candidates=[c+' '+year[0] if year[0] not in c else c for c in candidates]
 else:
  codes=[m[0] for m in re.finditer(r'(?<![\w])(?=[A-Za-z0-9.-]*[A-Za-z])(?=[A-Za-z0-9.-]*\d)[A-Za-z0-9][A-Za-z0-9.-]{2,}(?![\w])',remainder)]
  # Resolutions/dimensions and labeled technical quantities are not model codes.
  non_model=r'(?:\d+(?:[xх×]\d+)+|(?:LP)?DDR\d[A-Z0-9]*|(?:USB|HDMI|WIFI)[\d.-]+|\d+(?:[.,]\d+)?(?:HZ|W|KG|CM|MM|MBPS|MAH|BTU))'
  candidates=list(dict.fromkeys(code for code in codes if not re.fullmatch(non_model,code,re.I)))
  # LG sales suffix belongs to retail identity, not the base marketing model.
  if family=='lg':candidates=list(dict.fromkeys(c.split('.')[0] for c in candidates))
 if clean(explicit_model) and not re.search(r'[А-Яа-яЁё]',explicit_model):
  explicit=interpret(explicit_model,brand,'')
  if explicit['model']:
   if candidates and explicit['model'] not in candidates:result['warnings'].append('Модель из отдельной колонки отличается от названия; используется колонка модели')
   candidates=[explicit['model']];source='model_column'
 result['model_candidates']=candidates
 if len(candidates)==1:model=candidates[0]
 elif len(candidates)>1:confidence='ambiguous';result['warnings'].append('Несколько кандидатов модели; варианты будут проверены отдельно')
 else:confidence='missing';result['warnings'].append('Модель не извлечена однозначно; используются артикул и исходное название как fallback')
 for k,v in (configuration or {}).items():
  if v:result['configuration'][k]=dict(value=clean(v),source='configuration_column',confidence='high',raw=clean(v))
 result.update(model=model,category=cat)
 field('model',model,source,confidence,candidates=candidates if len(candidates)>1 else None)
 field('supplier_article',article,'article_column','high' if article else 'missing')
 result['configuration_hints']={k:v['value'] for k,v in result['configuration'].items() if v['value']}
 queries=[]
 for purpose,values in (('model',candidates),('article',[article] if structured(article) else []),('normalized_model',[re.sub(r'\s+','',m) for m in candidates]),('original_name',[name])):
  for value in values:
   if value and value not in [q['query'] for q in queries]:queries.append(dict(query=value,purpose=purpose,source='product_name' if purpose!='article' else 'article_column'))
 result['search_queries']=queries
 return result

def adapter_name(parsed):
 """Compatibility encoding for existing adapters; never written to original name."""
 model=parsed.get('model') or next(iter(parsed.get('model_candidates',[])),'')
 if not model:return parsed['original_name']
 opts=parsed['configuration_hints'];pairs=[]
 for key,value in opts.items():
  if any(c in str(value) for c in ';=[]'):continue
  pairs.append(('RAM' if key=='ram' else key)+'='+str(value))
 return model+(' ['+';'.join(pairs)+']' if pairs else '')

def attach_input_evidence(evidence,product):
 """A found source confirms a candidate, not an ambiguous supplier row."""
 parsed=product.get('input_interpretation')
 if parsed:
  evidence['input_interpretation']=parsed
  evidence['input_model_ambiguous']=parsed['fields']['model']['confidence']=='ambiguous'
