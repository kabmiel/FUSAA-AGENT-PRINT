"""Small browser smoke test for the standalone billing workspace.

The API is mocked so navigation and responsive layout can be checked without
starting a local server or touching production data.
"""
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

WEB = Path(__file__).parents[1] / "backend" / "app" / "web"

HTML = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;min-width:320px;background:#0b1727;color:#eef6ff;font:15px Arial,sans-serif}
.workspace{display:grid;grid-template-columns:230px minmax(0,1fr)}.sidebar{min-height:100vh;background:#102035}
main{max-width:1200px;width:100%;padding:24px}.view{display:none}.view.active{display:block}
.view-head{display:flex;justify-content:space-between}.stats{display:grid}button{width:100%;padding:11px;border:0;border-radius:10px;background:#2385e9;color:white;cursor:pointer}
input,select,textarea{width:100%;padding:10px;border:1px solid #345;border-radius:10px}h1,h2{margin-top:0}
</style><link rel="stylesheet" href="/billing-workspace.css"></head><body>
<div class="workspace"><aside class="sidebar">Menu FUSAA</aside><main>
<section id="dashboard" class="view active"><div class="view-head"><h1>Accueil</h1></div><div id="stats" class="stats"></div></section>
<section id="billing" class="view"></section></main></div>
<script>
let org="o",token="test";function loadBilling(){};
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money=value=>Number(value||0).toLocaleString("fr-FR")+" FCFA";
function tell(value){window.lastNotice=value}
function showFusaaOperation(){return null}async function hideFusaaOperation(){}
function selectView(view){document.querySelectorAll(".view").forEach(item=>item.classList.toggle("active",item.id===view));if(view==="billing")loadBilling()}
function openBillingAssistant(){}function openBillingInvoice(){}function downloadBillingInvoice(){}
async function api(path,options={}){
 if(path.includes("/billing/import/analyze"))return {kind:"categories",filename:"facturation_categories.csv",rows:2,delimiter:"point-virgule",headers:["categorie","description"],samples:[{line:2,name:"Bureautique"}],warning:""};
 if(path.includes("/billing/import/execute"))return {kind:"categories",filename:"facturation_categories.csv",created:2,skipped:0,errors:[],warnings:[]};
 if(path.includes("/billing/assistant"))return {title:"Brouillon de proforma",answer:"Brouillon prêt.",draft:{billing_header_id:"h",customer_id:"c",document_type:"PROFORMA",subject:"Proforma",notes:"",total_amount:7000,lines:[{product_id:"p",description:"Ramette A4",quantity:2,unit_amount:3500,unit:"paquet"}]}};
 if(path==="/api/v1/customers"&&options.method==="POST")return {id:"new-c",name:"Nouveau client",phone:"90000000",email:"client@example.test",address:"Zinder",notes:"Test"};
 if(path.includes("/billing/headers")&&options.method==="POST")return {id:"new-h",company_name:"Nouvelle entête",is_default:false,document_style:"standard",tax_enabled:false,tax_rate:19,isb_enabled:false,isb_rate:3};
 if(path.includes("/billing/dashboard"))return {invoices:0,invoiced_xof:0,billing_products:1,shop_products:0,customers:1,outstanding_xof:0,headers:1,recent:[]};
 if(path.includes("/billing/headers"))return [{id:"h",company_name:"FUSAA",is_default:true,document_style:"standard",tax_enabled:false,tax_rate:19,isb_enabled:false,isb_rate:3}];
 if(path.includes("/customers"))return [{id:"c",name:"Client exemple"}];
 if(path.includes("/billing/catalog/page"))return {items:[{id:"p",name:"Ramette A4",price_xof:3500,unit:"paquet",source:"FACTURATION",stock_quantity:2,stock_minimum:1,cost_xof:0}],page:1,total:1,has_more:false};
 return [];
}
</script><script src="/billing-workspace.js"></script></body></html>"""


def test_documents_direct_page_compact_and_debounced_search_ignores_stale_results(tmp_path):
    extra="""
window.documentRequests=[];window.documentDialogs=0;
const originalShowModal=HTMLDialogElement.prototype.showModal;
HTMLDialogElement.prototype.showModal=function(){window.documentDialogs++;return originalShowModal.call(this)};
const documentsApi=api;
api=async function(path,options={}){
 if(path.includes('/billing/invoices?')){
  const params=new URL(path,'http://documents.test').searchParams,q=params.get('q')||'',number=Number(params.get('page'));
  const call={q,page:number,page_size:Number(params.get('page_size')),aborted:false};window.documentRequests.push(call);
  options.signal?.addEventListener('abort',()=>call.aborted=true);
  await new Promise(resolve=>setTimeout(resolve,q==='slow'?900:90));
  return Array.from({length:q==='fast'?1:12},(_,i)=>({id:'doc-'+i,number:(q==='fast'?'FAST':'INV')+'-'+number+'-'+i,
    customer_name:'Client exemple',document_type:'INVOICE',document_style:'standard',total_amount:21000,paid_amount:0,
    status:'PENDING_PAYMENT',created_at:'2026-10-22T12:00:00Z'}));
 }
 return documentsApi(path,options);
};
"""
    html=HTML.replace('</script><script src="/billing-workspace.js">',extra+'</script><script src="/billing-workspace.js">')
    with playwright.sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        def serve(route):
            path=route.request.url.split('?',1)[0]
            if path.endswith('/admin'):route.fulfill(content_type='text/html; charset=utf-8',body=html)
            elif path.endswith('.js'):route.fulfill(content_type='application/javascript',body=(WEB/'billing-workspace.js').read_text(encoding='utf-8'))
            elif path.endswith('.css'):route.fulfill(content_type='text/css',body=(WEB/'billing-workspace.css').read_text(encoding='utf-8'))
            else:route.fulfill(status=404)
        page.route('**/*',serve);page.goto('http://documents.test/admin')
        page.locator('#billingHomeBadge').click();page.locator('[data-billtab="documents"]').click()
        search=page.get_by_role('searchbox',name='Rechercher un document');search.wait_for()
        page.locator('#billingDocumentsList tbody tr').first.wait_for()
        assert page.evaluate('window.documentDialogs')==0
        assert page.locator('#billingGlassDialog[open]').count()==0
        assert page.locator('.billing-documents-table .billing-type-badge').count()==0
        assert page.locator('.billing-documents-table .billing-row-type select').count()==12
        assert page.locator('.billing-documents-table tbody tr').first.evaluate('(node)=>node.getBoundingClientRect().height')<58
        assert page.evaluate('window.documentRequests.length')==1
        search.press_sequentially('client',delay=20)
        page.wait_for_function('window.documentRequests.length===2')
        page.wait_for_function("document.getElementById('billingDocumentsStatus').dataset.loading==='false'")
        assert search.input_value()=='client'
        page.locator('#billingDocumentsNext').click();page.wait_for_function('window.documentRequests.length===3')
        page.wait_for_function("document.getElementById('billingDocumentsPageLabel').textContent==='Page 2'")
        search.fill('');page.wait_for_function('window.documentRequests.length===4')
        page.wait_for_function("document.getElementById('billingDocumentsPageLabel').textContent==='Page 1'")
        search.fill('slow');page.wait_for_function("window.documentRequests.some(x=>x.q==='slow')")
        search.fill('fast');page.wait_for_function("document.getElementById('billingDocumentsList').textContent.includes('FAST-1-0')")
        page.wait_for_timeout(950)
        assert page.locator('#billingDocumentsList tbody tr').count()==1
        assert 'FAST-1-0' in page.locator('#billingDocumentsList').inner_text()
        calls=page.evaluate('window.documentRequests')
        assert len(calls)==6 and next(x for x in calls if x['q']=='slow')['aborted']
        assert all(x['page_size']==12 for x in calls)
        assert calls[2]['q']=='client' and calls[2]['page']==2
        page.screenshot(path=str(tmp_path/'documents-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(tmp_path/'documents-mobile.png'),full_page=True)
        assert not errors
        browser.close()


def test_document_conversion_requires_confirmation_then_opens_credit_account():
    extra="""
function newId(){return 'conversion-ui-00001'}
const creditApi=api;window.creditConversions=0;
api=async function(path,options={}){
 if(path.includes('/credit-accounts/from-invoice/')){window.creditConversions++;window.creditPayload=JSON.parse(options.body);return {customer_id:'c',balance:250,already_converted:false}}
 if(path.includes('/credit-accounts/c'))return {customer_id:'c',customer_name:'Client exemple',balance:250,total_purchases:300,total_repaid:50,archived:false,operations:[],page:1,operation_count:0,has_more:false};
 if(path.includes('/billing/invoices/i'))return {id:'i',number:'INV-TEST',status:'PARTIALLY_PAID',document_type:'INVOICE',total_amount:300,paid_amount:50,balance_amount:250,customer:{id:'c',name:'Client exemple'}};
 if(path.includes('/billing/invoices?'))return [{id:'i',number:'INV-TEST',status:'PARTIALLY_PAID',document_type:'INVOICE',total_amount:300,paid_amount:50,customer_name:'Client exemple'},{id:'q',number:'QUOTE-TEST',status:'DRAFT',document_type:'QUOTE',total_amount:300,paid_amount:0}];
 return creditApi(path,options);
};
"""
    html=HTML.replace('</script><script src="/billing-workspace.js">',extra+'</script><script src="/billing-workspace.js">')
    with playwright.sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':390,'height':844});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        def serve(route):
            path=route.request.url.split('?',1)[0]
            if path.endswith('/admin'):route.fulfill(content_type='text/html; charset=utf-8',body=html)
            elif path.endswith('.js'):route.fulfill(content_type='application/javascript',body=(WEB/'billing-workspace.js').read_text(encoding='utf-8'))
            elif path.endswith('.css'):route.fulfill(content_type='text/css',body=(WEB/'billing-workspace.css').read_text(encoding='utf-8'))
            else:route.fulfill(status=404)
        page.route('**/*',serve);page.goto('http://credit-ui.test/admin')
        page.locator('#billingHomeBadge').click();page.locator('[data-billtab="documents"]').click()
        action=page.get_by_role('button',name='Mettre cette facture à crédit INV-TEST',exact=True)
        action.wait_for();assert page.get_by_role('button',name='Mettre cette facture à crédit QUOTE-TEST',exact=True).count()==0
        action.click();dialog=page.locator('#billingInvoiceCreditDialog')
        dialog.get_by_role('button',name='Confirmer la mise à crédit').wait_for()
        assert page.evaluate('window.creditConversions')==0
        assert '250' in dialog.inner_text() and '50' in dialog.inner_text()
        assert dialog.evaluate('(node)=>node.getBoundingClientRect().width')<=390
        dialog.get_by_role('button',name='Confirmer la mise à crédit').click()
        assert page.evaluate('window.creditConversions')==0
        dialog.locator('[name="confirmation"]').check()
        dialog.get_by_role('button',name='Confirmer la mise à crédit').click()
        page.wait_for_function('window.creditConversions===1')
        page.get_by_role('heading',name='Client exemple',exact=True).wait_for()
        assert page.locator('#billingInvoiceCreditDialog').count()==0
        assert page.evaluate('window.creditPayload.expected_balance')==250
        assert page.evaluate('window.creditPayload.customer_id')=='c'
        assert not errors
        browser.close()


def test_invoice_header_has_search_inside_selectors_and_keeps_context(tmp_path):
    extra = """
const selectorApi=api;
window.assistantCalls=0;
api=async function(path,options={}){
 if(path.includes('/billing/assistant'))window.assistantCalls++;
 if(path.includes('/billing/headers')&&!options.method)return [
  {id:'h',company_name:'FUSAA',is_default:true},
  {id:'h2',company_name:'Deuxième entreprise'}];
 if(path.includes('/customers')&&!options.method)return [
  {id:'c',name:'Client exemple'}, {id:'c2',name:'Deuxième client'}];
 return selectorApi(path,options);
};
"""
    html=HTML.replace('</script><script src="/billing-workspace.js">',extra+'</script><script src="/billing-workspace.js">')
    with playwright.sync_playwright() as driver:
        try:
            browser=driver.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Chromium indisponible : {exc}")
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.set_default_timeout(5000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        def serve(route):
            path=route.request.url.split('?',1)[0]
            if path.endswith('/admin'): route.fulfill(content_type='text/html; charset=utf-8',body=html)
            elif path.endswith('.js'): route.fulfill(content_type='application/javascript',body=(WEB/'billing-workspace.js').read_text(encoding='utf-8'))
            elif path.endswith('.css'): route.fulfill(content_type='text/css',body=(WEB/'billing-workspace.css').read_text(encoding='utf-8'))
            else: route.fulfill(status=404)
        page.route('**/*',serve);page.goto('http://selector-ui.test/admin')
        page.locator('#billingHomeBadge').click()
        page.locator('[data-billtab="new"]').click()
        page.locator('#billingNewHeader option[value="h2"]').wait_for(state='attached')
        panel=page.locator('.billing-editor-header')
        assert panel.count()==1
        assert page.locator('#billingWorkspaceContent>.billing-hero').count()==0
        assert panel.get_by_role('button',name='Modifier',exact=True).count()==0
        assert page.locator('#billingAiPrompt').count()==0
        assert not page.locator('#billingHeaderSearch').is_visible()
        page.locator('#billingHeaderSearchToggle').click()
        page.locator('#billingHeaderSearch').fill('deuxieme')
        assert page.locator('#billingHeaderSearchOptions [role="option"]').count()==1
        page.locator('#billingHeaderSearch').press('Enter')
        assert page.locator('#billingNewHeader').input_value()=='h2'
        assert page.locator('#billingHeaderSearchToggle').inner_text()=='Deuxième entreprise'
        page.locator('#billingCustomerSearchToggle').click()
        page.locator('#billingCustomerSearch').fill('deuxième')
        page.locator('#billingCustomerSearch').press('ArrowDown')
        page.keyboard.press('Enter')
        assert page.locator('#billingNewCustomer').input_value()=='c2'
        page.get_by_role('button',name='Ouvrir le chat IA',exact=True).click()
        assert page.locator('#billingFacturationAssistantDialog').is_visible()
        assert 'Deuxième entreprise' in page.locator('#billingAssistantContext').inner_text()
        assert 'Deuxième client' in page.locator('#billingAssistantContext').inner_text()
        assert page.evaluate('window.assistantCalls')==0
        page.locator('#billingFacturationAssistantDialog button[aria-label="Fermer"]').click()
        page.locator('#billingAddHeader').click()
        page.locator('#billingHeaderQuickDialog [name="company_name"]').fill('Nouvelle entête')
        page.locator('#billingHeaderQuickDialog form').evaluate('form=>form.requestSubmit()')
        page.wait_for_function("document.getElementById('billingNewHeader').value==='new-h'")
        assert page.locator('#billingHeaderSearchToggle').inner_text()=='Nouvelle entête'
        page.locator('#billingAddCustomer').click()
        page.locator('#billingCustomerDialog [name="name"]').fill('Nouveau client')
        page.locator('#billingCustomerDialog form').evaluate('form=>form.requestSubmit()')
        page.wait_for_function("document.getElementById('billingNewCustomer').value==='new-c'")
        assert page.locator('#billingCustomerSearchToggle').inner_text()=='Nouveau client'
        for width in (1440,390,320):
            page.set_viewport_size({'width':width,'height':1000})
            page.locator('#billingHeaderSearchToggle').click()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('#billingHeaderSearch').press('Escape')
            panel.screenshot(path=str(tmp_path/f'selector-{width}.png'))
        page.evaluate("""async()=>{
          billingState.editingInvoice={id:'edit',billing_header_id:'h',document_type:'RECEIPT',customer:{id:'c'},issued_on:'2026-10-07',lines:[{description:'Produit conservé',quantity:2,unit_amount:100}]};
          billingState.documentType='RECEIPT';await billingNew();
        }""")
        assert page.locator('#billingHeaderSearchToggle').inner_text()=='FUSAA'
        assert page.locator('#billingCustomerSearchToggle').inner_text()=='Client exemple'
        assert page.locator('.bill-designation').input_value()=='Produit conservé'
        assert panel.get_by_role('button',name='Annuler',exact=True).is_visible()
        page.evaluate("async()=>{billingState.editingInvoice=null;billingState.creditMode=true;billingState.creditCustomerId='c';await billingNew()}")
        assert panel.get_by_role('heading',name='Nouvel achat à crédit').is_visible()
        assert page.locator('#billingCreditInitial').is_visible()
        assert not errors
        browser.close()


def test_compact_product_catalog_is_single_line_and_mobile_safe(tmp_path):
    extra = """
const productLayoutApi=api;
window.catalogReads=0;
api=async function(path,options={}){
 if(path.startsWith('/api/v1/billing/products?')){
  window.catalogReads++;
  return {items:[
   {id:'p',name:'Carton de papier A4 80 g/m² et fournitures scolaires de grande qualité',price_xof:1234567,unit:'pièce',source:'FACTURATION',stock_quantity:7},
   {id:'s',name:'Ramette A4',price_xof:3500,unit:'paquet',source:'BOUTIQUE',stock_quantity:5}
  ]};
 }
 return productLayoutApi(path,options);
};
"""
    html = HTML.replace('</script><script src="/billing-workspace.js">', extra + '</script><script src="/billing-workspace.js">')
    with playwright.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Chromium indisponible : {exc}")
        page = browser.new_page(viewport={"width":1440,"height":1000})
        page.set_default_timeout(5000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        def serve(route):
            path=route.request.url.split('?',1)[0]
            if path.endswith('/admin'): route.fulfill(content_type='text/html; charset=utf-8',body=html)
            elif path.endswith('.js'): route.fulfill(content_type='application/javascript',body=(WEB/'billing-workspace.js').read_text(encoding='utf-8'))
            elif path.endswith('.css'): route.fulfill(content_type='text/css',body=(WEB/'billing-workspace.css').read_text(encoding='utf-8'))
            else: route.fulfill(status=404)
        page.route('**/*',serve)
        page.goto('http://catalog-ui.test/admin')
        page.locator('#billingHomeBadge').click()
        page.locator('[data-billtab="new"]').click()
        page.locator('#billingNewCatalog tbody tr').nth(1).wait_for()
        table=page.locator('#billingNewCatalog table')
        assert table.locator('th').all_text_contents()==['Produit','Prix unitaire','Unité','Actions']
        assert table.locator('small').count()==0
        assert table.locator('tbody tr').first.get_by_role('button',name='Modifier le produit').count()==1
        assert table.locator('tbody tr').nth(1).get_by_role('button').count()==1
        for width in (1440,390,320):
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert table.locator('tbody tr').first.evaluate('row=>row.getBoundingClientRect().height')<=41
            assert table.locator('td').nth(1).evaluate('td=>getComputedStyle(td).whiteSpace')=='nowrap'
            assert table.locator('td').nth(1).evaluate('td=>td.scrollWidth<=td.clientWidth+1')
            assert table.locator('.billing-catalog-name').first.evaluate('el=>getComputedStyle(el).whiteSpace')=='nowrap'
            assert table.locator('.billing-catalog-name').first.get_attribute('title').startswith('Carton de papier')
            page.locator('.billing-catalog-panel').screenshot(path=str(tmp_path/f'catalog-{width}.png'))
        table.get_by_role('button',name='Ajouter à la facture').first.click()
        assert page.locator('.bill-designation').last.input_value().startswith('Carton de papier')
        page.locator('[data-billtab="products"]').click()
        page.locator('.billing-products-table tbody tr').nth(1).wait_for()
        assert page.locator('.billing-products-table th').all_text_contents()==['Produit','Prix unitaire','Stock','Actions']
        assert page.evaluate('window.catalogReads')==1
        assert not errors
        browser.close()


def test_compact_invoice_lines_reorder_without_reloading_and_save_in_that_order():
    extra = """
const originalLineApi=api;
api=async function(path,options={}){
 if(path==='/api/v1/billing/documents'&&options.method==='POST'){
  window.sentLines=JSON.parse(options.body).lines;return {id:'saved',number:'TEST'};
 }
 return originalLineApi(path,options);
};
"""
    html = HTML.replace('</script><script src="/billing-workspace.js">', extra + '</script><script src="/billing-workspace.js">')
    with playwright.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Chromium indisponible : {exc}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(5000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def serve(route):
            path = route.request.url.split('?', 1)[0]
            if path.endswith('/admin'): route.fulfill(content_type='text/html; charset=utf-8', body=html)
            elif path.endswith('.js'): route.fulfill(content_type='application/javascript', body=(WEB/'billing-workspace.js').read_text(encoding='utf-8'))
            elif path.endswith('.css'): route.fulfill(content_type='text/css', body=(WEB/'billing-workspace.css').read_text(encoding='utf-8'))
            else: route.fulfill(status=404)
        page.route('**/*', serve)
        page.goto('http://lines-ui.test/admin')
        page.locator('#billingHomeBadge').click()
        page.locator('[data-billtab="new"]').click()
        page.locator('#billingNewHeader option[value="h"]').wait_for(state='attached')
        page.evaluate("""() => {
          document.getElementById('billingLines').replaceChildren();
          ['A','B','C'].forEach((name,i)=>billingAddLine({id:name,name,quantity:i+1,price_xof:100,unit:'pièce'}));
          window.lineNodes=[...document.querySelectorAll('#billingLines .billing-line')];
          window.initialTotal=document.getElementById('billingDraftTotal').textContent;
          api=async (path,options={})=>{
            if(path==='/api/v1/billing/documents'){window.sentLines=JSON.parse(options.body).lines;return {id:'saved',number:'TEST'}};
            throw new Error('Requête inutile : '+path);
          };
          billingOpen=async()=>{};openBillingInvoice=()=>{};
        }""")
        names = lambda: page.locator('.bill-designation').evaluate_all('(inputs)=>inputs.map(input=>input.value)')
        page.locator('.billing-move-up').nth(2).click()
        assert names() == ['A', 'C', 'B']
        # Native drag-and-drop, using the handle only (inputs stay editable).
        page.evaluate("""() => {
          const rows=document.querySelectorAll('#billingLines .billing-line'),dataTransfer=new DataTransfer();
          rows[2].querySelector('.billing-line-grip').dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer}));
          const y=rows[0].getBoundingClientRect().top+1;
          rows[0].dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer,clientY:y}));
          rows[0].dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer,clientY:y}));
        }""")
        assert names() == ['B', 'A', 'C']
        assert page.evaluate("window.lineNodes.every(row=>document.getElementById('billingLines').contains(row))")
        assert page.locator('#billingDraftTotal').inner_text() == page.evaluate('window.initialTotal')
        assert page.locator('.billing-line-number').all_text_contents() == ['1', '2', '3']
        assert page.locator('.billing-move-up').first.is_disabled()
        assert page.locator('.billing-move-down').last.is_disabled()
        assert page.locator('.bill-quantity').first.evaluate('input=>getComputedStyle(input).textAlign') == 'center'
        assert page.locator('.billing-line').first.evaluate('row=>row.getBoundingClientRect().height') <= 40
        assert page.locator('.billing-line-actions').first.evaluate('el=>new Set([...el.children].map(b=>b.getBoundingClientRect().top)).size') == 1
        page.set_viewport_size({"width":390,"height":844})
        assert page.locator('.billing-line').first.evaluate('row=>getComputedStyle(row).gridTemplateColumns.split(" ").length') == 5
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
        page.evaluate('billingSaveDocument({preventDefault(){}})')
        assert [line['product_id'] for line in page.evaluate('window.sentLines')] == ['B','A','C']
        assert [line['quantity'] for line in page.evaluate('window.sentLines')] == [2,1,3]
        page.locator('.billing-remove-line').nth(1).click()
        assert names() == ['B','C']
        assert not errors
        browser.close()


def test_credit_workspace_purchase_form_and_repayment_popup(tmp_path):
    extra = """
function newId(){return 'credit-ui-request-0001'}
const originalBillingApi=api;
api=async function(path,options={}){
 if(path.includes('/credit-accounts/c'))return {customer_id:'c',customer_name:'Client exemple',balance:300,total_purchases:300,total_repaid:0,archived:false,operations:[{kind:'PURCHASE',date:'2026-10-02',number:'INV-TEST',invoice_id:'new-invoice',amount:300,allocations:[],lines:[{quantity:1,description:'Ramette'}]}],page:1,has_more:false,operation_count:1};
 if(path.includes('/credit-accounts'))return {items:[],total:0,active_count:0,balance:0,has_more:false};
 if(path==='/api/v1/billing/documents'&&options.method==='POST'){window.creditSent=JSON.parse(options.body);return {id:'new-invoice',number:'INV-TEST',customer_id:'c'}};
 return originalBillingApi(path,options);
};
"""
    html = HTML.replace('</script><script src="/billing-workspace.js">', extra + '</script><script src="/billing-workspace.js">')
    with playwright.sync_playwright() as driver:
        try:
            browser=driver.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Chromium indisponible : {exc}")
        page=browser.new_page(viewport={"width":1440,"height":1000})
        page.set_default_timeout(5000)
        errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
        def serve(route):
            path=route.request.url.split('?',1)[0]
            if path.endswith('/admin'): route.fulfill(content_type='text/html; charset=utf-8',body=html)
            elif path.endswith('.js'): route.fulfill(content_type='application/javascript',body=(WEB/'billing-workspace.js').read_text(encoding='utf-8'))
            elif path.endswith('.css'): route.fulfill(content_type='text/css',body=(WEB/'billing-workspace.css').read_text(encoding='utf-8'))
            else: route.fulfill(status=404)
        page.route('**/*',serve);page.goto('http://credit-ui.test/admin')
        page.locator('#billingHomeBadge').click()
        page.locator('[data-billtab="credits"]').click()
        page.get_by_role('button',name='＋ Nouvel achat à crédit',exact=True).click()
        page.locator('#billingNewCustomer option[value="c"]').wait_for(state='attached')
        page.locator('#billingCustomerSearchToggle').click()
        page.locator('#billingCustomerSearchOptions').get_by_role('option',name='Client exemple',exact=True).click()
        page.locator('.bill-designation').fill('Ramette')
        page.locator('.bill-price').fill('300')
        page.get_by_role('button',name='Enregistrer l’achat à crédit',exact=True).click()
        page.get_by_role('heading',name='Client exemple',exact=True).wait_for()
        assert page.evaluate('window.creditSent.on_credit') is True
        assert page.evaluate('window.creditSent.request_id') == 'credit-ui-request-0001'
        page.get_by_role('button',name='Rembourser',exact=True).click()
        assert page.locator('#billingCreditRepaymentDialog').is_visible()
        page.screenshot(path=str(tmp_path/'credits-ui.png'),full_page=True)
        assert not errors
        browser.close()


def test_billing_badges_and_invoice_editor_are_visible_on_desktop_and_mobile():
    with playwright.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Chromium indisponible : {exc}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(5000)
        page.set_default_navigation_timeout(5000)

        def serve(route):
            path = route.request.url.split("?", 1)[0]
            if path.endswith("/admin"):
                route.fulfill(status=200,content_type="text/html; charset=utf-8",body=HTML)
            elif path.endswith("/billing-workspace.js"):
                route.fulfill(status=200,content_type="application/javascript",body=(WEB / "billing-workspace.js").read_text(encoding="utf-8"))
            elif path.endswith("/billing-workspace.css"):
                route.fulfill(status=200,content_type="text/css",body=(WEB / "billing-workspace.css").read_text(encoding="utf-8"))
            else:
                route.fulfill(status=404)

        page.route("**/*", serve)
        page.goto("http://fusaa-ui.test/admin")
        assert page.locator("#billingHomeBadge").is_visible()
        page.locator("#billingHomeBadge").click()
        assert page.locator("#billing .billing-menu [data-billtab]").count() == 11
        assert not page.locator(".workspace > .sidebar").is_visible()
        page.locator('[data-billtab="clients"]').click()
        assert page.locator("#billingGlassDialog").is_visible()
        assert page.locator("#billingGlassContent .billing-hero h1").inner_text() == "Clients"
        page.locator("#billingGlassDialog button[aria-label='Fermer']").click()
        page.locator('[data-billtab="headers"]').click()
        assert page.locator("#billingGlassDialog").is_visible()
        assert page.locator("#billingGlassContent h2").first.inner_text() == "Entêtes disponibles"
        page.locator("#billingGlassDialog button[aria-label='Fermer']").click()
        page.locator('[data-billtab="new"]').click()
        assert page.locator("#billingWorkspaceContent .billing-editor-heading h1").inner_text() == "Nouvelle facture"
        assert page.locator("#billingNewHeader").input_value() == "h"
        assert page.locator("#billingNewCatalog table tbody tr").count() == 1
        assert page.locator("#billingLines .billing-line").count() == 1
        page.locator("#billingNewCatalog button[aria-label='Ajouter à la facture']").click()
        assert page.locator("#billingLines .billing-line").count() == 2
        assert page.locator("#billingLines .billing-line").last.get_attribute("data-unit") == "paquet"
        page.locator("#billingAddHeader").click()
        assert page.locator("#billingHeaderQuickDialog").is_visible()
        page.locator("#billingHeaderQuickDialog [name='company_name']").fill("Nouvelle entête")
        page.locator("#billingHeaderQuickDialog form").last.evaluate("form => form.requestSubmit()")
        assert page.locator("#billingNewHeader").input_value() == "new-h"
        page.locator("#billingAddCustomer").click()
        assert page.locator("#billingCustomerDialog").is_visible()
        page.locator("#billingCustomerDialog [name='name']").fill("Nouveau client")
        page.locator("#billingCustomerDialog form").evaluate("form => form.requestSubmit()")
        assert page.locator("#billingNewCustomer").input_value() == "new-c"
        page.get_by_role("button",name="Ouvrir le chat IA",exact=True).click()
        assert page.locator("#billingFacturationAssistantDialog").is_visible()
        page.locator("#billingAssistantInput").fill("Fais une proforma : 2 x Ramette A4 a 3 500")
        page.locator("#billingAssistantForm").evaluate("form=>form.requestSubmit()")
        assert page.locator("#billingFacturationAssistantDialog").get_by_text("Appliquer au brouillon").is_visible()
        page.locator("#billingFacturationAssistantDialog button[aria-label='Fermer']").click()
        page.locator('[data-billtab="dashboard"]').click()
        assert page.locator("#billingWorkspaceContent .billing-hero h1").inner_text() == "Facturation FUSAA"
        page.locator("#billingWorkspaceContent").get_by_text("Assistant import CSV").click()
        assert page.locator("#billingImportAssistantDialog").is_visible()
        page.locator("#billingImportFile-categories").set_input_files({"name":"facturation_categories.csv","mimeType":"text/csv","buffer":b"Categorie;Description\nBureautique;Papier\n"})
        page.locator("#billingImportAssistantDialog").get_by_text("Analyser les CSV").click()
        assert page.locator("#billingImportResults").get_by_text("Bureautique").is_visible()
        page.locator("#billingImportExecute").click()
        page.locator("#billingImportAssistantDialog").wait_for(state="hidden", timeout=5000)
        assert page.locator("#billingWorkspaceContent .billing-hero h1").inner_text() == "Facturation FUSAA"
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.locator('[data-billtab="new"]').is_visible()
        overflow = page.evaluate("""() => ({width:document.documentElement.scrollWidth, viewport:window.innerWidth, elements:[...document.querySelectorAll('#billing *')].filter(node=>node.getBoundingClientRect().right>window.innerWidth+1).slice(0,8).map(node=>({tag:node.tagName,className:node.className,right:Math.round(node.getBoundingClientRect().right)}))})""")
        assert overflow["width"] <= overflow["viewport"] + 1, overflow
        browser.close()
