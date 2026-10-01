(policy) => {
    // Only semantic values leave this function; no element HTML is serialized.
    const bytes = x => new TextEncoder().encode(JSON.stringify(x)).length;
    const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden],[aria-hidden="true"]');
    const excluded = e => !!e.closest('nav,header,footer,aside,[role="navigation"]');
    const secret = /csrf|xsrf|token|session|password|auth|cookie|nonce|signature|secret/i;
    const url = (value, observedSearchResult=false) => {
        try {
            const u = new URL(value, location.href);
            if (!['http:','https:'].includes(u.protocol) || u.username || u.password || (u.port && !['80','443'].includes(u.port))) return '';
            if (!observedSearchResult && !policy.allowed_hosts.some(h => u.hostname === h || u.hostname.endsWith('.'+h))) return '';
            if (secret.test(u.pathname) || /[a-f0-9]{32,}/i.test(u.pathname)) return '';
            for (const k of [...u.searchParams.keys()]) if (!['q','query','search','sku','mpn','model','productcode'].includes(k.toLowerCase())) u.searchParams.delete(k);
            u.hash = '';
            return u.href;
        } catch { return ''; }
    };
    const safeText = value => String(value || '').replace(/\s+/g,' ').trim().slice(0,300);
    const projection = {projection_version:'2',url:url(location.href),title:safeText(document.title),inputs:[],fragments:[],protection:false,cookie_dialog:{visible:false},metrics:{dom_elements:document.getElementsByTagName('*').length,links_examined:0,fragment_count:0,projection_bytes:0}};
    let overflow=false;
    const add = fragment => {
        if (overflow) return;
        if (bytes(fragment)>policy.max_fragment_bytes || projection.fragments.length>=policy.max_projection_fragments) {overflow=true;return;}
        projection.fragments.push(fragment);
        if (bytes(projection)>policy.max_projection_bytes) overflow=true;
    };
    const searchWord = /\b(search|suche)\b|\u043f\u043e\u0438\u0441\u043a|\u0456\u0437\u0434\u0435\u0443/i;
    if (policy.render_mode !== 'render_existing_search_result') Array.from(document.querySelectorAll('input,textarea,[role="searchbox"]')).forEach((e,index) => {
        if (!visible(e) || e.disabled || e.type==='hidden') return;
        const f=e.closest('form');
        const label=safeText((e.getAttribute('aria-label')||'')+' '+Array.from(e.labels||[]).map(l=>safeText(l.textContent)).join(' '));
        const reason=e.type==='search'?'input_type_search':e.getAttribute('role')==='searchbox'?'role_searchbox':searchWord.test(label)?'explicit_search_label':f?.getAttribute('role')==='search'?'form_role_search':'';
        if (!reason) return;
        const action=url(f?.getAttribute('action')||location.href);
        const context=f?((f.getAttribute('action')||'')+' '+f.id+' '+f.className):'';
        const password=!!f?.querySelector('input[type="password"]'),file=!!f?.querySelector('input[type="file"]');
        const security=!!f && Array.from(f.querySelectorAll('input,textarea')).some(x=>secret.test(x.name));
        const method=f?(f.getAttribute('method')||'GET').toUpperCase():'Enter';
        const unsafe=secret.test(f?.getAttribute('action')||'') || !action || !['GET','POST','Enter'].includes(method) || password || file || security || secret.test(e.name) || ['password','file','email'].includes(e.type) || /login|register|account|cart|checkout|contact|support|newsletter/i.test(context);
        const a=action?new URL(action):null;
        const descriptor={index,type:e.type||'',role:e.getAttribute('role')==='searchbox'?'searchbox':'',label:searchWord.test(label)?'Search':'',form_present:!!f,action_host:a?.hostname||'',action_path:a?.pathname||'',form_action:action,submit_method:method,visible:true,password_input:password,file_input:file,security_input:security,unsafe,discovery_method:reason,selector_description:reason,originating_url:url(location.href)};
        if (bytes(descriptor)>policy.max_fragment_bytes || projection.inputs.length>=20) overflow=true;
        else projection.inputs.push(descriptor);
    });
    for (const e of document.querySelectorAll('[role="dialog"],#onetrust-banner-sdk,.cookie-banner')) {
        if (visible(e) && /cookie/i.test((e.textContent||'').slice(0,5000))) projection.cookie_dialog.visible=true;
    }
    for (const e of document.querySelectorAll('iframe[src*="captcha"],iframe[src*="challenge"],.g-recaptcha,.h-captcha,#challenge-form')) if (visible(e)) projection.protection=true;
    // Inspect text locally, returning only a boolean. Never copy unrelated body text.
    const walker=document.createTreeWalker(document.body||document.documentElement,NodeFilter.SHOW_TEXT);
    let textNode,seen=0;
    while ((textNode=walker.nextNode()) && seen++<20000) {
        const e=textNode.parentElement;
        if (e && !e.closest('script,style,noscript,svg') && /verify (?:that )?you are human|access denied|unusual traffic|checking your browser|bots use DuckDuckGo too|complete the following challenge/i.test(textNode.nodeValue.slice(0,2000)) && visible(e)) {projection.protection=true;break;}
    }
    if (policy.inspect_only) return {protection:projection.protection};
    const cardPattern=/(?:^|[ _-])(?:product-card|card-product|product-item|search-result|result-item)(?:[ _-]|$)/i;
    for (const a of document.querySelectorAll('a[href]')) {
        if (overflow) break;
        projection.metrics.links_examined++;
        if (!visible(a) || excluded(a) || a.hasAttribute('download')) continue;
        const searchProvider=/(^|\.)(google\.com|bing\.com|duckduckgo\.com)$/.test(location.hostname);
        const resultContainer=searchProvider ? a.closest('li.b_algo, article[data-testid="result"], .result, .web-result') : null;
        const primaryResultLink=resultContainer?.querySelector('h2 a, h3 a, a[data-testid="result-title-a"], a.result__a, a[href]');
        if (primaryResultLink && primaryResultLink!==a) continue;
        const href=url(a.getAttribute('href'), !!resultContainer);if (!href) continue;
        let card=null,node=a;
        for(let i=0;i<4 && node && !['BODY','MAIN','HTML'].includes(node.tagName);i++,node=node.parentElement) {
            if (cardPattern.test(node.className||'') || node.hasAttribute('data-product-id')) {card=node;break;}
        }
        const title=safeText(a.innerText || a.getAttribute('title') || (card?.querySelector('h2,h3,h4')?.textContent));
        const path=new URL(href).pathname;
        const exact=(policy.queries||[]).some(q=>title.toUpperCase().includes(q.toUpperCase())||path.toUpperCase().includes(q.toUpperCase()));
        // Generic external search results may point at a base-model URL while
        // the exact article is printed only in the result card. The URL remains
        // a candidate; the opened manufacturer's page decides identity.
        const targetHost=new URL(href).hostname;
        const externalResult=searchProvider &&
            (location.hostname.endsWith('google.com') ?
             (policy.search_result_hosts||[]).some(h=>targetHost===h||targetHost.endsWith('.'+h)) :
             !!resultContainer);
        if (!card && !exact && !externalResult && !/\/(?:products?|p|mkt-product)\/[^/]+/i.test(path)) continue;
        let snippet='';
        if (externalResult) {
            let parent=resultContainer||a.parentElement;
            for(let depth=0;depth<5 && parent;depth++,parent=parent.parentElement) {
                const nearby=safeText(parent.innerText||'');
                if(nearby.length>title.length+15 && nearby.length<600) {
                    snippet=safeText(nearby.replace(title,'').trim());
                    break;
                }
            }
        }
        add({type:'result_link',url:href,title,snippet,local_card:!!card});
    }
    const scalarKeys=['name','model','sku','mpn','color','size','storage','ram','revision','serviceIndex','region','configuration','productGroupID'];
    function clean(value,depth=0) {
        if (depth>8 || value==null) return null;
        if(Array.isArray(value)) {if(value.length>100)overflow=true;return value.slice(0,100).map(x=>clean(x,depth+1)).filter(Boolean);}
        if(typeof value!=='object') return null;
        const out={};
        if(['Product','ItemList','ListItem'].includes(value['@type'])) out['@type']=value['@type'];
        for(const k of scalarKeys) if(['string','number'].includes(typeof value[k])) out[k]=safeText(value[k]);
        if(typeof value.url==='string' && url(value.url)) out.url=url(value.url);
        for(const k of ['itemListElement','item','@graph']) if(value[k]) out[k]=clean(value[k],depth+1);
        return out;
    }
    function visit(value,depth=0) {
        if(depth>8 || overflow || !value) return;
        if(Array.isArray(value)){for(const x of value.slice(0,100))visit(x,depth+1);return;}
        if(typeof value!=='object')return;
        if(['Product','ItemList'].includes(value['@type'])) {add({type:'json_ld',data:clean(value)});return;}
        visit(value['@graph'],depth+1);
    }
    for(const script of document.querySelectorAll('script[type="application/ld+json"]')) {
        // Source scripts have an independent bounded parse limit.
        if(script.textContent.length>200000) {if(/"@type"\s*:\s*(?:\[\s*)?"(?:Product|ItemList)"/.test(script.textContent))overflow=true;continue;}
        try {visit(JSON.parse(script.textContent));} catch {}
    }
    for(const root of document.querySelectorAll('[itemscope][itemtype]')) {
        if(!/(?:https?:\/\/schema.org\/Product)(?:\s|$)/i.test(root.getAttribute('itemtype')))continue;
        const values={};
        for(const e of root.querySelectorAll('[itemprop]')) {
            if(e.parentElement.closest('[itemscope]')!==root)continue;
            for(const k of e.getAttribute('itemprop').split(/\s+/)) if(scalarKeys.includes(k)) values[k]=safeText(e.getAttribute('content')||e.textContent);
        }
        add({type:'microdata',data:values});
    }
    projection.metrics.fragment_count=projection.fragments.length;
    projection.metrics.projection_bytes=bytes(projection);
    if(overflow || bytes(projection)>policy.max_projection_bytes) return {projection_version:'2',overflow:true,metrics:projection.metrics};
    return projection;
}
