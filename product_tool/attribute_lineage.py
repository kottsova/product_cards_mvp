"""Explicit raw admission lineage, independent of identity and fact resolution."""
import re
import unicodedata

def text_key(value):
    text=str(value or '').translate(str.maketrans({'\u2010':'-','\u2011':'-','\u2012':'-','\u2013':'-','\u2014':'-','\u2018':"'",'\u2019':"'",'\u201c':'"','\u201d':'"'}))
    # Footnote glyphs are source annotations, not capacities or model numbers.
    text=re.sub('[⁰¹²³⁴⁵⁶⁷⁸⁹]+','',text)
    return re.sub(r'\s+',' ',unicodedata.normalize('NFC',text)).strip().casefold()

def source_row_matches(raw,origin):
    label=lambda r:r.get('raw_label',r.get('label',r.get('name','')))
    value=lambda r:r.get('raw_value',r.get('value',''))
    sections=lambda r:{text_key(r[k]) for k in ('section','source_section') if r.get(k)}
    return text_key(label(raw))==text_key(label(origin)) and text_key(value(raw))==text_key(value(origin)) and (not sections(origin) or bool(sections(raw)&sections(origin)))

def linked_facts(raw,admissions,facts):
    """Match exact parser-authored targets; never infer identity from a value."""
    found={f['id']:f for f in facts if source_row_matches(raw,{'raw_label':f['raw_name'],'raw_value':f['raw_value'],'section':f['section']})}
    if not found:
        label=raw.get('raw_label',raw.get('label',raw.get('name','')));value=raw.get('raw_value',raw.get('value',''))
        same=[f for f in facts if text_key(f['raw_name'])==text_key(label) and text_key(f['raw_value'])==text_key(value)]
        component=text_key(raw.get('component',raw.get('component_scope','')))
        # Presentation may rename a technical heading. A unique same-name,
        # same-value fact may be linked, except explicit component ownership.
        if len({f['normalized_name'] for f in same})==1 and component in {'','not yet classified'} and not re.search(r'microphone|headphone|микрофон|наушник',text_key(raw.get('section',''))):
            found={f['id']:f for f in same}
    for admitted in admissions:
        origins=admitted.get('raw_rows',[admitted])
        if not any(source_row_matches(raw,o) for o in origins):continue
        targets=admitted.get('derived_fields',[])
        if admitted.get('name'):targets=[*targets,{'name':admitted['name'],'value':admitted['value']}]
        elif admitted.get('accepted_label'):targets=[*targets,{'name':admitted['accepted_label'],'value':admitted['value']}]
        elif admitted.get('label') and admitted.get('raw_value') is not None:targets=[*targets,{'name':admitted['label'],'value':admitted['value']}]
        for target in targets:
            for f in facts:
                if text_key(f['raw_name'])==text_key(target['name']) and text_key(f['raw_value'])==text_key(target['value']):found[f['id']]=f;continue
                # Use the existing quantity/boolean normalizer, never a fuzzy
                # substring match, for translated aliases and printed units.
                from .normalization import normalize_fact
                from .adapters.common import RawAttribute
                normalized=normalize_fact(RawAttribute(target['name'],target['value'],target.get('section',f['section']),value_cell=True))
                if (normalized.normalized_name,normalized.normalized_value,normalized.unit)==(f['normalized_name'],f['normalized_value'],f['unit']):found[f['id']]=f
    return list(found.values())

def technical_role(label,section=''):
    """Closed semantic feature vocabulary; quantities remain core."""
    return 'feature' if re.search(r'trigger|haptic|promotion|dynamic island|haptic touch|hyper\w*|chroma|quick resume|smart delivery|mop.?extend|airdry|hob2hood|ambient aware|turbo.?wash|ai dd|трениров|безопасност|эколог|язык|siri|apple pay|жест|специальные возможности|ray tracing|трассиров|функци|подсветк|макрос',label+' '+section,re.I) else 'core'
