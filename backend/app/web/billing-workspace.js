/* Facturation FUSAA : espace de gestion inspiré des parcours Boulangerie. */
const billingState={tab:"dashboard",page:1,productPage:1,productSearch:"",products:[],headers:[],customers:[],categories:[],selectedHeader:null};
const billingLabels={dashboard:"Tableau de bord",new:"Nouvelle facture",documents:"Documents",clients:"Clients",products:"Produits",headers:"Entêtes",categories:"Catégories",reports:"Rapports",maintenance:"Maintenance",settings:"Paramètres"};
const billingIcon=paths=>'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+paths+'</svg>';
const billingIcons={
  dashboard:billingIcon('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'),
  new:billingIcon('<path d="M12 4v16M4 12h16"/><rect x="3" y="3" width="18" height="18" rx="3"/>'),
  documents:billingIcon('<path d="M7 3h7l4 4v14H7zM14 3v5h4M10 12h5M10 16h5"/>'),
  clients:billingIcon('<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 5"/>'),
  products:billingIcon('<path d="m12 3 9 5-9 5-9-5 9-5ZM3 8v9l9 5 9-5V8M12 13v9"/>'),
  headers:billingIcon('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 14h5M7 17h8"/>'),
  categories:billingIcon('<path d="M3 7h7v7H3zM14 7h7v7h-7zM3 17h7v4H3zM14 17h7v4h-7z"/>'),
  reports:billingIcon('<path d="M4 20V11m5 9V6m5 14v-8m5 8V4M2 20h20"/>'),
  maintenance:billingIcon('<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9 7 7m10 10 2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>'),
  settings:billingIcon('<path d="M4 7h16M4 17h16M8 4v6m8 4v6"/><circle cx="8" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>')
};
const billingCurrency=value=>money(Number(value||0));
const billingDate=value=>value?new Date(value).toLocaleDateString("fr-FR"):"—";
const billingSelect=(items,placeholder)=>'<option value="">'+esc(placeholder)+'</option>'+items.map(item=>'<option value="'+esc(item.id)+'">'+esc(item.company_name||item.name)+'</option>').join("");
function mountBillingWorkspace(){
  const billingView=document.getElementById("billing");
  if(!billingView||document.getElementById("billingWorkspace"))return false;
  Array.from(billingView.children).forEach(item=>item.style.display="none");
  billingView.insertAdjacentHTML("beforeend",'<div id="billingWorkspace" class="billing-workspace"><aside class="billing-menu"><a class="billing-back" href="#dashboard" onclick="selectView(\'dashboard\');return false">← Accueil FUSAA</a><h2>Gestion Factures</h2><div class="billing-menu-grid">'+Object.entries(billingLabels).map(([key,label])=>'<button type="button" data-billtab="'+key+'" aria-label="'+esc(label)+'"><i>'+billingIcons[key]+'</i><span>'+esc(label)+'</span></button>').join("")+'</div></aside><div class="billing-main"><div id="billingWorkspaceContent"></div></div></div>');
  document.getElementById("billingWorkspace").addEventListener("click",event=>{const button=event.target.closest("[data-billtab]");if(button)billingNavigate(button.dataset.billtab)});
  loadBilling=()=>billingOpen("dashboard");
  return true;
}
window.mountBillingWorkspace=mountBillingWorkspace;
mountBillingWorkspace();
function mountBillingHomeBadge(){const head=document.querySelector("#dashboard .view-head");if(head&&!document.getElementById("billingHomeBadge"))head.insertAdjacentHTML("afterend",'<button id="billingHomeBadge" type="button" onclick="selectView(\'billing\')"><span class="billing-home-icon">'+billingIcons.documents+'</span><span><strong>Facturation FUSAA</strong><small>Factures, devis, entêtes et rapports</small></span><b>Ouvrir la facturation →</b></button>')}
mountBillingHomeBadge();

function billingHero(title,subtitle,action=""){
  return '<div class="billing-hero"><div><span class="billing-eyebrow">BOUTIQUE & SERVICE · FCFA</span><h1>'+esc(title)+'</h1><p>'+esc(subtitle)+'</p></div><div class="billing-actions">'+action+'</div></div>';
}
function billingSet(html){const target=document.getElementById(billingState.popupTarget||"billingWorkspaceContent");if(target)target.innerHTML=html}
function billingActive(tab){document.querySelectorAll("#billing .billing-menu button").forEach(button=>{const active=button.dataset.billtab===tab;button.classList.toggle("active",active);button.setAttribute("aria-pressed",active?"true":"false")})}
const billingPopupTabs=new Set(["documents","clients","products","headers","categories","reports","maintenance","settings"]);
function billingNavigate(tab){billingPopupTabs.has(tab)?billingPopup(tab):billingOpen(tab)}
async function billingPopup(tab){
  let dialog=document.getElementById("billingGlassDialog");
  if(!dialog){document.body.insertAdjacentHTML("beforeend",'<dialog id="billingGlassDialog" class="billing-glass-dialog"><div class="billing-glass-head"><span class="billing-eyebrow">FACTURATION FUSAA</span><button class="secondary" type="button" aria-label="Fermer" onclick="billingClosePopup()">×</button></div><div id="billingGlassContent"></div></dialog>');dialog=document.getElementById("billingGlassDialog")}
  billingState.popupTarget="billingGlassContent";dialog.showModal();
  try{await billingOpen(tab)}finally{billingState.popupTarget=null}
}
function billingClosePopup(){const dialog=document.getElementById("billingGlassDialog");if(dialog?.open)dialog.close();billingState.popupTarget=null}
async function billingOpen(tab){
  if(!billingLabels[tab])tab="dashboard";
  billingState.tab=tab;billingActive(tab);
  billingSet(billingHero(billingLabels[tab],"Chargement de votre espace de facturation…")+'<div class="billing-panel billing-empty">Chargement…</div>');
  try{
    if(tab==="dashboard")await billingDashboard();
    if(tab==="new")await billingNew();
    if(tab==="documents")await billingDocuments();
    if(tab==="clients")await billingClients();
    if(tab==="products")await billingProducts();
    if(tab==="headers")await billingHeaders();
    if(tab==="categories")await billingCategories();
    if(tab==="reports")await billingReports();
    if(tab==="maintenance")await billingMaintenance();
    if(tab==="settings")await billingSettings();
  }catch(error){billingSet(billingHero(billingLabels[tab],"Une erreur empêche le chargement.")+'<div class="billing-panel billing-note">'+esc(error.message)+'</div>');tell(error.message)}
}

async function billingDashboard(){
  const data=await api("/api/v1/billing/dashboard?organization_id="+encodeURIComponent(org));
  const cards=[
    ["new","Nouvelle facture","Créer une facture, un devis ou un reçu"],["headers","Entêtes","Nom, logo, adresse et modèle PDF"],["clients","Clients","Coordonnées et comptes clients"],["products","Produits","Catalogue partagé et import CSV"],["documents","Documents","Factures, devis et bons archivés"],["categories","Catégories","Classer les produits de facturation"],["settings","Paramètres facture","TVA, ISB, devise et préférences"],["reports","Rapports","Encaissements et soldes clients"],["maintenance","Maintenance","Contrôler et régénérer les documents"]
  ];
  billingSet(billingHero("Facturation FUSAA","Choisissez une action. Les outils s’ouvrent dans des cartes liquid glass.",'<span class="billing-total">'+billingCurrency(data.invoiced_xof)+'</span>')+
    '<section class="billing-landing"><div class="billing-landing-intro"><div><span class="billing-eyebrow">ESPACE DE GESTION</span><h2>Tout votre atelier de facturation</h2><p>Les données Boutique et Facturation restent réunies dans le même compte FUSAA.</p></div><div class="billing-mini-stats"><span><b>'+data.invoices+'</b>Documents</span><span><b>'+data.customers+'</b>Clients</span><span><b>'+data.headers+'</b>Entêtes</span></div></div><div class="billing-card-grid">'+cards.map(([key,title,subtitle])=>'<button type="button" class="billing-glass-card '+(key==="new"?"primary":"")+'" onclick="'+(key==="new"?'billingOpen':'billingPopup')+'(\''+key+'\')"><i>'+billingIcons[key]+'</i><strong>'+title+'</strong><small>'+subtitle+'</small><em>Ouvrir <span>→</span></em></button>').join("")+'</div></section>');
}
function billingInvoiceTable(items){
  if(!items.length)return '<p class="billing-empty">Aucun document enregistré.</p>';
  return '<div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Numéro</th><th>Client</th><th>Type</th><th>Date</th><th>Montant</th><th>Actions</th></tr></thead><tbody>'+items.map(item=>'<tr><td><b>'+esc(item.number)+'</b></td><td>'+esc(item.customer_name||item.customer||"Client comptant")+'</td><td>'+esc(item.document_type)+'</td><td>'+billingDate(item.created_at)+'</td><td>'+billingCurrency(item.total_amount)+'</td><td><button class="secondary" type="button" onclick="openBillingInvoice(\''+esc(item.id)+'\')">Voir</button><button class="secondary" type="button" onclick="downloadBillingInvoice(\''+esc(item.id)+'\',\''+esc(item.number)+'\')">PDF</button><button class="secondary" type="button" onclick="billingDuplicate(\''+esc(item.id)+'\')">Dupliquer</button><button class="secondary" type="button" onclick="billingCompetition(\''+esc(item.id)+'\')">Concurrence</button></td></tr>').join("")+'</tbody></table></div>';
}
async function billingDuplicate(id){const type=prompt("Type de copie : INVOICE, QUOTE, PROFORMA, DELIVERY_NOTE ou RECEIPT","QUOTE");if(type===null)return;try{const result=await api("/api/v1/billing/invoices/"+id+"/duplicate?document_type="+encodeURIComponent(type.trim().toUpperCase()),{method:"POST"});tell(result.number+" créé.");billingOpen("documents")}catch(error){tell(error.message)}}
async function billingCompetition(id){try{const headers=await api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org));const choices=headers.map((item,index)=>(index+1)+". "+item.company_name).join("\n");const selected=prompt("Choisissez le numéro de l’entête pour le devis concurrence :\n"+choices,"1");if(selected===null)return;const header=headers[Number(selected)-1];if(!header)throw Error("Entête invalide.");const margin=prompt("Marge en pourcentage","10");if(margin===null)return;const result=await api("/api/v1/billing/invoices/"+id+"/competition",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({billing_header_id:header.id,margin_percent:Number(margin)})});tell(result.number+" créé.");billingOpen("documents")}catch(error){tell(error.message)}}

async function billingLoadReference(){
  const [headers,customers]=await Promise.all([api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org)),api("/api/v1/customers?organization_id="+encodeURIComponent(org))]);
  billingState.headers=headers;billingState.customers=customers;
}
async function billingNew(){
  await billingLoadReference();billingState.productPage=1;billingState.productSearch="";
  billingSet(billingHero("Nouvelle facture","Créez une facture avec l’entête et les produits de votre choix.",'<button class="secondary" type="button" onclick="billingOpen(\'documents\')">← Retour à la liste</button>')+`
    <section class="billing-panel billing-ai">
      <div class="billing-actions billing-ai-title"><h2>✦ Assistant IA de facturation</h2><span class="muted">Prépare un brouillon, puis attend votre confirmation</span></div>
      <div class="billing-ai-fields">
        <label>Entreprise / entête<input id="billingHeaderSearch" placeholder="Rechercher dans entreprise / entête…"><select id="billingNewHeader" required>${billingSelect(billingState.headers,"Choisir dans la demande")}</select></label>
        <label>Client<input id="billingCustomerSearch" placeholder="Rechercher dans client…"><select id="billingNewCustomer">${billingSelect(billingState.customers,"Nouveau ou à préciser")}</select></label>
        <label>Demande<input id="billingAiPrompt" placeholder="Ex. 2 × Ramette A4 à 3 500"></label>
        <button type="button" onclick="billingAskAi()">Ouvrir le chat IA</button>
      </div>
    </section>
    <div class="billing-composer">
      <section class="billing-panel billing-catalog-panel">
        <div class="billing-catalog-heading"><h2>Catalogue<br>des produits</h2><div class="billing-catalog-tools"><button class="secondary" type="button" onclick="document.getElementById('billingNewCsv').click()">↧ Importer (CSV)</button><button type="button" onclick="billingQuickProduct()">＋ Ajouter produit</button><button class="secondary" type="button" onclick="billingProductSearch()">↻ Actualiser</button><input id="billingNewSearch" placeholder="Rechercher un produit"><button class="secondary" type="button" onclick="billingProductSearch(true)">Rechercher</button></div></div>
        <input id="billingNewCsv" class="hidden" type="file" accept=".csv,text/csv" onchange="billingQuickImportCsv()">
        <div id="billingNewCatalog"></div>
      </section>
      <section class="billing-panel billing-lines-panel">
        <div class="billing-actions billing-lines-title"><h2>Lignes de facture</h2><button class="secondary" type="button" onclick="billingAddLine()">＋ Ajouter une ligne</button></div>
        <div class="billing-line-head"><span>N°</span><span>Désignation</span><span>Quantité</span><span>Prix unitaire</span><span>Actions</span></div>
        <div id="billingLines"></div><div id="billingDraftTotal" class="billing-total">Total HT : 0 FCFA</div>
        <div class="billing-actions billing-submit-row"><button type="submit" form="billingNewForm">↧ Enregistrer la facture</button></div>
      </section>
    </div>
    <form id="billingNewForm" class="billing-panel"><h2>Informations générales</h2><div class="billing-form-grid"><label>Nom du nouveau client<input id="billingNewCustomerName" placeholder="Nom et prénom"></label><label>Téléphone<input id="billingNewCustomerPhone" placeholder="Téléphone"></label><label>Adresse client<input id="billingNewCustomerAddress" placeholder="Adresse"></label><label>Date<input id="billingNewDate" type="date"></label><label>Type de document<select id="billingNewType"><option value="INVOICE">Facture</option><option value="QUOTE">Devis</option><option value="PROFORMA">Proforma</option><option value="DELIVERY_NOTE">Bon de livraison</option><option value="RECEIPT">Reçu</option></select></label><label>Remise FCFA<input id="billingNewDiscount" type="number" min="0" value="0"></label><label class="wide">Pour / objet<input id="billingNewSubject" placeholder="Objet de la facture"></label><label class="wide">Notes<textarea id="billingNewNotes" placeholder="Mentions complémentaires"></textarea></label></div></form>
    <dialog id="billingQuickProductDialog" class="billing-quick-dialog"><form method="dialog"><div class="billing-actions billing-lines-title"><h2>Ajouter un produit de facturation</h2><button class="secondary" type="submit" aria-label="Fermer">×</button></div></form><form id="billingQuickProductForm" class="billing-form-grid"><label>Désignation<input name="name" required></label><label>Prix FCFA<input name="unit_price" type="number" min="0" required></label><label>Unité<input name="unit" value="piece"></label><label>Code<input name="sku"></label><button type="submit">Enregistrer le produit</button></form></dialog>`);
  document.getElementById("billingNewHeader").value=billingState.headers.find(item=>item.is_default)?.id||billingState.headers[0]?.id||"";
  document.getElementById("billingNewDate").value=new Date().toISOString().slice(0,10);
  document.getElementById("billingNewForm").onsubmit=billingSaveDocument;
  document.getElementById("billingNewCustomer").onchange=()=>{const has=Boolean(document.getElementById("billingNewCustomer").value);["billingNewCustomerName","billingNewCustomerPhone","billingNewCustomerAddress"].forEach(id=>document.getElementById(id).disabled=has)};
  document.getElementById("billingHeaderSearch").oninput=event=>billingFilterSelect("billingNewHeader",billingState.headers,event.target.value,"company_name");
  document.getElementById("billingCustomerSearch").oninput=event=>billingFilterSelect("billingNewCustomer",billingState.customers,event.target.value,"name");
  document.getElementById("billingQuickProductForm").onsubmit=billingSaveQuickProduct;
  billingAddLine();await billingProductSearch(true);
}
function billingAskAi(){const prompt=document.getElementById("billingAiPrompt")?.value.trim();openBillingAssistant();if(prompt){document.getElementById("aiMessage").value=prompt;document.getElementById("aiMessage").focus()}}
function billingFilterSelect(id,items,search,key){
  const select=document.getElementById(id),previous=select.value,needle=search.trim().toLocaleLowerCase("fr");
  const filtered=items.filter(item=>String(item[key]||"").toLocaleLowerCase("fr").includes(needle));
  select.innerHTML=billingSelect(filtered,id==="billingNewHeader"?"Choisir dans la demande":"Nouveau ou à préciser");
  if(filtered.some(item=>item.id===previous))select.value=previous;
  else if(id==="billingNewHeader"&&filtered.length)select.value=filtered[0].id;
}
function billingQuickProduct(){document.getElementById("billingQuickProductDialog")?.showModal()}
async function billingSaveQuickProduct(event){
  event.preventDefault();const form=new FormData(event.target);
  try{
    await api("/api/v1/billing/products",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:String(form.get("name")).trim(),unit_price:Number(form.get("unit_price")),unit:String(form.get("unit")||"piece"),sku:form.get("sku")||null,stock_quantity:0,stock_minimum:3,cost_xof:0})});
    document.getElementById("billingQuickProductDialog").close();tell("Produit enregistré dans la facturation.");await billingProductSearch(true);
  }catch(error){tell(error.message)}
}
async function billingQuickImportCsv(){
  const file=document.getElementById("billingNewCsv")?.files[0];if(!file)return;
  const body=new FormData();body.append("file",file);
  try{const result=await api("/api/v1/billing/products/import?organization_id="+encodeURIComponent(org),{method:"POST",body});tell(result.created+" produit(s) importé(s) pour la facturation.");await billingProductSearch(true)}catch(error){tell(error.message)}
}
function billingAddLine(item){
  const box=document.getElementById("billingLines");if(!box)return;
  const row=document.createElement("div");row.className="billing-line";row.dataset.productId=item?.id||"";row.dataset.unit=item?.unit||"piece";
  row.innerHTML='<span class="billing-line-number"></span><input class="bill-designation" placeholder="Désignation" required value="'+esc(item?.name||"")+'"><input class="bill-quantity" type="number" min="0.01" step="0.01" value="1" aria-label="Quantité"><input class="bill-price" type="number" min="0" step="0.01" value="'+esc(item?.price_xof??"")+'" placeholder="Prix" aria-label="Prix unitaire"><button class="danger" type="button" aria-label="Supprimer la ligne">×</button>';
  row.querySelector("button").onclick=()=>{row.remove();billingUpdateTotal()};row.querySelectorAll("input").forEach(input=>input.addEventListener("input",billingUpdateTotal));box.append(row);billingUpdateTotal();
}
function billingUpdateTotal(){const rows=[...document.querySelectorAll("#billingLines .billing-line")];rows.forEach((row,index)=>row.querySelector(".billing-line-number").textContent=index+1);const sum=rows.reduce((value,row)=>value+Number(row.querySelector(".bill-quantity").value||0)*Number(row.querySelector(".bill-price").value||0),0);const target=document.getElementById("billingDraftTotal");if(target)target.textContent="Total HT : "+billingCurrency(sum)}
async function billingProductSearch(reset=false){
  const target=document.getElementById("billingNewCatalog");if(!target)return;
  if(reset)billingState.productPage=1;billingState.productSearch=document.getElementById("billingNewSearch")?.value.trim()||"";
  const data=await api("/api/v1/billing/catalog/page?organization_id="+encodeURIComponent(org)+"&q="+encodeURIComponent(billingState.productSearch)+"&page="+billingState.productPage+"&page_size=12");billingState.products=data.items;
  target.innerHTML=data.items.length?'<div class="billing-table-wrap billing-catalog-table"><table class="billing-table"><thead><tr><th>Produit</th><th>Prix unitaire</th><th>Unité</th><th>Ajouter</th><th>Modifier</th><th>Supprimer</th></tr></thead><tbody>'+data.items.map((item,index)=>'<tr><td>'+esc(item.name)+'<small>'+esc(item.source==="BOUTIQUE"?"Boutique":"Facturation")+'</small></td><td>'+billingCurrency(item.price_xof)+'</td><td>'+esc(item.unit||"piece")+'</td><td><button type="button" class="secondary billing-round-action" aria-label="Ajouter à la facture" onclick="billingAddLine(billingState.products['+index+'])">＋</button></td><td>'+(item.source==="FACTURATION"?'<button type="button" class="secondary billing-round-action" aria-label="Modifier le produit" onclick="billingQuickEditProduct('+index+')">✎</button>':"—")+'</td><td>'+(item.source==="FACTURATION"?'<button type="button" class="secondary billing-round-action" aria-label="Archiver le produit" onclick="billingQuickDeleteProduct('+index+')">♜</button>':"—")+'</td></tr>').join("")+'</tbody></table></div>':'<p class="billing-empty">Aucun produit trouvé. Vous pouvez saisir une ligne libre.</p>';
  target.innerHTML+='<div class="billing-pagination"><button class="secondary" type="button" '+(data.page<=1?"disabled":"")+' onclick="billingState.productPage--;billingProductSearch()">←</button><span>Page '+data.page+'</span><button class="secondary" type="button" '+(!data.has_more?"disabled":"")+' onclick="billingState.productPage++;billingProductSearch()">→</button></div>';
}
async function billingQuickEditProduct(index){
  const item=billingState.products[index];if(!item||item.source!=="FACTURATION")return;
  const name=prompt("Désignation",item.name);if(name===null||!name.trim())return;
  const price=prompt("Prix FCFA",item.price_xof);if(price===null||!Number.isFinite(Number(price))||Number(price)<0)return;
  try{await api("/api/v1/billing/products/"+item.id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:name.trim(),unit_price:Number(price),sku:item.sku,billing_category_id:item.billing_category_id,unit:item.unit||"piece",stock_quantity:item.stock_quantity,stock_minimum:item.stock_minimum,cost_xof:item.cost_xof})});tell("Produit modifié.");await billingProductSearch()}catch(error){tell(error.message)}
}
async function billingQuickDeleteProduct(index){
  const item=billingState.products[index];if(!item||item.source!=="FACTURATION"||!confirm("Archiver ce produit réservé à la facturation ?"))return;
  try{await api("/api/v1/billing/products/"+item.id,{method:"DELETE"});tell("Produit archivé.");await billingProductSearch()}catch(error){tell(error.message)}
}
async function billingSaveDocument(event){
  event.preventDefault();const rows=[...document.querySelectorAll("#billingLines .billing-line")];
  const lines=rows.map(row=>({product_id:row.dataset.productId||null,description:row.querySelector(".bill-designation").value.trim(),quantity:Number(row.querySelector(".bill-quantity").value),unit_amount:Number(row.querySelector(".bill-price").value),unit:row.dataset.unit||"piece"})).filter(item=>item.description);
  if(!lines.length){tell("Ajoutez au moins une ligne à la facture.");return}
  if(!document.getElementById("billingNewHeader").value){tell("Choisissez une entête d’entreprise.");document.getElementById("billingNewHeader").focus();return}
  const customerId=document.getElementById("billingNewCustomer").value;
  const body={organization_id:org,billing_header_id:document.getElementById("billingNewHeader").value,customer_id:customerId||null,customer_name:customerId?null:document.getElementById("billingNewCustomerName").value.trim(),customer_phone:document.getElementById("billingNewCustomerPhone").value.trim()||null,customer_address:document.getElementById("billingNewCustomerAddress").value.trim()||null,issued_on:document.getElementById("billingNewDate").value+"T12:00:00Z",document_type:document.getElementById("billingNewType").value,subject:document.getElementById("billingNewSubject").value.trim()||null,notes:document.getElementById("billingNewNotes").value.trim()||null,discount_amount:Number(document.getElementById("billingNewDiscount").value||0),lines};
  try{const result=await api("/api/v1/billing/documents",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});tell(result.number+" enregistré.");await billingOpen("documents");openBillingInvoice(result.id)}catch(error){tell(error.message)}
}

async function billingDocuments(){
  const items=await api("/api/v1/billing/invoices?organization_id="+encodeURIComponent(org)+"&page="+billingState.page+"&page_size=25");
  billingSet(billingHero("Documents","Factures, devis, proformas, bons de livraison et reçus.",'<button type="button" onclick="billingOpen(\'new\')">+ Nouvelle facture</button>')+
    '<section class="billing-panel">'+billingInvoiceTable(items)+'<div class="billing-pagination"><button class="secondary" type="button" '+(billingState.page<=1?"disabled":"")+' onclick="billingState.page--;billingOpen(\'documents\')">← Précédent</button><span>Page '+billingState.page+'</span><button class="secondary" type="button" '+(items.length<25?"disabled":"")+' onclick="billingState.page++;billingOpen(\'documents\')">Suivant →</button></div></section>');
}

async function billingClients(){
  const items=await api("/api/v1/customers?organization_id="+encodeURIComponent(org));billingState.customers=items;
  billingSet(billingHero("Clients","Répertoire partagé par la Boutique et la facturation.")+'<section class="billing-panel"><h2>Ajouter un client</h2><form id="billClientForm" class="billing-form-grid"><label>Nom<input name="name" required></label><label>Téléphone<input name="phone"></label><label>E-mail<input name="email" type="email"></label><label>Adresse<input name="address"></label><button>Ajouter</button></form></section><section class="billing-panel"><h2>Comptes clients</h2><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Nom</th><th>Téléphone</th><th>E-mail</th><th>Actions</th></tr></thead><tbody>'+items.map(item=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.phone||"—")+'</td><td>'+esc(item.email||"—")+'</td><td><button class="secondary" type="button" onclick="billingEditClient(\''+esc(item.id)+'\')">Modifier</button><button class="danger" type="button" onclick="billingRemoveClient(\''+esc(item.id)+'\')">Supprimer</button></td></tr>').join("")+'</tbody></table></div></section>');
  document.getElementById("billClientForm").onsubmit=async event=>{event.preventDefault();const form=new FormData(event.target);try{await api("/api/v1/customers",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:form.get("name"),phone:form.get("phone")||null,email:form.get("email")||null,address:form.get("address")||null})});tell("Client ajouté.");billingClients()}catch(error){tell(error.message)}};
}
async function billingEditClient(id){const item=billingState.customers.find(value=>value.id===id);if(!item)return;const name=prompt("Nom",item.name);if(name===null||!name.trim())return;const phone=prompt("Téléphone",item.phone||"");if(phone===null)return;try{await api("/api/v1/billing/customers/"+id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({...item,organization_id:org,name:name.trim(),phone:phone.trim()||null})});tell("Client modifié.");billingClients()}catch(error){tell(error.message)}}
async function billingRemoveClient(id){if(!confirm("Supprimer ce client ? Son historique de factures sera protégé."))return;try{await api("/api/v1/billing/customers/"+id+"?organization_id="+encodeURIComponent(org),{method:"DELETE"});tell("Client supprimé.");billingClients()}catch(error){tell(error.message)}}

async function billingProducts(){
  const [categories,data]=await Promise.all([api("/api/v1/billing/categories?organization_id="+encodeURIComponent(org)),api("/api/v1/billing/catalog/page?organization_id="+encodeURIComponent(org)+"&page="+billingState.productPage+"&page_size=20&q="+encodeURIComponent(billingState.productSearch))]);
  billingState.categories=categories;billingState.products=data.items;
  billingSet(billingHero("Produits","Le catalogue de facturation réunit les articles Boutique et les articles internes.",'<button type="button" onclick="billingOpen(\'new\')">+ Nouvelle facture</button>')+
    '<section class="billing-panel"><h2>Ajouter un produit réservé à la facturation</h2><form id="billProductForm" class="billing-form-grid"><label>Désignation<input name="name" required></label><label>Prix FCFA<input name="unit_price" type="number" min="0" required></label><label>Code<input name="sku"></label><label>Catégorie<select name="billing_category_id">'+billingSelect(categories,"Sans catégorie")+'</select></label><label>Unité<input name="unit" value="piece"></label><label>Stock initial<input name="stock_quantity" type="number" min="0" value="0"></label><label>Seuil d’alerte<input name="stock_minimum" type="number" min="0" value="3"></label><label>Coût d’achat<input name="cost_xof" type="number" min="0" value="0"></label><button>Enregistrer le produit</button></form><div class="billing-actions"><input id="billCsvFile" type="file" accept=".csv,text/csv"><button class="secondary" type="button" onclick="billingImportCsv()">Importer la liste CSV</button></div></section>'+
    '<section class="billing-panel"><div class="billing-toolbar"><input id="billProductsSearch" placeholder="Rechercher" value="'+esc(billingState.productSearch)+'"><button class="secondary" type="button" onclick="billingState.productSearch=document.getElementById(\'billProductsSearch\').value.trim();billingState.productPage=1;billingProducts()">Rechercher</button></div><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Produit</th><th>Source</th><th>Prix</th><th>Stock</th><th>Actions</th></tr></thead><tbody>'+data.items.map((item,index)=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.source)+'</td><td>'+billingCurrency(item.price_xof)+'</td><td>'+esc(item.stock_quantity)+'</td><td>'+(item.source==="FACTURATION"?'<button class="secondary" type="button" onclick="billingEditProduct('+index+')">Modifier</button><button class="danger" type="button" onclick="billingRemoveProduct('+index+')">Archiver</button>':'<span class="muted">Gérer dans Boutique</span>')+'</td></tr>').join("")+'</tbody></table></div><div class="billing-pagination"><button class="secondary" type="button" '+(data.page<=1?"disabled":"")+' onclick="billingState.productPage--;billingProducts()">←</button><span>'+data.page+' / '+Math.max(1,Math.ceil(data.total/20))+'</span><button class="secondary" type="button" '+(!data.has_more?"disabled":"")+' onclick="billingState.productPage++;billingProducts()">→</button></div></section>');
  document.getElementById("billProductForm").onsubmit=async event=>{event.preventDefault();const f=new FormData(event.target);try{await api("/api/v1/billing/products",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:f.get("name"),unit_price:Number(f.get("unit_price")),sku:f.get("sku")||null,billing_category_id:f.get("billing_category_id")||null,unit:f.get("unit")||"piece",stock_quantity:Number(f.get("stock_quantity")||0),stock_minimum:Number(f.get("stock_minimum")||3),cost_xof:Number(f.get("cost_xof")||0)})});tell("Produit enregistré.");billingProducts()}catch(error){tell(error.message)}};
}
async function billingImportCsv(){const file=document.getElementById("billCsvFile")?.files[0];if(!file){tell("Choisissez un fichier CSV.");return}const body=new FormData();body.append("file",file);try{const result=await api("/api/v1/billing/products/import?organization_id="+encodeURIComponent(org),{method:"POST",body});tell(result.created+" produit(s) importé(s)"+(result.errors.length?" · "+result.errors.length+" ligne(s) ignorée(s)":""));billingProducts()}catch(error){tell(error.message)}}
async function billingEditProduct(index){const item=billingState.products[index];if(!item||item.source!=="FACTURATION")return;const name=prompt("Désignation",item.name);if(name===null||!name.trim())return;const price=prompt("Prix FCFA",item.price_xof);if(price===null)return;try{await api("/api/v1/billing/products/"+item.id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:name.trim(),unit_price:Number(price),sku:item.sku,billing_category_id:item.billing_category_id,unit:item.unit,stock_quantity:item.stock_quantity,stock_minimum:item.stock_minimum,cost_xof:item.cost_xof})});tell("Produit modifié.");billingProducts()}catch(error){tell(error.message)}}
async function billingRemoveProduct(index){const item=billingState.products[index];if(!item||!confirm("Archiver ce produit de facturation ?"))return;try{await api("/api/v1/billing/products/"+item.id,{method:"DELETE"});tell("Produit archivé ; les anciennes factures sont conservées.");billingProducts()}catch(error){tell(error.message)}}

async function billingHeaders(){
  const items=await api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org));billingState.headers=items;
  const current=items.find(item=>item.id===billingState.selectedHeader)||items.find(item=>item.is_default)||items[0];billingState.selectedHeader=current?.id||null;
  billingSet(billingHero("Entêtes d’entreprise","Les coordonnées, la TVA ou l’ISB et le style choisis apparaissent sur les PDF.")+
    '<div class="billing-split"><section class="billing-panel"><div class="billing-actions" style="justify-content:space-between"><h2>Entêtes disponibles</h2><button class="secondary" type="button" onclick="billingState.selectedHeader=null;billingHeaderForm(null)">+ Ajouter</button></div>'+items.map(item=>'<button class="billing-kpi" style="min-height:70px;margin:5px 0" type="button" onclick="billingState.selectedHeader=\''+esc(item.id)+'\';billingHeaderForm(billingState.headers.find(h=>h.id===billingState.selectedHeader))"><b style="font-size:1rem">'+esc(item.company_name)+'</b><small>'+esc(item.document_style)+(item.is_default?" · Par défaut":"")+'</small></button>').join("")+'</section><section id="billingHeaderFormHost" class="billing-panel"></section></div>');
  billingHeaderForm(current);
}
function billingHeaderForm(item){const host=document.getElementById("billingHeaderFormHost");if(!host)return;const styles={standard:"Standard",scan_gauche:"Référence 1 · gauche",scan_alasko:"Référence 2 · Alasko",scan_centre:"Référence 3 · centre",scan_compact:"Référence 4 · compact",scan_facture_simple:"Référence 5 · facture simple",moderne_clair:"Moderne clair",moderne_bandeau:"Moderne bandeau",moderne_minimal:"Moderne minimal"};
  host.innerHTML='<h2>'+(item?"Modifier l’entête":"Nouvel entête")+'</h2><form id="billHeaderForm" class="billing-form-grid"><label class="wide">Nom de l’entreprise<input name="company_name" required value="'+esc(item?.company_name||"")+'"></label><label class="wide">Adresse<textarea name="address">'+esc(item?.address||"")+'</textarea></label><label>Téléphone<input name="phone" value="'+esc(item?.phone||"")+'"></label><label>E-mail<input name="email" type="email" value="'+esc(item?.email||"")+'"></label><label>NIF<input name="nif" value="'+esc(item?.nif||"")+'"></label><label>RCCM<input name="rccm" value="'+esc(item?.rccm||"")+'"></label><label class="wide">URL du logo Cloudinary<input name="logo_url" value="'+esc(item?.logo_url||"")+'" placeholder="https://res.cloudinary.com/..."></label><label>Style PDF<select name="document_style">'+Object.entries(styles).map(([key,label])=>'<option value="'+key+'" '+(item?.document_style===key?"selected":"")+'>'+label+'</option>').join("")+'</select></label><label>Police du tableau<select name="table_font_family">'+["","times","arial","calibri","segoe","courier","trebuchet"].map(font=>'<option value="'+font+'" '+(item?.table_font_family===font?"selected":"")+'>'+(font||"Style par défaut")+'</option>').join("")+'</select></label><label>Taille police du tableau<input name="table_font_size" type="number" min="8" max="14" step=".5" value="'+esc(item?.table_font_size??"")+'"></label><label>Taux TVA (%)<input name="tax_rate" type="number" min="0" max="100" step=".01" value="'+esc(item?.tax_rate??19)+'"></label><label><input name="tax_enabled" type="checkbox" '+(item?.tax_enabled?"checked":"")+'> TVA applicable</label><label>Taux ISB (%)<input name="isb_rate" type="number" min="0" max="100" step=".01" value="'+esc(item?.isb_rate??3)+'"></label><label><input name="isb_enabled" type="checkbox" '+(item?.isb_enabled?"checked":"")+'> ISB applicable</label><label><input name="is_default" type="checkbox" '+(item?.is_default?"checked":"")+'> Entête par défaut</label><div class="billing-actions wide"><button>Enregistrer l’entête</button>'+(item?'<button class="danger" type="button" onclick="billingDeleteHeader(\''+esc(item.id)+'\')">Supprimer</button>':"")+'</div></form>';
  const logoField=host.querySelector('input[name="logo_url"]').closest("label");
  logoField.insertAdjacentHTML("afterend",item?'<div class="billing-header-logo wide">'+(item.logo_url?'<img src="'+esc(item.logo_url)+'" alt="Logo de '+esc(item.company_name)+'">':'<span class="muted">Aucun logo enregistré</span>')+'<div><label>Importer un logo (PNG, JPEG ou WebP)<input id="billingHeaderLogoFile" type="file" accept="image/png,image/jpeg,image/webp"></label><button class="secondary" type="button" onclick="billingUploadHeaderLogo(\''+esc(item.id)+'\')">Envoyer le logo</button></div></div>':'<p class="muted wide">Enregistrez l’entête, puis importez son logo.</p>');
  document.getElementById("billHeaderForm").onsubmit=event=>billingSaveHeader(event,item?.id||null);
}
async function billingUploadHeaderLogo(id){
  const file=document.getElementById("billingHeaderLogoFile")?.files[0];if(!file){tell("Choisissez un logo.");return}
  const body=new FormData();body.append("file",file);
  try{await api("/api/v1/billing/headers/"+encodeURIComponent(id)+"/logo",{method:"POST",body});tell("Logo enregistré sur l’entête.");await billingHeaders()}catch(error){tell(error.message)}
}
async function billingSaveHeader(event,id){event.preventDefault();const f=new FormData(event.target);const body={company_name:String(f.get("company_name")).trim(),address:f.get("address")||null,phone:f.get("phone")||null,email:f.get("email")||null,nif:f.get("nif")||null,rccm:f.get("rccm")||null,logo_url:f.get("logo_url")||null,document_style:f.get("document_style"),table_font_family:f.get("table_font_family")||null,table_font_size:f.get("table_font_size")?Number(f.get("table_font_size")):null,tax_enabled:f.has("tax_enabled"),tax_rate:Number(f.get("tax_rate")||0),isb_enabled:f.has("isb_enabled"),isb_rate:Number(f.get("isb_rate")||0),is_default:f.has("is_default")};try{const saved=await api("/api/v1/billing/headers"+(id?"/"+id:"?organization_id="+encodeURIComponent(org)),{method:id?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});billingState.selectedHeader=saved.id;tell("Entête enregistré.");billingHeaders()}catch(error){tell(error.message)}}
async function billingDeleteHeader(id){if(!confirm("Supprimer cet entête ? Les entêtes utilisés dans les factures sont protégés."))return;try{await api("/api/v1/billing/headers/"+id,{method:"DELETE"});billingState.selectedHeader=null;tell("Entête supprimé.");billingHeaders()}catch(error){tell(error.message)}}

async function billingCategories(){const items=await api("/api/v1/billing/categories?organization_id="+encodeURIComponent(org));billingState.categories=items;billingSet(billingHero("Catégories","Organisation du catalogue réservé à la facturation.")+'<section class="billing-panel"><form id="billCategoryForm" class="billing-form-grid"><label>Nom<input name="name" required></label><label>Description<input name="description"></label><button>Ajouter la catégorie</button></form></section><section class="billing-panel"><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Catégorie</th><th>Description</th><th>Actions</th></tr></thead><tbody>'+items.map((item,index)=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.description||"—")+'</td><td><button class="secondary" type="button" onclick="billingEditCategory('+index+')">Modifier</button><button class="danger" type="button" onclick="billingDeleteCategory('+index+')">Supprimer</button></td></tr>').join("")+'</tbody></table></div></section>');document.getElementById("billCategoryForm").onsubmit=async event=>{event.preventDefault();const f=new FormData(event.target);try{await api("/api/v1/billing/categories?organization_id="+encodeURIComponent(org),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:f.get("name"),description:f.get("description")||null})});tell("Catégorie créée.");billingCategories()}catch(error){tell(error.message)}}}
async function billingEditCategory(index){const item=billingState.categories[index],name=prompt("Nom de catégorie",item.name);if(name===null||!name.trim())return;try{await api("/api/v1/billing/categories/"+item.id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:name.trim(),description:item.description})});tell("Catégorie modifiée.");billingCategories()}catch(error){tell(error.message)}}
async function billingDeleteCategory(index){const item=billingState.categories[index];if(!confirm("Supprimer cette catégorie ? Les produits seront conservés."))return;try{await api("/api/v1/billing/categories/"+item.id,{method:"DELETE"});tell("Catégorie supprimée.");billingCategories()}catch(error){tell(error.message)}}

async function billingReports(){const [summary,credits]=await Promise.all([api("/api/v1/billing/reports/summary?organization_id="+encodeURIComponent(org)+"&days=30"),api("/api/v1/billing/customers/credits?organization_id="+encodeURIComponent(org))]);billingSet(billingHero("Rapports","Chiffres des 30 derniers jours et soldes clients.")+'<div class="billing-kpis">'+[["Facturé",billingCurrency(summary.invoiced)],["Encaissé",billingCurrency(summary.paid)],["À recevoir",billingCurrency(summary.outstanding)],["Clients débiteurs",credits.items.filter(item=>item.balance>0).length]].map(item=>'<div class="billing-kpi"><small>'+item[0]+'</small><b>'+esc(item[1])+'</b></div>').join("")+'</div><section class="billing-panel"><h2>Clients débiteurs</h2><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Client</th><th>Téléphone</th><th>Factures</th><th>Reste</th></tr></thead><tbody>'+credits.items.filter(item=>item.balance>0).map(item=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.phone||"—")+'</td><td>'+item.invoices+'</td><td>'+billingCurrency(item.balance)+'</td></tr>').join("")+'</tbody></table></div></section>')}
async function billingMaintenance(){const items=await api("/api/v1/billing/invoices?organization_id="+encodeURIComponent(org)+"&page_size=25");billingSet(billingHero("Maintenance","Les PDF peuvent être régénérés depuis leurs données enregistrées.")+'<section class="billing-panel"><h2>Documents récents</h2><p>Ouvrez un PDF pour le générer à nouveau ou le télécharger. Les données et les entêtes restent protégés dans la base.</p>'+billingInvoiceTable(items)+'</section>')}
async function billingSettings(){const headers=await api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org));billingSet(billingHero("Paramètres","Configuration de la facturation FUSAA.")+'<section class="billing-panel"><h2>Configuration active</h2><p>Entête par défaut : <b>'+esc(headers.find(item=>item.is_default)?.company_name||"Aucun")+'</b></p><p>Devise : <b>FCFA (XOF)</b></p><div class="billing-actions"><button type="button" onclick="billingOpen(\'headers\')">Configurer les entêtes</button><button class="secondary" type="button" onclick="billingOpen(\'categories\')">Catégories</button><button class="secondary" type="button" onclick="billingOpen(\'products\')">Produits</button></div></section>')}
