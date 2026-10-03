"""Stage 58 generic Bosch identity and grouped extraction boundaries."""
import json
import unittest
from product_tool.adapters.bosch_official import BoschOfficialAdapter, model_query, parse_official_page
from product_tool.adapters.policy_session import PolicyResponse
from product_tool.adapters.common import RawAttribute
from product_tool.adapters.lg_browser_search import BrowserCandidate, BrowserSearchResult
from product_tool.normalization import normalize_fact


def page(code, *, mpn=None):
    product={"@type":"Product","mpn":mpn or code,"gtin":"1234567890123",
             "image":[f"https://media3.bsh-group.com/Product_Shots/1_{code}_def.webp",
                      "https://media3.bsh-group.com/Product_Shots/2_OTHER_def.webp"]}
    groups={"specifications":[{"name":"Размер и вес","specifications":[
        {"name":{"text":"Размеры прибора (мм)"},"value":{"text":"51x592x522"},"unit":"мм"},
        {"name":{"text":"Размеры прибора в упаковке (ВхШхГ)"},"value":{"text":"130x753x610"},"unit":"мм"},
        {"name":{"text":"Размеры нагревательных элементов"},"value":{"text":"2 x (18,0 cm Ø), 1 x (21,0 cm Ø)"}}]},
        {"name":"Особенности","specifications":[
        {"name":{"text":"Home Connect"},"value":{"text":"specifications.translatedBoolean.no"}}]}],
        "documents":[{"titleKey":"user-manuals","url":"https://media3.bsh-group.com/Documents/manual.pdf"},
                     {"titleKey":"installation-instruction","url":"https://media3.bsh-group.com/Documents/manual.pdf"}]}
    flight=json.dumps('0:'+json.dumps(groups,ensure_ascii=False),ensure_ascii=False)
    return ('<html><script type="application/ld+json">'+json.dumps(product)+'</script>'
            '<script>self.__next_f.push([1,'+flight+'])</script></html>')


class FakeHttp:
    def __init__(self,pages):self.pages=pages;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(url)
        return PolicyResponse(url,200,self.pages[url],'text/html') if url in self.pages else PolicyResponse(url,404,'','text/html')


class BoschOfficialStage58(unittest.TestCase):
    def test_exact_page_extracts_sections_boolean_documents_and_model_photos(self):
        url='https://www.bosch-home.com/kz/ru/product/ABC123'
        doc,report=parse_official_page(page('ABC123'),url,'ABC123')
        self.assertEqual(doc.match_level,'full_sku')
        self.assertEqual(len(doc.photos),1)
        self.assertEqual(len([x for x in doc.photo_candidates if x.kind == 'excluded']),1)
        self.assertEqual(report['photo_excluded'][0]['reason'],'not_model_bound')
        self.assertIn(('Особенности','Home Connect','Нет'),[(x.section,x.name,x.value) for x in doc.attributes])
        self.assertEqual({x['type'] for x in report['documents_typed']},{'User manual','Installation instructions'})
        compact=normalize_fact(RawAttribute(
            'Размеры продукта (ШxВxГмм)','285 x 305 x 445'))
        self.assertEqual(compact.normalized_value,'w=285;h=305;d=445')
        ambiguous=next(x for x in doc.attributes if x.name=='Размеры прибора (мм)')
        self.assertEqual(normalize_fact(ambiguous).normalized_value,'51x592x522 мм')
        packaged=next(x for x in doc.attributes if 'упаковке' in x.name)
        self.assertEqual(normalize_fact(packaged).normalized_value,'w=753;h=130;d=610')
        heater=next(x for x in doc.attributes if 'нагревательных' in x.name)
        self.assertEqual(normalize_fact(heater).normalized_name,'heating_element_sizes')

    def test_suffix_and_revision_are_base_relation_only(self):
        url='https://www.bosch-home.com/kz/ru/product/ABC123'
        for article in ('ABC123_KZ','ABC123_1','ABC123/01'):
            with self.subTest(article=article):
                self.assertEqual(model_query(article),('ABC123','base_model'))
                doc,_=parse_official_page(page('ABC123'),url,article)
                self.assertEqual(doc.match_level,'base_model')
                self.assertFalse(doc.attributes)
                self.assertFalse(doc.photos)
                self.assertTrue(all(x.kind == 'excluded' for x in doc.photo_candidates))

    def test_sitemap_candidate_is_content_validated_after_wrong_first_result(self):
        wrong='https://www.bosch-home.com/kz/ru/product/ABC123'
        right='https://www.bosch-home.com/eg/en/product/ABC123'
        sitemap='https://www.bosch-home.com/eg/en/sitemap.xml'
        xml=f'<urlset><url><loc>{right}</loc></url></urlset>'
        http=FakeHttp({wrong:page('ABC123',mpn='OTHER'),right:page('ABC123'),sitemap:xml})
        events=[]
        adapter=BoschOfficialAdapter(http=http,clock=lambda:0.0,trace_callback=events.append)
        doc=adapter.find_source('ABC123',category='test',deadline=100.0)
        self.assertEqual(doc.url,right)
        self.assertEqual(doc.match_level,'full_sku')
        self.assertTrue(any(x.get('decision')=='rejected' and x.get('identity')=='mismatch' for x in events))
        self.assertTrue(any(x.get('provider')=='bosch_sitemap' and x.get('decision')=='accepted' for x in events))


    def test_external_browser_runs_after_sitemap_miss_and_rejects_wrong_first_page(self):
        requested='ABC123'
        wrong=f'https://www.bosch-home.com/sa/en/mkt-product/wrong/{requested}'
        right=f'https://www.bosch-home.com/sa/en/mkt-product/appliances/{requested}'
        http=FakeHttp({wrong:page(requested,mpn='OTHER'),right:page(requested)})
        class FakeSearch:
            def __init__(self):self.calls=[]
            def search_provider(self,provider,query):
                self.calls.append((provider,query))
                return BrowserSearchResult('global',query,'candidates_found',(
                    BrowserCandidate(wrong,'product',position=1,provider=provider),
                    BrowserCandidate(right,'product',position=2,provider=provider)))
        browser=FakeSearch();events=[]
        adapter=BoschOfficialAdapter(http=http,clock=lambda:0.0,
                                     browser_search=browser,trace_callback=events.append)
        doc=adapter.find_source(requested,category='test',deadline=100.0)
        self.assertEqual(doc.url,right)
        self.assertEqual(doc.match_level,'full_sku')
        self.assertEqual(browser.calls[0][0],'google')
        self.assertTrue(any(x.get('provider')=='bosch_sitemap' for x in events))
        self.assertLess(next(i for i,x in enumerate(events) if x.get('provider')=='bosch_sitemap'),
                        next(i for i,x in enumerate(events) if x.get('provider')=='google_browser'))
        self.assertTrue(any(x.get('url')==wrong and x.get('identity')=='mismatch' for x in events))



if __name__=='__main__':unittest.main()
