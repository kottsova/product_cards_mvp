"""Closed structural grammars for compound technical facts, independent of brand.

Only complete recognized structures are decomposed. Unknown clauses retain the
original fact. Every child keeps its original raw block through normalization.
"""
from dataclasses import dataclass
import re


def text(value):
    return ' '.join(str(value or '').translate(str.maketrans({'\u2011':'-','\u2010':'-','\u2013':'-','\u00a0':' '})).split())


@dataclass(frozen=True)
class Component:
    key:str
    value:str
    unit:str=''


FIELDS={
 'magnet_array':('Массив магнитов','Беспроводная зарядка','feature'),
 'alignment_magnet':('Магнит выравнивания','Беспроводная зарядка','feature'),
 'accessory_identification_nfc':('Идентификация аксессуаров NFC','Подключение','feature'),
 'magnetometer':('Магнитометр','Датчики','feature'),
 'facetime_audio':('Аудиозвонки FaceTime','Аудиозвонки','feature'),
 'volte_calls':('Звонки VoLTE','Аудиозвонки','feature'),
 'wifi_calls':('Звонки по Wi-Fi','Аудиозвонки','feature'),
 'shareplay':('SharePlay','Аудиозвонки','feature'),
 'screen_sharing':('Демонстрация экрана','Аудиозвонки','feature'),
 'spatial_audio':('Пространственное аудио','Аудио','feature'),
 'voice_isolation':('Изоляция голоса','Аудио','feature'),
 'wide_spectrum_microphone':('Широкий спектр микрофона','Аудио','feature'),
 'adjustable_volume_limit':('Настраиваемое ограничение громкости','Аудио','feature'),
 'audio_supported_formats':('Поддерживаемые аудиоформаты','Аудио','core'),
 'video_supported_formats':('Поддерживаемые видеоформаты','Воспроизведение видео','core'),
 'hdr_supported_formats':('Поддерживаемые форматы HDR','Воспроизведение видео','core'),
 'airplay_video_output':('Вывод видео AirPlay','Воспроизведение видео','feature'),
 'usb_c_charging':('Зарядка через USB-C','Разъёмы и зарядка','feature'),
 'usb_c_displayport':('DisplayPort через USB-C','Разъёмы и зарядка','feature'),
 'usb_c_data_standard':('Стандарт передачи данных USB-C','Разъёмы и зарядка','core'),
 'usb_c_max_data_rate':('Максимальная скорость передачи данных USB-C','Разъёмы и зарядка','core'),
 'display_brightness_typical_max':('Максимальная типичная яркость экрана, нит','Дисплей','core'),
 'display_brightness_hdr_peak':('Пиковая яркость HDR, нит','Дисплей','core'),
 'display_brightness_outdoor_peak':('Пиковая яркость на улице, нит','Дисплей','core'),
 'display_brightness_min':('Минимальная яркость экрана, нит','Дисплей','core'),
}
PROTOCOLS={'magsafe':'MagSafe','qi2':'Qi2','qi':'Qi','usb_c':'USB-C','usb_pd':'USB PD','quick_charge':'Quick Charge'}
for key,label in PROTOCOLS.items():
    FIELDS['wireless_charging_power_'+key]=(f'Мощность беспроводной зарядки {label}, Вт','Беспроводная зарядка','core')
    for suffix,title in [('supported',f'Быстрая зарядка {label}'),('target_percent',f'Уровень заряда при быстрой зарядке {label}, %'),('time_minutes',f'Время быстрой зарядки {label}, мин'),('adapter_power',f'Мощность адаптера для быстрой зарядки {label}, Вт'),('conditions',f'Условия быстрой зарядки {label}')]:
        FIELDS[f'fast_charge_{key}_{suffix}']=(title,'Быстрая зарядка','feature' if suffix=='supported' else 'core')

def field_spec(key):return FIELDS.get(key)

EXACT={
 'magnet array':'magnet_array','alignment magnet':'alignment_magnet','accessory identification nfc':'accessory_identification_nfc','magnetometer':'magnetometer',
 'facetime audio':'facetime_audio','voice over lte (volte)':'volte_calls','wi-fi calling':'wifi_calls',
 'shareplay':'shareplay','screen sharing':'screen_sharing','spatial audio':'spatial_audio','spatial audio playback':'spatial_audio',
 'user-configurable maximum volume limit':'adjustable_volume_limit',
}

def _charging(value):
    starts=list(re.finditer(r'(?:up to\s+)?\d+(?:[.,]\d+)?%\s+charge\s+in\s+(?:(?:around|about)\s+)?\d+(?:[.,]\d+)?\s+minutes?\b',value,re.I))
    if not starts:return None
    prefix=value[:starts[0].start()].strip(' :;')
    if prefix and not re.fullmatch(r'fast-charge capable',prefix,re.I):return None
    result=[];seen=set()
    for i,start in enumerate(starts):
        clause=value[start.start():starts[i+1].start() if i+1<len(starts) else len(value)].strip(' ;')
        modes=[key for key,pattern in [('magsafe',r'\bMagSafe\b'),('usb_c',r'\bUSB-C\b'),('usb_pd',r'\bUSB PD\b'),('quick_charge',r'\bQuick Charge\b'),('qi2',r'\bQi2\b')] if re.search(pattern,clause,re.I)]
        if len(modes)!=1 or modes[0] in seen:return None
        mode=modes[0];seen.add(mode)
        m=re.match(r'(up to\s+)?(\d+(?:[.,]\d+)?)%\s+charge\s+in\s+((?:around|about)\s+)?(\d+(?:[.,]\d+)?)\s+minutes?\b(.*)',clause,re.I)
        if not m:return None
        watts=list(re.finditer(r'(\d+(?:[.,]\d+)?)\s*W(?:-capable)?\s+adapter\s*(or higher)?',m[5],re.I))
        if len(watts)!=1:return None
        power=watts[0];base='fast_charge_'+mode+'_'
        number=lambda s:s.replace(',','.')
        result.extend([Component(base+'supported','true','bool'),
            Component(base+'target_percent',('up_to=' if m[1] else '')+number(m[2]),'%'),
            Component(base+'time_minutes',('approx=' if m[3] else '')+number(m[4]),'min'),
            Component(base+'adapter_power',('at_least=' if power[2] else '')+number(power[1]),'W'),
            Component(base+'conditions',m[5].strip())])
    return result

def decompose(fact):
    value=text(fact.value)
    charging=_charging(value)
    if charging:return charging
    parts=[p.strip() for p in re.split(r';|\n|\r',str(fact.value)) if p.strip()]
    if len(parts)<2:return None
    parts=[text(p) for p in parts]
    result=[];port_context=False
    for part in parts:
        lowered=part.casefold()
        brightness=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s+nits?\s+(max brightness \(typical\)|peak brightness \(HDR\)|peak brightness \(outdoor\)|minimum brightness)',part,re.I)
        if brightness:
            scope={'max brightness (typical)':'typical_max','peak brightness (hdr)':'hdr_peak','peak brightness (outdoor)':'outdoor_peak','minimum brightness':'min'}[brightness[2].casefold()]
            result.append(Component('display_brightness_'+scope,brightness[1].replace(',','.'),'nit'));continue
        if lowered in EXACT:
            result.append(Component(EXACT[lowered],'true','bool'));continue
        if re.fullmatch(r'voice isolation and wide spectrum microphone modes',part,re.I):
            result.extend([Component('voice_isolation','true','bool'),Component('wide_spectrum_microphone','true','bool')]);continue
        m=re.fullmatch(r'(MagSafe|Qi2|Qi) wireless charging (up to\s+)?(\d+(?:[.,]\d+)?)\s*W',part,re.I)
        if m:
            result.append(Component('wireless_charging_power_'+m[1].casefold(),('up_to=' if m[2] else '')+m[3].replace(',','.'),'W'));continue
        m=re.fullmatch(r'supported formats include\s+(.+)',part,re.I)
        if m:
            scope=text(fact.section+' '+fact.name).casefold()
            kind='audio' if re.search(r'audio|аудио',scope) else 'video' if re.search(r'video|видео',scope) else ''
            if not kind:return None
            result.append(Component(kind+'_supported_formats',m[1]));continue
        m=re.fullmatch(r'HDR with\s+(.+)',part,re.I)
        if m:result.append(Component('hdr_supported_formats',m[1]));continue
        if re.match(r'up to \d+K HDR AirPlay\b',part,re.I):result.append(Component('airplay_video_output',part));continue
        if re.fullmatch(r'USB-C connector with support for:',part,re.I):port_context=True;continue
        if port_context:
            if lowered=='charging':result.append(Component('usb_c_charging','true','bool'));continue
            if lowered=='displayport':result.append(Component('usb_c_displayport','true','bool'));continue
            m=re.fullmatch(r'USB\s+(\d+(?:\.\d+)?)\s*\(up to\s+(\d+(?:\.\d+)?)\s*Gb/s\)',part,re.I)
            if m:
                result.extend([Component('usb_c_data_standard','USB '+m[1]),Component('usb_c_max_data_rate','up_to='+m[2],'Gbit/s')]);continue
        return None
    if len(result)<2:return None
    keys=[x.key for x in result]
    # Several alternatives for the same parameter need configuration resolution,
    # not a first-value rule or a merged column.
    if len(set(keys))!=len(keys):return None
    return result


def evidence(facts):
    rows=[]
    for fact in facts:
        children=decompose(fact)
        if children:
            rows.append(dict(raw_name=fact.name,raw_value=fact.value,section=fact.section,
                rule='complete_explicit_structure',children=[dict(key=c.key,label=FIELDS[c.key][0],value=c.value,unit=c.unit) for c in children]))
    return rows
