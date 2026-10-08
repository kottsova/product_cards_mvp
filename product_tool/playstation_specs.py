"""Scoped official hardware tables; no inference from an input marketing name."""
import re
from .adapters.common import RawAttribute, SourceDocument, clean_text
from .playstation_identity import codes

LABELS = {
    'CPU': 'Процессор', 'GPU': 'Графический процессор', 'Memory': 'Оперативная память',
    'Storage': 'Объём накопителя', 'Maximum rated power': 'Максимальная потребляемая мощность',
    'Mass': 'Вес товара', 'Battery capacity': 'Ёмкость аккумулятора',
    'Input power rating': 'Питание', 'Electrical rating': 'Питание',
    'Battery type': 'Тип аккумулятора', 'Battery voltage': 'Напряжение аккумулятора',
    'Input/output': 'Разъёмы', 'Networking': 'Сетевые интерфейсы', 'AV output': 'Видеовыход',
    'Screen': 'Экран', 'Sound': 'Динамики', 'Charge time': 'Время зарядки',
    'Operating temperature': 'Рабочая температура',
}
DIM_LABELS = ('Ширина товара, мм', 'Высота товара, мм', 'Глубина товара, мм')

def clean_pdf(value):
    # These PDFs print decimal points as an unencoded glyph; retain original raw text too.
    value = re.sub(r'(?<=\d)\s*�\s*(?=\d)', '.', value)
    value = re.sub(r'(?<=\d)\s*�', '.', value).replace('Approx�', 'Approx.').replace('TFL OPS', 'TFLOPS')
    value = re.sub(r'(×\s*)2\s+16(?=\s*mm)', r'\g<1>216', value)
    return clean_text(value)

def cover_matches(cover, code, linked_codes):
    """A support link must name the exact code even when a shared cover prints CFI-20XX."""
    found = codes(cover)
    if code in found: return True
    if code not in linked_codes: return False
    base = re.sub(r'[AB]$', '', code)
    return base in found or any(re.fullmatch(re.escape(c).replace('XX', r'\d{2}') + '[AB]?', code) for c in found if 'XX' in c)

def parse_hardware_specs(text, url, code, *, linked_codes=(), drive_relation=None):
    doc = SourceDocument('playstation_hardware', 'PlayStation hardware guide', url,
                         found_model=code, match_level='hardware_confirmed')
    raw, candidates = [], []
    parts = re.split(r'(?m)^Specifications\s*$', text)
    if len(parts) < 2: return doc, raw, candidates
    block = parts[1]
    console = '/ps5-docs/' in url
    combined = bool(re.search(r'/\d{4}ab/', url))
    if console: block = re.split(r'Wireless controller|DualSense', block)[0]
    else: block = re.split(r'GUARANTEE|Compliance|For customers|System software', block)[0]
    # A/B is the shipped configuration. The source has removable-drive installation states.
    # Routing requires an exact official link and independently evidenced A/B semantics.
    routed = (combined and code in linked_codes and cover_matches(text[:1000], code, linked_codes)
              and drive_relation in {'with_disc', 'without_disc'}
              and bool(re.search(r'Console with the disc drive\s+installed\s+Console without a disc drive\s+installed',block)))
    if combined and not routed:
        return doc, raw, [dict(section='Specifications', raw_label='Combined hardware table',
                              value=block[:6500], reason='Exact linked CFI and evidenced drive-row relation required')]
    lines = [clean_pdf(l) for l in block.splitlines()]
    pattern = re.compile(r'^(' + '|'.join(re.escape(k) for k in sorted(LABELS, key=len, reverse=True)) + r')(?:\*\d)?(?::|\s|$)\s*(.*)')
    i = 0; dimension_context = ''; dim_rows = []
    while i < len(lines):
        line = lines[i]; i += 1
        if not line: continue
        m = pattern.match(line)
        if line.startswith('External dimensions'):
            dimension_context = line
            continue
        if dimension_context and line.startswith('('): dimension_context += ' ' + line; continue
        d = re.search(r'([\d.]+)\s*×\s*([\d.]+)\s*×\s*([\d.]+)\s*mm', line)
        if d and dimension_context:
            if not re.search(r'package|packaging|\bwith\s+(?:the\s+)?stand', dimension_context, re.I):
                dim_rows.append((d.groups(), line))
            continue
        if m:
            label, value = m.groups()
            # Continuations belong to the current row only, not the next table/footnotes.
            while i < len(lines) and not pattern.match(lines[i]) and not re.match(r'External dimensions|^\*|^\d+$|^Console |^Main Processor', lines[i]):
                if label not in {'GPU','Memory','Input/output','Networking','Electrical rating','Screen'}: break
                if lines[i]: value += ' ' + lines[i]
                i += 1
            dimension_context = ''
            item = dict(section='Specifications', raw_label=label, value=clean_text(value),
                        hardware_code=code, row_scope=drive_relation if combined else 'single_hardware')
            raw.append(item)
            if label == 'Mass' and combined:
                masses = re.findall(r'Approx\.?\s*([\d.]+)\s*kg', value)
                if len(masses) != 2:
                    candidates.append({**item,'reason':'Ambiguous mass columns'}); continue
                value = 'Approx. ' + masses[0 if drive_relation == 'with_disc' else 1] + ' kg'
            if value: doc.attributes.append(RawAttribute(LABELS[label], value, section='Характеристики оборудования '+code, value_cell=True))
            continue
        item = dict(section='Specifications',raw_label='Unmapped specification line',value=line,hardware_code=code)
        raw.append(item); candidates.append({**item,'reason':'Unmapped qualifier or technical line'})
    if combined:
        headers = re.search(r'Console with the disc drive\s+installed\s+Console without a disc drive\s+installed', block)
        if len(dim_rows) == 2 and headers:
            dim_rows = [dim_rows[0 if drive_relation == 'with_disc' else 1]]
        else:
            candidates.append(dict(section='Specifications',raw_label='Dimensions',value=str(dim_rows),reason='Ambiguous table column order'))
            dim_rows = []
        doc.attributes.append(RawAttribute('Оптический привод','Ultra HD Blu-ray' if drive_relation=='with_disc' else 'Без установленного привода',section='Конфигурация оборудования '+code,value_cell=True))
    for values, line in dim_rows:
        raw.append(dict(section='Specifications',raw_label=dimension_context or 'External dimensions (excluding projecting parts)',value=line,hardware_code=code,row_scope=drive_relation))
        for label, value in zip(DIM_LABELS, values):
            doc.attributes.append(RawAttribute(label,value+' мм',section='Габариты оборудования '+code+' без выступающих частей',value_cell=True))
    return doc, raw, candidates
