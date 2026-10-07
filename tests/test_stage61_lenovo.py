from __future__ import annotations
import copy
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from product_tool.adapters.lenovo_psref import parse_exact,read_capture
from product_tool.adapters.lenovo_documents import verify_sg,verify_pdf
from product_tool import jobs,storage,worker,lenovo_pipeline,attribute_projection,card_evidence,exporter
from product_tool.adapters.lenovo import LenovoAdapter
from product_tool.adapters.common import SourceDocument,RawAttribute,PhotoCandidate
from product_tool.resolution import resolve_attributes

ARTICLE='21AB1234US'

def payloads():
    info={'code':1,'data':{'Model':ARTICLE,'ProductKey':'Test_Family','ProductId':42,'ProductName':'Test Family'}}
    specs={'code':1,'data':{'ProductKey':'Test_Family','ProductID':42,'ModelGroupTable':[{'k':'Model','v':ARTICLE}],
        'SpecData':[{'title':'PERFORMANCE','name':'Processor','content':['CPU A']},{'name':'Memory','content':['16 GB']},
                    {'name':'Case Color','content':['Blue']},{'name':'Dimensions (WxDxH)','content':['300 x 200 x 15 mm (11.81 x 7.87 x 0.59 inches)']}]}}
    return info,specs

def save_capture(root,info,specs):
    records=[]
    for kind,payload,query in [('GetInfoByKey',info,'ModelCode'),('SpecData',specs,'model_code')]:
        raw=json.dumps(payload).encode();digest=hashlib.sha256(raw).hexdigest();name=digest+'.json';(root/name).write_bytes(raw)
        records.append({'url':f'https://psref.lenovo.com/api/model/Info/{kind}?{query}={ARTICLE}','status':200,'file':name,'sha256':digest})
    (root/f'{ARTICLE}.manifest.json').write_text(json.dumps({'article':ARTICLE,'entry_url':f'https://psref.lenovo.com/Detail/Model?M={ARTICLE}','records':records}),encoding='utf-8')

class ExactPsrefTests(unittest.TestCase):
    def test_exact_body_and_returned_mtm_row_are_primary_facts(self):
        info,spec=payloads();doc,r=parse_exact(info,spec,ARTICLE,'https://psref.lenovo.com/Detail/Model')
        self.assertEqual(doc.source_key,'lenovo_psref');self.assertEqual(doc.match_level,'full_sku')
        self.assertEqual(len(doc.attributes),4);self.assertEqual(r['raw_psref'],spec)
    def test_request_echo_without_returned_model_row_never_confirms(self):
        info,spec=payloads();spec['data']['ModelGroupTable']=[]
        doc,r=parse_exact(info,spec,ARTICLE,f'https://psref.lenovo.com/Detail?M={ARTICLE}')
        self.assertNotEqual(doc.match_level,'full_sku');self.assertFalse(doc.attributes)
    def test_other_mtm_is_not_promoted_by_requested_url(self):
        info,spec=payloads();spec['data']['ModelGroupTable'][0]['v']='21AB9999US'
        self.assertFalse(parse_exact(info,spec,ARTICLE,'https://psref.lenovo.com/Detail')[0].attributes)
    def test_cross_family_info_and_specs_cannot_be_combined(self):
        info,spec=payloads();spec['data']['ProductKey']='Other_Family'
        self.assertFalse(parse_exact(info,spec,ARTICLE,'https://psref.lenovo.com/Detail')[0].attributes)
    def test_cto_template_is_not_a_resolved_configuration(self):
        info,spec=payloads();info['data']['Model']='21ABCTO1WW';spec['data']['ModelGroupTable'][0]['v']='21ABCTO1WW'
        self.assertFalse(parse_exact(info,spec,'21ABCTO1WW','https://psref.lenovo.com/Detail')[0].attributes)
    def test_qualified_weight_and_maximum_capabilities_remain_candidates(self):
        info,spec=payloads();spec['data']['SpecData'] += [
            {'name':'Weight','content':['1.5 kg'],'feature_note':['It may not be the exact weight for each specific model.']},
            {'name':'Max Memory','content':['64 GB']},{'name':'Battery','content':['optional 57Wh']}]
        doc,r=parse_exact(info,spec,ARTICLE,'https://psref.lenovo.com/Detail')
        self.assertFalse({'Weight','Max Memory','Battery'} & {a.name for a in doc.attributes})
        self.assertEqual(len(r['configuration_candidates']),3)
    def test_configured_optional_ports_are_actual_configuration_not_family_options(self):
        info,spec=payloads();spec['data']['SpecData'].append({'name':'Optional Rear Ports (configured)','content':['1x HDMI']})
        doc,_=parse_exact(info,spec,ARTICLE,'https://psref.lenovo.com/Detail')
        self.assertIn('Optional Rear Ports (configured)',{a.name for a in doc.attributes})
    def test_multiple_fixed_ports_are_preserved_and_not_treated_as_multiple_configurations(self):
        info,spec=payloads();spec['data']['SpecData'].append({'name':'Standard Ports','content':['2x USB-A','1x HDMI']})
        doc,_=parse_exact(info,spec,ARTICLE,'https://psref.lenovo.com/Detail')
        self.assertEqual(next(a.value for a in doc.attributes if a.name=='Standard Ports'),'2x USB-A; 1x HDMI')
    def test_multiple_cpu_or_display_options_are_not_actual_configuration(self):
        info,spec=payloads();spec['data']['SpecData']=[{'name':'Processor','content':['CPU A','CPU B']},{'name':'Display','content':['IPS or OLED']}]
        doc,report=parse_exact(info,spec,ARTICLE,'https://psref.lenovo.com/Detail')
        self.assertFalse(doc.attributes);self.assertEqual(len(report['configuration_candidates']),2)
    def test_captured_bytes_must_match_manifest_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_capture(root,*payloads());self.assertEqual(read_capture(root,ARTICLE)[0].match_level,'full_sku')
            manifest=json.loads((root/f'{ARTICLE}.manifest.json').read_text());(root/manifest['records'][0]['file']).write_text('{}')
            self.assertIsNone(read_capture(root,ARTICLE))
    def test_foreign_request_context_cannot_import_exact_body(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_capture(root,*payloads());path=root/f'{ARTICLE}.manifest.json';manifest=json.loads(path.read_text())
            manifest['records'][1]['url']='https://evil.test/api/model/Info/SpecData?model_code='+ARTICLE
            path.write_text(json.dumps(manifest));self.assertIsNone(read_capture(root,ARTICLE))
    def test_missing_or_non_json_response_is_an_extraction_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_capture(root,*payloads());manifest=json.loads((root/f'{ARTICLE}.manifest.json').read_text())
            (root/manifest['records'][1]['file']).unlink();self.assertIsNone(read_capture(root,ARTICLE))
        self.assertFalse(parse_exact({'code':0},[],ARTICLE,'https://psref.lenovo.com/Detail')[0].attributes)
    def test_model_filtered_gallery_is_not_automatically_confirmed_when_color_metadata_is_null(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_capture(root,*payloads());path=root/f'{ARTICLE}.manifest.json';m=json.loads(path.read_text())
            raw=json.dumps({'code':1,'data':[{'src':'https://psrefstuff.lenovo.com/family.png','color':None}]}).encode();digest=hashlib.sha256(raw).hexdigest();(root/(digest+'.json')).write_bytes(raw)
            m['records'].append({'url':f'https://psref.lenovo.com/api/product/Photo/42?ProductKey=Test_Family&model_code={ARTICLE}','status':200,'file':digest+'.json','sha256':digest});path.write_text(json.dumps(m))
            doc,report=read_capture(root,ARTICLE);self.assertEqual(len(doc.photo_candidates),1);self.assertFalse(report['exact_photo_assets'])
    def test_psref_facts_do_not_need_duplicate_storefront_evidence(self):
        facts=[{'source_key':'lenovo_psref','normalized_name':'memory','normalized_value':'16 GB','unit':'text'}]
        rows=resolve_attributes(facts,[{'source_key':'lenovo_psref','match_level':'full_sku','error':''}])
        self.assertTrue(rows[0].full_sku_confirmed);self.assertEqual(rows[0].selected_source,'lenovo_psref')

class GuideTests(unittest.TestCase):
    def guide(self):
        return {'data':[{'docId':'SG12345','language':'RU','body':'<html lang="ru"><head><meta name="prodname" content="21AB,21AC"></head><body>'+'Нажмите кнопку и подключите устройство. '*12+'</body></html>'}]}
    def test_actual_russian_guide_body_names_machine_type(self):
        self.assertTrue(verify_sg(self.guide(),ARTICLE,'https://support.lenovo.com/ru/ru/documentation/SG12345','User Guide'))
    def test_russian_support_ui_does_not_prove_english_guide(self):
        p=self.guide();p['data'][0]['language']='EN';p['data'][0]['body']=p['data'][0]['body'].replace('lang="ru"','lang="en"')
        self.assertIsNone(verify_sg(p,ARTICLE,'https://support.lenovo.com/ru/ru/documentation/SG12345','User Guide'))
    def test_other_machine_type_cannot_verify_user_guide(self):
        self.assertIsNone(verify_sg(self.guide(),'83ZZ1234US','https://support.lenovo.com/ru/ru/documentation/SG12345','User Guide'))
    def test_hardware_maintenance_is_not_user_guide(self):
        self.assertIsNone(verify_sg(self.guide(),ARTICLE,'https://support.lenovo.com/ru/ru/documentation/SG12345','Hardware Maintenance Manual'))
    def test_missing_saved_guide_is_a_technical_blocker_not_a_checked_absence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'manual_reviews.json').write_text(json.dumps({ARTICLE:{'catalog_checked':True,'documents':[{'type':'User Guide','language':'Русский','url':'https://download.lenovo.com/guide.pdf','source_url':'https://download.lenovo.com/guide_en.pdf','proof_file':'missing.pdf'}]}}))
            adapter=LenovoAdapter(session=object(),psref_capture_dir=root);report={};adapter.load_document_reviews(ARTICLE,report)
            self.assertEqual(report['manual_status'],'Не проверена');self.assertIn('manual_review_gap',report)
    def test_russian_pdf_title_can_wrap_and_language_thresholds_stay_shared(self):
        pages=[SimpleNamespace(extract_text=lambda:'Test Family Руководство\nпользователя '+ARTICLE[:4]+'\n'+('Нажмите кнопку и подключите компьютер для эксплуатации. '*150))]
        with patch('pypdf.PdfReader',return_value=SimpleNamespace(pages=pages)):
            result=verify_pdf(b'%PDF-test',ARTICLE,'Test Family')
        self.assertTrue(result['verified']);self.assertTrue(result['language_assessment']['russian_instruction'])

class RecoveryPipelineTests(unittest.TestCase):
    def test_only_reviewed_asset_is_selected_and_manual_deselection_survives_rerun(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/'audit.sqlite3';jobs.initialize(db)
            with storage._connection(db) as conn:
                conn.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('lenovo','test','Products','{}',storage._now()))
                pid=conn.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('lenovo',1,'Test','Lenovo',ARTICLE,'','laptop',0,'[]','{}')).lastrowid
            class Adapter:
                source_key='lenovo_psref';reports={ARTICLE:{'exact_photo_assets':['reviewed'],'manual_status':'Проверена','verified_documents':[]}}
                def find_source(self,*a,**kw):return SourceDocument('lenovo_psref','PSREF','https://psref.lenovo.com/Detail',found_model=ARTICLE,match_level='full_sku',attributes=[RawAttribute('Memory','16 GB')],photo_candidates=[PhotoCandidate('https://psrefstuff.lenovo.com/a.png','reviewed'),PhotoCandidate('https://psrefstuff.lenovo.com/b.png','family')])
                def find_documents(self,*a):return []
            class Dealer:
                def find_source(self,*a,**kw):return SourceDocument('dns','DNS','',match_level='dealer_url_needed')
            def run():
                jobs.enqueue(db,pid,[1,2,3,4,6]);worker.run_once(db,lenovo_adapter_factory=Adapter,dns_adapter_factory=Dealer)
            run();photos=jobs.get_photo_candidates(db,pid)
            self.assertEqual([p['asset_key'] for p in photos if p['selected']],['reviewed'])
            self.assertEqual(lenovo_pipeline.card_readiness(db,pid)['verdict'],'export_ready_with_gaps')
            self.assertIn('russian_user_guide_not_verified',lenovo_pipeline.card_readiness(db,pid)['gaps'])
            jobs.set_photo_selection(db,pid,[],mode='none');run()
            self.assertEqual(lenovo_pipeline.card_readiness(db,pid)['verdict'],'not_ready')
            self.assertIn('verified_gallery_not_selected',lenovo_pipeline.card_readiness(db,pid)['gaps'])
    def test_production_worker_consumes_captures_with_strict_gallery_gate_and_russian_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);capture=root/'psref_captures';capture.mkdir();save_capture(capture,*payloads());db=root/'audit.sqlite3';jobs.initialize(db)
            with storage._connection(db) as conn:
                conn.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('lenovo','test','Products','{}',storage._now()))
                pid=conn.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('lenovo',1,'Test Family','Lenovo',ARTICLE,'','laptop',0,'[]','{}')).lastrowid
            class Dealer:
                def find_source(self,*a,**kw):return SourceDocument('dns','DNS','',match_level='dealer_url_needed')
            jobs.enqueue(db,pid,[1,2,3,4,6]);worker.run_once(db,lenovo_adapter_factory=lambda:LenovoAdapter(fetch_log_path=root/'fetch.json',session=object()),dns_adapter_factory=Dealer)
            self.assertEqual(jobs.list_jobs(db,pid)[0]['status'],'done')
            self.assertEqual(lenovo_pipeline.card_readiness(db,pid)['verdict'],'not_ready')
            rows=attribute_projection.final_attribute_rows(db,pid)
            self.assertTrue({'Ширина товара, мм','Высота товара, мм','Глубина товара, мм'} <= {r['display_name'] for r in rows})
            self.assertTrue(all(f['source_key']=='lenovo_psref' for f in jobs.get_facts(db,pid)))
            self.assertTrue(all('inches' in r['sources']['lenovo_psref']['raw_value'] for r in rows if r.get('derived_from')))
            self.assertIn('Точный MTM Lenovo',jobs.identification_status(jobs.get_source_pages(db,pid)))

if __name__=='__main__':unittest.main()
