"""Russian labels for already scoped Dreame facts, without resolving components anew."""
import re
LABELS={'Rated Power':'Номинальная мощность','Maximum Suction':'Максимальная мощность всасывания','Suction Power':'Мощность всасывания','Battery Capacity':'Ёмкость аккумулятора','Maximum Runtime':'Максимальное время работы','Runtime':'Время работы','Charging Time':'Время зарядки','Navigation':'Навигация','Obstacle Avoidance':'Обнаружение препятствий','Obstacle Crossing Height':'Высота преодоления препятствий','Main Brush Type':'Тип основной щётки','Brush Type':'Тип щётки','Type of Brush':'Тип щётки','Side Brush':'Боковая щётка','Mop Type':'Тип швабры','Mop Lifting':'Подъём швабр','Mop Extension':'Выдвижение швабры','Edge Cleaning':'Очистка краёв','Hot Water Washing':'Мойка горячей водой','Hot Air Drying':'Сушка горячим воздухом','Auto Detergent':'Автоподача моющего средства','Auto Empty':'Автоопустошение','Clean Water Tank':'Бак чистой воды','Used Water Tank':'Бак грязной воды','Dirty Water Tank':'Бак грязной воды','Dust Bag':'Мешок для пыли','Dust Cup':'Пылесборник','Detergent Tank':'Бак моющего средства','Weight':'Вес товара, кг','Machine Weight':'Вес товара, кг','Robot Vacuum Weight':'Вес робота, кг','Base Station Weight':'Вес станции, кг','Robot Vacuum Dimensions':'Габариты робота (порядок осей не опубликован)','Base Station Dimensions':'Габариты станции (порядок осей не опубликован)','Dimensions':'Габариты (порядок осей не опубликован)','Width':'Ширина товара, мм','Height':'Высота товара, мм','Depth':'Глубина товара, мм','Motor':'Двигатель','Cleaning Modes':'Режимы уборки','Working Mode':'Режимы работы','Auto Dirt Detection':'Автообнаружение загрязнений','Dirt Detection':'Обнаружение загрязнений','Self Cleaning':'Самоочистка','Self-Drying':'Сушка','Lie Flat':'Горизонтальное положение','Screen':'Дисплей','Prompts':'Уведомления','App Support':'Поддержка приложения'}
BRANDED=('HyperStream','MopExtend','RoboSwing','DuoBrush','VersaLift','ProLeap','DToF','3DAdapt','AceClean DryBoard','ThermoHub','LDS','LiDAR','Dreamehome','Eco','Standard','Turbo','Max')

def label(raw,section=''):
    base=LABELS.get(raw,raw if re.search('[а-яё]',raw,re.I) or any(x in raw for x in BRANDED) else 'Характеристика: '+raw)
    if raw.startswith('Maximum Runtime — '):base='Максимальное время работы — '+raw.split(' — ',1)[1]
    if raw.startswith(('Used Water Tank — ','Dirty Water Tank — ')):
        mode=raw.split(' — ',1)[1];base='Бак грязной воды — '+{'Standing':'вертикально','Lie-Flat':'горизонтально'}.get(mode,mode)
    if section=='База / станция' and 'станци' not in base.casefold():base=base.replace('товара','станции') if 'товара' in base else base+' (станция)'
    elif section in {'Робот','Устройство','Ручной пылесос'} and re.search(r'бак|пылесборник|мешок',base,re.I):base+=' ('+{'Робот':'робот','Устройство':'устройство','Ручной пылесос':'ручной пылесос'}[section]+')'
    if section=='Ручной пылесос' and 'ручной' not in base.casefold():base+=' (ручной пылесос)'
    return base

def project(rows):
    out=[]
    for original in rows:
        row={**original,'dreame_presentation':True};fact=next(iter(row.get('sources',{}).values()),{});row['display_name']=label(fact.get('raw_name') or row['display_name'],fact.get('section',''))
        if row.get('resolved'):
            row['resolved']=dict(row['resolved']);shown=row['resolved'].get('display_value','')
            for term in BRANDED:shown=re.sub(re.escape(term),term,shown,flags=re.I)
            shown=re.sub(r'\bup to\b','до',shown,flags=re.I)
            shown=re.sub(r'(?<=\d)\s*ml\b',' мл',shown,flags=re.I);shown=re.sub(r'(?<=\d)\s*l\b',' л',shown,flags=re.I)
            row['resolved']['display_value']=shown
        out.append(row)
    return out
