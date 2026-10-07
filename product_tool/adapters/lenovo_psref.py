"""Parse official attended PSREF responses; request parameters are never identity.

Captures are imported explicitly. This module neither issues auth tokens nor
retries a protected API. Original response bytes stay separate from Support.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from bs4 import BeautifulSoup
from .common import SourceDocument, RawAttribute, PhotoCandidate, clean_text

KEY = 'lenovo_psref'
QUALIFIED = re.compile(r'\b(up to|starting (?:at|from)|optional|varies|depending|around|approximately|approximate|may not be the exact|var[yies]+ between models)\b', re.I)
CAPABILITY = re.compile(r'^(max(?:imum)? |supported |optional |support[s]?\b)', re.I)

def plain(value):
    return clean_text(BeautifulSoup(str(value), 'html.parser').get_text(' ', strip=True))

def parse_exact(info, payload, article, url):
    article=clean_text(article).upper()
    info=info if isinstance(info,dict) else {};payload=payload if isinstance(payload,dict) else {}
    data=payload.get('data') if isinstance(payload.get('data'),dict) else {}
    identity=info.get('data') if isinstance(info.get('data'),dict) else {}
    model_rows=[plain(x.get('v','')).upper() for x in (data.get('ModelGroupTable') or []) if isinstance(x,dict) and x.get('k')=='Model']
    exact=(info.get('code')==1 and payload.get('code')==1 and str(identity.get('Model') or '').upper()==article
           and model_rows==[article] and identity.get('ProductKey')==data.get('ProductKey')
           and str(identity.get('ProductId'))==str(data.get('ProductID')) and not re.search('CTO|XXXX',article))
    report={'article':article,'raw_psref':payload,'psref_info':info,'configuration_candidates':[],
            'configuration_identity':{'relation':'exact_mtm' if exact else 'unknown','returned_model':identity.get('Model',''),
                                      'model_row':model_rows,'configuration_resolved':exact,'product_key':data.get('ProductKey')},
            'manuals':[],'manual_status':'Не проверена','sources':[{'type':'psref','url':url,'relation':'exact_mtm' if exact else 'unknown'}],
            'exact_photo_assets':[],'photos_relation':'family_model','rejected_specs':[],'accepted_specs':[]}
    doc=SourceDocument(KEY,'Lenovo PSREF',url,found_model=identity.get('Model',''),match_level='full_sku' if exact else 'unknown',
                       evidence=json.dumps(report['configuration_identity'],ensure_ascii=False),error='' if exact else 'PSREF returned model/row/product relation not proven')
    section='Specifications'
    for row in data.get('SpecData',[]) or []:
        if not isinstance(row,dict):continue
        section=row.get('title') or section
        label=row.get('name','')
        content=row.get('content',[])
        if not isinstance(label,str) or not label or not isinstance(content,list):continue
        values=[plain(x) for x in content if isinstance(x,(str,int,float))]
        if not values:continue
        value='; '.join(values)
        notes=' '.join(plain(x) for key in ('note','feature_note','value_note') for x in (row.get(key,[]) or []) if isinstance(x,str))
        raw={'section':section,'raw_label':label,'value':value,'notes':notes}
        option_field=label.casefold() in {'processor','graphics','memory','storage','display','wlan + bluetooth'}
        alternatives=option_field and (bool(re.search(r'\b(?:or|either|one of|available with)\b',value,re.I)) or
            (len(values)>1 and not all(re.match(r'^\d+x\b',v,re.I) for v in values)))
        reason=('unresolved_model_relation' if not exact else 'qualified_or_model_dependent' if QUALIFIED.search(value+' '+notes)
                else 'ambiguous_configuration_options' if alternatives
                else 'platform_capability' if (CAPABILITY.search(label) and '(configured)' not in label.lower()) or (label=='Operating System' and value.startswith('Support '))
                else 'support_service_content' if re.search(r'warranty|service|repair|BIOS|driver',label,re.I) else '')
        if reason:
            candidate={**raw,'scope':'family_option' if not exact else 'conditional_configuration','reason':reason}
            report['configuration_candidates'].append(candidate);report['rejected_specs'].append(candidate)
        else:
            doc.attributes.append(RawAttribute(label,value,section));report['accepted_specs'].append(raw)
    return doc,report

def read_capture(directory, article):
    directory=Path(directory);article=clean_text(article).upper()
    if not re.fullmatch(r'[A-Z0-9]{8,12}',article):return None
    path=directory/f'{article}.manifest.json'
    if not path.is_file():return None
    try:manifest=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    if manifest.get('article')!=article or manifest.get('challenge'):return None
    loaded={}
    for record in manifest.get('records',[]):
        if record.get('status')!=200 or not record.get('file'):continue
        parsed=urlsplit(record['url']);query=parse_qs(parsed.query)
        if parsed.scheme!='https' or parsed.hostname!='psref.lenovo.com':continue
        name=record['file']
        if Path(name).name!=name:continue
        try:raw=(directory/name).read_bytes();decoded=json.loads(raw)
        except (OSError,ValueError):continue
        if hashlib.sha256(raw).hexdigest()!=record.get('sha256'):continue
        if parsed.path.endswith('/GetInfoByKey') and query.get('ModelCode')==[article]:loaded['info']=decoded
        elif parsed.path.endswith('/SpecData') and query.get('model_code')==[article]:loaded['specs']=decoded
        elif '/product/Photo/' in parsed.path and query.get('model_code')==[article]:loaded['photos']=(decoded,query)
        elif parsed.path.endswith('/ShowDocumentations'):loaded['documents']=(decoded,query)
    if not {'info','specs'}<=loaded.keys():return None
    doc,report=parse_exact(loaded['info'],loaded['specs'],article,manifest.get('final_url') or manifest['entry_url'])
    report['capture_manifest']=manifest
    product_key=report['configuration_identity']['product_key']
    if loaded.get('photos') and loaded['photos'][1].get('ProductKey')==[product_key]:
        report['raw_gallery']=loaded['photos'][0]
        for image in loaded['photos'][0].get('data',[]):
            url=image.get('src','')
            if urlsplit(url).hostname not in {'psrefstuff.lenovo.com','psref.lenovo.com'}:continue
            kind='lifestyle' if 'lifestyle' in str(image).lower() else 'product_gallery'
            doc.photo_candidates.append(PhotoCandidate(url,url,kind,excluded_reason='family_render_unverified'))
    if loaded.get('documents') and loaded['documents'][1].get('ProductKey')==[product_key]:report['raw_documentation']=loaded['documents'][0]
    review_path=directory/'photo_reviews.json'
    if review_path.is_file() and doc.match_level=='full_sku':
        color=next((x['value'] for x in report['accepted_specs'] if x['raw_label']=='Case Color'),'')
        reviews=json.loads(review_path.read_text(encoding='utf-8')).get(article,[])
        for review in reviews:
            asset=review.get('asset_key')
            image_file=review.get('image_file','')
            image_ok=bool(image_file and Path(image_file).name==image_file and (directory/image_file).is_file()
                          and hashlib.sha256((directory/image_file).read_bytes()).hexdigest()==review.get('image_sha256'))
            if review.get('verified') and image_ok and review.get('role')=='color_bound_render' and review.get('case_color')==color and asset in {p.asset_key for p in doc.photo_candidates}:
                report['exact_photo_assets'].append(asset)
        doc.photo_candidates=[PhotoCandidate(p.url,p.asset_key,p.kind,excluded_reason='' if p.asset_key in report['exact_photo_assets'] else p.excluded_reason) for p in doc.photo_candidates]
        report['photo_reviews']=reviews
    return doc,report
