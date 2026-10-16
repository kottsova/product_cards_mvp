"""Production batch projection, truthful phases, form CAPTCHA and binary ZIP."""
import hashlib,io,json,unittest,zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from product_tool import jobs,storage,batch_progress,job_progress,photo_archive,card_evidence
from product_tool.web import create_app,_preview
from product_tool.census.attended_support import looks_like_challenge
from product_tool.census.endpoint_probe import classify_protection
from product_tool.adapters.sulpak import SulpakAdapter
from tests.test_web import workbook_bytes

class ProductionBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.db=self.root/'batches.sqlite3';self.client=TestClient(create_app(self.root));self.addCleanup(self.client.close)
        response=self.client.post('/upload',files={'file':('mixed.xlsx',workbook_bytes([['Бренд','Артикул','Название'],['LG','XL7S','LG XL7S'],['Apple','supplier-1','Apple iPhone 16']]))},follow_redirects=False)
        draft=response.headers['location'].rsplit('/',1)[1];preview=_preview(self.root/'uploads'/f'{draft}.xlsx',storage.get_draft(self.db,draft));form={}
        for p in preview.products:
            for key in ('brand','search_code','alternate_code','category'):form[f'{key}_{p.row_number}']=getattr(p,key)
        response=self.client.post(f'/drafts/{draft}/confirm',data=form,follow_redirects=False)
        self.assertEqual(response.status_code,303);self.batch=draft;self.products=storage.get_batch(self.db,draft)['products']

    def test_json_is_read_only_and_readiness_independent_from_queue(self):
        pid=self.products[0]['id'];job=jobs.enqueue(self.db,pid,[1,3,4]);url=f'/batches/{self.batch}/progress'
        for _ in range(3):
            result=self.client.get(url);self.assertEqual(result.status_code,200)
            row=result.json()['rows'][0];self.assertEqual(row['status_label'],'В очереди');self.assertEqual(row['readiness_label'],'—')
            self.assertEqual(result.json()['summary']['queued'],1)
        self.assertEqual(len(jobs.list_jobs(self.db,pid)),1)
        jobs.claim_next(self.db)
        job_progress.set_phase(self.db,job,'extraction_photos')
        self.assertEqual(self.client.get(url).json()['rows'][0]['progress_label'],'Фотографии')
        jobs.finish(self.db,job,'needs_review','Недостаточно evidence')
        row=self.client.get(url).json()['rows'][0]
        self.assertEqual(row['current_stage'],'completed');self.assertEqual(row['final_status'],'needs_review')
        self.assertEqual(row['readiness_label'],'Не готова')
        self.assertTrue(all(row[k] for k in ('queued_at','started_at','stage_started_at','finished_at')))
        self.assertEqual(self.client.get(url).json()['summary']['completed'],1)
        self.assertEqual(self.client.get('/batches/missing/progress').status_code,404)

    def test_one_table_all_selected_no_lg_duplicate_or_import_warning(self):
        html=self.client.get(f'/batches/{self.batch}').text;soup=BeautifulSoup(html,'html.parser')
        self.assertEqual(len(soup.select('table')),1);self.assertEqual(len(soup.select('[data-product-row]')),2)
        self.assertEqual(len(soup.select('[name="product_ids"][checked]')),2)
        self.assertNotIn('Проверка LG одной кнопкой',html);self.assertNotIn('Требовало проверки',html)
        self.assertNotIn('Обновить прогресс',html);self.assertNotIn('http-equiv="refresh"',html)
        self.assertIn('Скачать Excel',html)
        data={'product_ids':[str(p['id']) for p in self.products],'stages':['1']}
        for _ in range(2):self.assertEqual(self.client.post(f'/batches/{self.batch}/search',data=data,follow_redirects=False).status_code,303)
        self.assertTrue(all(len(jobs.list_jobs(self.db,p['id']))==1 for p in self.products))

    def test_photo_view_and_empty_archive(self):
        pid=self.products[0]['id'];response=self.client.get(f'/products/{pid}/photos')
        self.assertEqual(response.status_code,200);self.assertIn('Скачать выбранные фото',response.text)
        self.assertEqual(self.client.get(f'/products/{pid}/photos.zip').status_code,422)

    def test_excel_gallery_projection_does_not_grow_per_image(self):
        from product_tool import exporter,photo_inventory
        from product_tool.adapters.common import SourceDocument,PhotoCandidate
        pid=self.products[0]['id']
        photos=[PhotoCandidate(url=f'https://www.lg.com/XL7S/{i}.jpg',asset_key=str(i),kind='product_gallery') for i in range(8)]
        jobs.save_source_document(self.db,pid,SourceDocument('lg_kz','LG','https://www.lg.com/kz/XL7S',found_model='XL7S',match_level='full_sku',photo_candidates=photos))
        with patch.object(photo_inventory,'enriched_photos',wraps=photo_inventory.enriched_photos) as projection:
            content=exporter.export_batch(self.db,self.batch)
        self.assertLessEqual(projection.call_count,len(self.products))
        self.assertTrue(content.startswith(b'PK'))

class AccessAndIdentityTests(unittest.TestCase):
    def test_sulpak_one_attempt_even_on_transient_response(self):
        import requests
        class Session:
            headers={}
            calls=0
            def get(self,*a,**kw):
                self.calls+=1
                raise requests.Timeout('bounded synthetic timeout')
        session=Session();doc=SulpakAdapter(session,clock=lambda:0).find_source('P12ED.NSAR + P12ED.USAR',deadline=30)
        self.assertEqual(session.calls,1);self.assertTrue(doc.error)

    def test_expired_other_product_challenge_keeps_history_without_host_stop(self):
        from datetime import datetime,timedelta,timezone
        from product_tool.adapters import access_stop
        now=datetime.now(timezone.utc)
        event=access_stop.stop_event('https://www.sulpak.kz/g/other',access_stop.CHALLENGE,at=now-timedelta(minutes=31),source_session='old')
        history=[event];self.assertEqual(access_stop.active_stops(history,now=now),{})
        self.assertEqual(len(history),1);self.assertEqual(history[0]['source_session'],'old')

    def test_optional_comment_captcha_is_not_access_challenge(self):
        html='<h1>LG P12ED</h1>'+('<p>Specifications and ordinary product information</p>'*8)+'<form class="product-review-comments"><div class="g-recaptcha"></div></form><script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script>'
        self.assertFalse(looks_like_challenge('https://www.sulpak.kz/g/model',html,200))
        self.assertNotEqual(classify_protection(html,http_status=200).status.value,'challenge_confirmed')
        for gate in ('<form id="challenge-form"><div class="g-recaptcha"></div></form>','<h1>Verify you are human</h1><div class="g-recaptcha"></div>'):
            self.assertTrue(looks_like_challenge('https://www.sulpak.kz/g/model',gate,200))
            self.assertEqual(classify_protection(gate,http_status=200).status.value,'challenge_confirmed')
        self.assertTrue(looks_like_challenge('https://site.test','<body class="reviews"><form id="verify-human"><div class="g-recaptcha"></div></form></body>',200))

    def test_kit_url_is_not_identity_but_product_sku_can_be(self):
        adapter=SulpakAdapter();kit='P12ED.NSAR + P12ED.USAR';url='https://www.sulpak.kz/g/p12ednsar_p12edusar'
        body='<h1>LG P12ED</h1><link rel="canonical" href="'+url+'"><script type="application/ld+json">'+json.dumps({'@type':'Product','name':'LG P12ED','url':url,'image':url+'.jpg'})+'</script>'
        doc=adapter.parse_page(kit,url,body);self.assertEqual(doc.match_level,'unknown');self.assertFalse(doc.attributes or doc.photo_candidates)
        body+='<script type="application/ld+json">'+json.dumps({'@type':'Product','sku':kit})+'</script>'
        self.assertEqual(adapter.parse_page(kit,url,body).match_level,'full_sku')

class ArchiveTests(unittest.TestCase):
    def test_local_photo_serves_verified_bytes_and_rejects_cross_product_id(self):
        from product_tool import photo_content
        with TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/'official_images';directory.mkdir();data=b'previously verified image';digest=hashlib.sha256(data).hexdigest();file=directory/(digest+'.img');file.write_bytes(data)
            photo=dict(id=1,source_key='lg_kz',asset_key='a',url='https://www.lg.com/a.png',kind='product_gallery')
            evidence={'entries':{'lg_kz / a / https://www.lg.com/a.png':dict(saved_file=str(file),sha256=digest,format='PNG')}}
            with patch.object(jobs,'get_photo_candidate',return_value=photo),patch.object(card_evidence,'load',return_value=evidence),patch.object(photo_content.photo_metadata,'inspect_saved_photo') as fetch:
                result=photo_content.content(root/'db',1,1);self.assertEqual(result,(data,'image/png'));fetch.assert_not_called()
                for alias in ('JPG','JPEG'):
                    evidence['entries']['lg_kz / a / https://www.lg.com/a.png']['format']=alias
                    self.assertEqual(photo_content.content(root/'db',1,1),(data,'image/jpeg'))
            with patch.object(jobs,'get_photo_candidate',return_value=None):
                with self.assertRaises(ValueError):photo_content.content(root/'db',2,1)

    def test_selected_alias_uses_highest_published_rendition_and_dedupes_bytes(self):
        with TemporaryDirectory() as tmp:
            db=Path(tmp)/'db.sqlite3';directory=Path(tmp)/'official_images';directory.mkdir()
            data=b'verified-image-test-bytes';digest=hashlib.sha256(data).hexdigest();file=directory/(digest+'.img');file.write_bytes(data)
            base=dict(source_key='lg_kz',kind='product_gallery',selected=1,identity_confirmed=True,official_color='',variant_relation='exact',excluded_reason='',sha256=digest,verified_format='PNG',saved_file=str(file),byte_verified=True)
            photos=[dict(base,id=1,asset_key='a',url='https://www.lg.com/a.png?width=100',normalized_asset='https://www.lg.com/a.png',width=100,height=100),dict(base,id=2,asset_key='b',url='https://www.lg.com/a.png?width=1000',normalized_asset='https://www.lg.com/a.png',width=1000,height=1000)]
            with patch.object(jobs,'get_product',return_value={'brand':'LG','model':'../P12ED','search_code':'A/B'}),patch.object(photo_archive.photo_inventory,'enriched_photos',return_value=photos),patch.object(photo_archive.photo_metadata,'inspect_saved_photo') as fetch:
                name,content=photo_archive.archive(db,1);fetch.assert_not_called()
            self.assertNotIn('/',name);self.assertTrue(name.endswith('_photos.zip'))
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                self.assertEqual(len(z.namelist()),1);self.assertEqual(z.read(z.namelist()[0]),data)
            self.assertGreater(photo_archive.quality_rank(photos[1]),photo_archive.quality_rank(photos[0]))

    def test_cache_escape_and_failed_fetch_never_return_zip(self):
        with TemporaryDirectory() as tmp:
            db=Path(tmp)/'db';outside=Path(tmp)/'outside.png';outside.write_bytes(b'x')
            photo=dict(id=1,asset_key='a',url='https://www.lg.com/a.png',normalized_asset='https://www.lg.com/a.png',source_key='lg_kz',kind='product_gallery',selected=1,identity_confirmed=True,saved_file=str(outside),sha256=hashlib.sha256(b'x').hexdigest())
            def denied(*a,**kw):raise ValueError('HTTP 403')
            with patch.object(jobs,'get_product',return_value={'brand':'LG','model':'X','search_code':'X'}),patch.object(photo_archive.photo_inventory,'enriched_photos',return_value=[photo]):
                with self.assertRaisesRegex(ValueError,'HTTP 403'):photo_archive.archive(db,1,inspector=denied)
