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
        assert page.locator("#billing .billing-menu [data-billtab]").count() == 10
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
        assert page.locator("#billingWorkspaceContent .billing-hero h1").inner_text() == "Nouvelle facture"
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
        page.locator("#billingAiPrompt").fill("Fais une proforma : 2 x Ramette A4 a 3 500")
        page.locator("button",has_text="Ouvrir le chat IA").click()
        assert page.locator("#billingFacturationAssistantDialog").is_visible()
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
