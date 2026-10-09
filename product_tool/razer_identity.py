"""Literal official model codes; opaque retail suffixes, no numeric decoding."""
import re
from .adapters.common import clean_text
CODE=re.compile(r'\bRZ\d{2}-[A-Z0-9]+(?:-[A-Z0-9]+)?\b',re.I)
def components(article):
 code=clean_text(article).upper();bits=code.split('-')
 return {'requested':code,'family_prefix':bits[0] if CODE.fullmatch(code) else '', 'part_body':bits[1] if len(bits)>1 else '', 'regional_suffix':bits[2] if len(bits)>2 else '', 'full_part':len(bits)==3,'suffix_decoded':False}
def model_name(name):return clean_text(name.split(' [',1)[0])
def key(text):return re.sub(r'[^a-z0-9]','',text.casefold())
def requested_configuration(name):
 match=re.search(r'\[([^\]]+)\]',name);return dict(x.strip().split('=',1) for x in match[1].split(';') if '=' in x) if match else {}
def model_relation(article,name,title):
 codes=CODE.findall(title);label=re.split(r'\s*[|]\s*',title)[0];label=re.sub(r'\s+(?:Support.*|Drivers.*)$','',label,flags=re.I)
 wanted=model_name(name);same=key(label)==key(wanted)
 # Trailing x explicitly denotes a hardware family wildcard, never a retail SKU.
 matching=[x.upper() for x in codes if article.upper()==x.upper().rstrip('X') or (components(article)['full_part'] and article.upper().startswith(x.upper().rstrip('X'))) or (not components(article)['full_part'] and len(components(article)['part_body'])>=4 and same and x.upper().rstrip('X').startswith(article.upper()))]
 return {'model_confirmed':bool(same and matching),'model':label,'model_code':matching[0] if matching else '', 'requested':article,'model_relation':'model_confirmed' if same and matching else 'unproven','configuration_relation':'unproven','exact_sku':False,'reason':'Explicit official model name and printed RZ code' if same and matching else 'Name/code mismatch; neighboring model, generation or connectivity is insufficient','requested_configuration':requested_configuration(name),'components':components(article)}
def configuration_sensitive(label,category=''):
 text=label.casefold()
 return bool(re.search(r'color|colour|цвет|layout|расклад|region|регион|bundle|комплект|\bsku\b|part number|edition|редакц|processor|\bcpu\b|\bgpu\b|graphics|\bram\b|memory|storage|display|процессор|видеокарт|оператив|накопител|экран',text) or ('клавиат' in category.casefold() and re.search(r'switch|переключ',text)))
