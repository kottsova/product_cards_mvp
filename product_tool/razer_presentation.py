"""Razer-only presentation; source labels remain in its raw evidence."""
import re
from .razer_page import LABELS
CONFIG_LABELS={'color':'Цвет','layout':'Раскладка','switch':'Переключатели','region':'Регион','GPU':'Видеокарта','RAM':'Оперативная память','storage':'Накопитель'}
REASONS={'configuration_specific':'Нужен источник точной конфигурации','family_options_or_variant_values':'Перечень вариантов не подтверждает выбранный вариант','model_not_proven':'Точная модель не подтверждена','identity_or_software_help':'Служебное поле модели или ПО','axis_or_product_context_unproven':'Оси или измеряемый объект не подтверждены'}
def project(rows):
 labels={'product_dimensions__width':'Ширина','product_dimensions__height':'Высота','product_dimensions__depth':'Глубина','product_weight':'Вес'}
 for row in rows:
  row['display_name']=labels.get(row['normalized_name'],LABELS.get(row['display_name'],row['display_name']))
  raw=next((v.get('raw_name','') for k,v in row.get('sources',{}).items() if k.startswith('razer_')),'')
  if raw and re.search('[А-Яа-я]',raw) and row['normalized_name'] not in labels:row['display_name']=raw
  row['display_name']=re.sub(r'\bHz\b','Гц',row['display_name'],flags=re.I)
  row['razer_presentation']=True
  for v in ([row['resolved']] if row.get('resolved') else [])+list(row.get('sources',{}).values()):
   if not v.get('display_value'):continue
   text=v['display_value']
   for term in ('HyperPolling','Focus Pro','Razer Chroma RGB','HyperSpeed Wireless','Snap Tap','Gen-3','Bluetooth','PTFE','DPI','IPS','USB-C','USB-A','Razer Speedflex'):
    text=re.sub(re.escape(term),term,text,flags=re.I)
   for p,r in ((r'\bup to\b','До'),(r'\b(?:hours?|hrs?)\b','ч'),(r'\bat\b','при'),(r'\bHz\b','Гц'),(r'\bmm\b','мм')):text=re.sub(p,r,text,flags=re.I)
   v['display_value']=text
 return rows
