/* Facturation FUSAA : espace de gestion inspiré des parcours Boulangerie. */
const billingProductSearchBase=billingProductSearch;
billingProductSearch=async function(...args){const started=showFusaaOperation("Mise a jour du catalogue…");try{return await billingProductSearchBase(...args)}finally{await hideFusaaOperation(started)}};
async function billingLoading(label,work){const started=showFusaaOperation(label);try{return await work()}finally{await hideFusaaOperation(started)}}
const billingRequestTimeout=12000;
async function billingRequest(path,options={},timeout=billingRequestTimeout){
  const controller=new AbortController();let timer=0;
  try{return await Promise.race([api(path,{...options,signal:controller.signal}),new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error("Le chargement prend trop de temps. Vérifiez la connexion puis réessayez."))},timeout)})])}
  finally{clearTimeout(timer)}
}
const billingPause=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));
function billingLoadingContent(title){return billingHero(title,"Préparation sécurisée de votre espace de facturation…")+'<section class="billing-panel billing-popup-loading" aria-live="polite"><span class="billing-loader-orbit"><i></i></span><div><b>Chargement en cours</b><p>FUSAA récupère vos données et prépare les actions.</p></div><em><u></u></em></section>'}
function billingImportProgress(label,percent=8){return '<section class="billing-import-progress" style="--billing-import-progress:'+Math.max(4,Math.min(100,percent))+'%" aria-live="polite"><span class="billing-loader-orbit"><i></i></span><div><b id="billingImportProgressLabel">'+esc(label)+'</b><p>Vos données sont enregistrées de façon sécurisée.</p></div><em><u></u></em></section>'}
function billingImportProgressAt(target,label,percent,detail=""){
  if(!target)return;
  target.innerHTML=billingImportProgress(label,percent)+(detail?'<p class="billing-import-step">'+esc(detail)+'</p>':"");
}
async function billingImportProductsWithProgress(file,targetId){
  const target=document.getElementById(targetId),fileName=file?.name||"produits.csv";
  if(!file)throw Error("Choisissez un fichier CSV de produits.");
  billingImportProgressAt(target,"Lecture de "+fileName,12,"Vérification du séparateur et des colonnes Boulangerie…");
  const analyseBody=new FormData();analyseBody.append("file",file);analyseBody.append("kind","products");
  const analysis=await api("/api/v1/billing/import/analyze?organization_id="+encodeURIComponent(org),{method:"POST",body:analyseBody});
  const rows=Number(analysis.rows||0);
  if(!rows)throw Error("Le CSV ne contient aucun produit à importer.");
  if(analysis.errors?.length){
    const message=analysis.errors.slice(0,3).map(item=>"Ligne "+item.line+" : "+item.error).join(" · ");
    throw Error("Corrigez le CSV avant l’import. "+message);
  }
  billingImportProgressAt(target,"Produits détectés : "+rows,38,"Préparation des catégories et contrôle des doublons…");
  await billingPause(240);
  const body=new FormData();body.append("file",file);body.append("kind","products");
  let percent=49;
  const progressTimer=setInterval(()=>{
    percent=Math.min(91,percent+Math.max(1,Math.ceil((91-percent)/5)));
    billingImportProgressAt(target,"Importation des produits",percent,"Enregistrement en cours : "+rows+" ligne(s) préparée(s)…");
  },260);
  try{
    const result=await api("/api/v1/billing/import/execute?organization_id="+encodeURIComponent(org),{method:"POST",body});
    billingImportProgressAt(target,"Import terminé",100,(result.created||0)+" produit(s) enregistrés · "+(result.skipped||0)+" doublon(s) ignoré(s)");
    await billingPause(460);
    target.innerHTML=billingImportResultCard({...analysis,...result},"done")+'<p class="billing-import-success">Les produits importés restent réservés à la facturation : ils ne sont pas publiés dans la Boutique.</p>';
    return result;
  }finally{clearInterval(progressTimer)}
}
const billingClientsBase=billingClients;
billingClients=async function(...args){return billingLoading("Chargement des clients…",()=>billingClientsBase(...args))};
const billingHeadersBase=billingHeaders;
billingHeaders=async function(...args){return billingLoading("Chargement des entetes…",()=>billingHeadersBase(...args))};
const billingProductsBase=billingProducts;
billingProducts=async function(...args){return billingLoading("Chargement des produits…",()=>billingProductsBase(...args))};
const billingCategoriesBase=billingCategoryPage;
billingCategoryPage=async function(...args){return billingLoading("Chargement des categories…",()=>billingCategoriesBase(...args))};
const billingEditDocumentBase=billingEditDocument;
billingEditDocument=async function(id){const started=showFusaaOperation("Ouverture de la facture…");try{return await billingEditDocumentBase(id)}finally{await hideFusaaOperation(started)}};
const billingInvoiceDetailBase=window.openBillingInvoice;
if(billingInvoiceDetailBase)openBillingInvoice=async function(id){const started=showFusaaOperation("Chargement du document…");try{return await billingInvoiceDetailBase(id)}finally{await hideFusaaOperation(started)}};
var billingState={tab:"dashboard",page:1,productPage:1,productSearch:"",products:[],headers:[],customers:[],categories:[],selectedHeader:null,documentType:"INVOICE",editingInvoice:null};
const billingMenuLabels={dashboard:"Tableau de bord",new:"Nouvelle facture",documents:"Documents",clients:"Clients",products:"Produits",headers:"Entêtes",categories:"Catégories",reports:"Rapports",maintenance:"Maintenance",settings:"Paramètres"};
var billingLabels=billingMenuLabels;
const billingDocumentTypes={INVOICE:"Facture",QUOTE:"Devis",PROFORMA:"Facture proforma",DELIVERY_NOTE:"Bon de livraison",RECEIPT:"Reçu"};
const billingDocumentLabel=type=>billingDocumentTypes[type]||"Facture";
const billingDocumentTypeOptions=selected=>Object.entries(billingDocumentTypes).map(([value,label])=>'<option value="'+value+'" '+(value===selected?"selected":"")+'>'+label+'</option>').join("");
const billingIcon=paths=>'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+paths+'</svg>';
const billingEyeIcon=billingIcon('<path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/>');
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
  settings:billingIcon('<path d="M4 7h16M4 17h16M8 4v6m8 4v6"/><circle cx="8" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>'),
  import:billingIcon('<path d="M12 3v12m0 0 4-4m-4 4-4-4M5 18v3h14v-3"/><rect x="4" y="2" width="16" height="20" rx="3"/>')
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
  const billingRoot=document.getElementById("billing");
  if(billingRoot&&dialog.parentElement!==billingRoot)billingRoot.appendChild(dialog);
  billingState.popupTarget="billingGlassContent";if(!dialog.open)dialog.showModal();
  try{await billingOpen(tab)}finally{billingState.popupTarget=null}
}
function billingClosePopup(){const dialog=document.getElementById("billingGlassDialog");if(dialog?.open)dialog.close();billingState.popupTarget=null}
async function billingOpen(tab){
  if(!billingMenuLabels[tab])tab="dashboard";
  billingState.tab=tab;billingActive(tab);
  billingSet(billingLoadingContent(billingMenuLabels[tab]));
  try{
    if(tab==="dashboard")await billingDashboard();
    if(tab==="new")await billingNew();
    if(tab==="documents")await billingDocuments();
    if(tab==="clients")await billingClients();
    if(tab==="products")await billingProducts();
    if(tab==="headers")await billingHeaders();
    if(tab==="categories")await billingCategoryPage();
    if(tab==="reports")await billingReports();
    if(tab==="maintenance")await billingMaintenance();
    if(tab==="settings")await billingSettings();
    billingEnsureExport(tab);
  }catch(error){billingSet(billingHero(billingMenuLabels[tab],"Une erreur empêche le chargement.")+'<div class="billing-panel billing-load-error"><i>!</i><div><b>La fenêtre n’a pas pu se charger</b><p>'+esc(error.message)+'</p><button type="button" onclick="billingPopup(\''+esc(tab)+'\')">Réessayer</button></div></div>');tell(error.message)}
}
const billingOpenBase=billingOpen;
billingOpen=async function(tab){const label=billingMenuLabels[tab]||"Facturation",started=showFusaaOperation("Chargement · "+label+"…");try{return await billingOpenBase(tab)}finally{await hideFusaaOperation(started)}};
async function billingExport(kind){const started=showFusaaOperation("Preparation de l export…");try{const url="/api/v1/billing/export/"+kind+".csv?organization_id="+encodeURIComponent(org),response=await fetch(url,{headers:{Authorization:"Bearer "+token}});if(!response.ok)throw Error("Export impossible");const blob=await response.blob(),link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="fusaa-"+kind+".csv";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}}
function billingEnsureExport(tab){const kinds={documents:"documents",clients:"clients",products:"products",headers:"headers"};const kind=kinds[tab];if(!kind)return;const host=document.getElementById("billingGlassContent");const action=host?.querySelector(".billing-hero .billing-actions");if(action&&!action.querySelector("[data-billing-export]")){action.insertAdjacentHTML("beforeend",'<button class="secondary" type="button" data-billing-export onclick="billingExport(\''+kind+'\')">Exporter CSV</button>');if(tab==="clients")action.insertAdjacentHTML("beforeend",'<input id="billingClientsCsv" class="hidden" type="file" accept=".csv,text/csv" onchange="billingImportClients()"><button class="secondary" type="button" onclick="document.getElementById(\'billingClientsCsv\').click()">Importer Boulangerie</button>')}}
async function billingImportClients(){const file=document.getElementById("billingClientsCsv")?.files[0];if(!file)return;const body=new FormData();body.append("file",file);const started=showFusaaOperation("Importation des clients…");try{const result=await api("/api/v1/customers/import?organization_id="+encodeURIComponent(org),{method:"POST",body});tell(result.created+" client(s) importé(s)"+(result.errors?.length?" · "+result.errors.length+" ligne(s) ignorée(s)":""));billingClosePopup();await billingOpen("dashboard")}catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}}

async function billingDashboard(){
  const data=await api("/api/v1/billing/dashboard?organization_id="+encodeURIComponent(org));
  const cards=[
    ["new","Nouvelle facture","Créer une facture, un devis ou un reçu"],["headers","Entêtes","Nom, logo, adresse et modèle PDF"],["clients","Clients","Coordonnées et comptes clients"],["products","Produits","Catalogue partagé et import CSV"],["documents","Documents","Factures, devis et bons archivés"],["categories","Catégories","Classer les produits de facturation"],["settings","Paramètres facture","TVA, ISB, devise et préférences"],["reports","Rapports","Encaissements et soldes clients"],["maintenance","Maintenance","Contrôler et régénérer les documents"]
    ,["import","Assistant import CSV","Analyser puis importer Boulangerie sans doublons"]
  ];
  billingSet(billingHero("Facturation FUSAA","Choisissez une action. Les outils s’ouvrent dans des cartes liquid glass.",'<span class="billing-total">'+billingCurrency(data.invoiced_xof)+'</span>')+
    '<section class="billing-landing"><div class="billing-landing-intro"><div><span class="billing-eyebrow">ESPACE DE GESTION</span><h2>Tout votre atelier de facturation</h2><p>Les données Boutique et Facturation restent réunies dans le même compte FUSAA.</p></div><div class="billing-mini-stats"><span><b>'+data.invoices+'</b>Documents</span><span><b>'+data.customers+'</b>Clients</span><span><b>'+data.headers+'</b>Entêtes</span></div></div><div class="billing-card-grid">'+cards.map(([key,title,subtitle])=>'<button type="button" class="billing-glass-card '+(key==="new"?"primary":"")+'" onclick="'+(key==="import"?"billingImportAssistantOpen()":key==="new"?'billingOpen(\'new\')':'billingPopup(\''+key+'\')')+'"><i>'+billingIcons[key]+'</i><strong>'+title+'</strong><small>'+subtitle+'</small><em>Ouvrir <span>→</span></em></button>').join("")+'</div></section>');
}
function billingInvoiceTable(items){
  if(!items.length)return '<p class="billing-empty">Aucun document enregistré.</p>';
  return '<div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Numéro</th><th>Client</th><th>Type</th><th>Date</th><th>Montant</th><th>Actions</th></tr></thead><tbody>'+items.map(item=>{
    const typeId="billingDocumentType-"+item.id,itemId=esc(item.id),number=esc(item.number),selected=item.document_type||"INVOICE";
    return '<tr><td><b>'+number+'</b></td><td>'+esc(item.customer_name||item.customer||"Client comptant")+'</td><td><div class="billing-row-type"><span class="billing-type-badge">'+esc(billingDocumentLabel(item.document_type))+'</span><select id="'+typeId+'" aria-label="Type à générer pour '+number+'">'+billingDocumentTypeOptions(selected)+'</select></div></td><td>'+billingDate(item.created_at)+'</td><td>'+billingCurrency(item.total_amount)+'</td><td><button class="secondary billing-icon-button" type="button" title="Visualiser le type sélectionné" aria-label="Visualiser le PDF '+number+'" onclick="previewBillingInvoice(\''+itemId+'\',\''+number+'\',document.getElementById(\''+typeId+'\').value)">'+billingEyeIcon+'<span>Visualiser</span></button><button class="secondary" type="button" onclick="downloadBillingInvoice(\''+itemId+'\',\''+number+'\',document.getElementById(\''+typeId+'\').value)">PDF</button><button class="secondary" type="button" onclick="billingDuplicate(\''+itemId+'\',document.getElementById(\''+typeId+'\').value)">Dupliquer</button><button class="secondary" type="button" onclick="billingCompetition(\''+itemId+'\')">Concurrence</button></td></tr>'
  }).join("")+'</tbody></table></div>';
}
billingInvoiceTable=function(items){
  if(!items.length)return '<p class="billing-empty">Aucun document enregistre.</p>';
  return '<div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Numero</th><th>Client</th><th>Type</th><th>Style PDF</th><th>Date</th><th>Montant</th><th>Actions</th></tr></thead><tbody>'+items.map(item=>{
    const typeId="billingDocumentType-"+item.id,styleId="billingInvoiceStyle-"+item.id,itemId=esc(item.id),number=esc(item.number),selected=item.document_type||"INVOICE",style=item.document_style||"standard",locked=Boolean(item.source_shop_order_id)||Number(item.paid_amount||0)>0;
    const competition=item.competition_source_invoice_id?'<small class="billing-competition-mark">Concurrence +'+Number(item.competition_margin_percent||0).toLocaleString("fr-FR",{maximumFractionDigits:2})+' %</small>':"";
    const edit=locked?'<span class="muted billing-document-locked" title="Commande Boutique ou document deja paye">Verrouille</span>':'<button class="secondary" type="button" onclick="billingEditDocument(\''+itemId+'\')">Modifier</button>';
    return '<tr><td><b>'+number+'</b>'+competition+'</td><td>'+esc(item.customer_name||item.customer||"Client comptant")+'</td><td><div class="billing-row-type"><span class="billing-type-badge">'+esc(billingDocumentLabel(item.document_type))+'</span><select id="'+typeId+'" aria-label="Type a generer pour '+number+'">'+billingDocumentTypeOptions(selected)+'</select></div></td><td><div class="billing-row-style"><select id="'+styleId+'" aria-label="Style PDF pour '+number+'">'+billingHeaderStyleOptions(style)+'</select><button class="secondary" type="button" onclick="billingUpdateInvoiceStyle(\''+itemId+'\',document.getElementById(\''+styleId+'\').value)">Appliquer</button></div></td><td>'+billingDate(item.created_at)+'</td><td>'+billingCurrency(item.total_amount)+'</td><td><button class="secondary billing-icon-button" type="button" title="Visualiser le type selectionne" aria-label="Visualiser le PDF '+number+'" onclick="previewBillingInvoice(\''+itemId+'\',\''+number+'\',document.getElementById(\''+typeId+'\').value)">'+billingEyeIcon+'<span>Visualiser</span></button>'+edit+'<button class="secondary" type="button" onclick="billingDuplicate(\''+itemId+'\',document.getElementById(\''+typeId+'\').value)">Dupliquer</button><button class="secondary" type="button" onclick="billingCompetition(\''+itemId+'\')">Concurrence</button></td></tr>'
  }).join("")+'</tbody></table></div>';
};
async function billingEditDocument(id){
  try{
    const invoice=await api("/api/v1/billing/invoices/"+encodeURIComponent(id));
    if(invoice.source_shop_order_id)throw Error("La facture creee par une commande Boutique est protegee.");
    if(Number(invoice.paid_amount||0)>0)throw Error("Cette facture a un paiement enregistre. Creez plutot un avoir ou un nouveau document.");
    billingState.editingInvoice=invoice;billingState.documentType=invoice.document_type||"INVOICE";billingClosePopup();await billingOpen("new");
  }catch(error){tell(error.message)}
}
function billingCancelDocumentEdit(){billingState.editingInvoice=null;billingOpen("documents")}
async function previewBillingInvoice(id,number,documentType="INVOICE"){
  const selected=documentType||"INVOICE",started=showFusaaOperation("Génération de l’aperçu · "+billingDocumentLabel(selected)+"…");
  try{
    const response=await fetch("/api/v1/billing/invoices/"+encodeURIComponent(id)+"/pdf?document_type="+encodeURIComponent(selected),{headers:{Authorization:"Bearer "+token}});
    if(!response.ok)throw Error("Visualisation impossible");
    const url=URL.createObjectURL(await response.blob());
    const preview=window.open(url,"_blank");
    if(preview)preview.opener=null;
    else{const link=document.createElement("a");link.href=url;link.download=number+".pdf";link.click();tell("La fenêtre est bloquée : le PDF a été téléchargé.")}
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  }catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}
}
async function billingUpdateInvoiceStyle(id,style){
  const started=showFusaaOperation("Application du style PDF…");
  try{
    const saved=await api("/api/v1/billing/invoices/"+encodeURIComponent(id)+"/style",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({document_style:style})});
    tell("Style PDF appliqué à "+saved.number+". Visualisez le document pour le régénérer.");
    await billingOpen("documents");
  }catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}
}
async function billingDuplicate(id,documentType=null){const type=documentType||prompt("Type de copie : INVOICE, QUOTE, PROFORMA, DELIVERY_NOTE ou RECEIPT","QUOTE");if(type===null)return;try{const result=await api("/api/v1/billing/invoices/"+id+"/duplicate?document_type="+encodeURIComponent(type.trim().toUpperCase()),{method:"POST"});tell(result.number+" créé.");billingOpen("documents")}catch(error){tell(error.message)}}
async function billingCompetitionLegacy(id){try{const headers=await api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org));const choices=headers.map((item,index)=>(index+1)+". "+item.company_name).join("\n");const selected=prompt("Choisissez le numéro de l’entête pour le devis concurrence :\n"+choices,"1");if(selected===null)return;const header=headers[Number(selected)-1];if(!header)throw Error("Entête invalide.");const margin=prompt("Marge en pourcentage","10");if(margin===null)return;const result=await api("/api/v1/billing/invoices/"+id+"/competition",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({billing_header_id:header.id,margin_percent:Number(margin)})});tell(result.number+" créé.");billingOpen("documents")}catch(error){tell(error.message)}}

function billingCompetitionDialog(){
  let dialog=document.getElementById("billingCompetitionDialog");
  if(dialog)return dialog;
  const host=document.getElementById("billing");if(!host)throw Error("Espace de facturation indisponible.");
  host.insertAdjacentHTML("beforeend",`<dialog id="billingCompetitionDialog" class="billing-quick-dialog billing-competition-dialog"><form id="billingCompetitionForm"><div class="billing-actions billing-lines-title"><div><span class="billing-eyebrow">FACTURATION FUSAA</span><h2>Cr\u00e9er une concurrence</h2></div><button class="secondary" type="button" aria-label="Fermer" onclick="billingCompetitionClose()">\u00d7</button></div><p class="billing-competition-description">Une copie en <b>devis brouillon</b> : les quantit\u00e9s, le client, l'objet et les notes sont conserv\u00e9s. Un autre ent\u00eate et une marge sont appliqu\u00e9s \u00e0 chaque prix unitaire.</p><label>Nouvel ent\u00eate \u00e9metteur<select id="billingCompetitionHeader" required onchange="billingCompetitionRefresh()"></select></label><div><span class="billing-competition-label">Marge automatique sur les prix</span><div class="billing-competition-margins"><button type="button" data-competition-margin="5" onclick="billingCompetitionSetMargin(5,this)">+5 %</button><button type="button" data-competition-margin="10" onclick="billingCompetitionSetMargin(10,this)">+10 %</button><button type="button" data-competition-margin="15" onclick="billingCompetitionSetMargin(15,this)">+15 %</button></div></div><label>Marge personnalis\u00e9e (%)<input id="billingCompetitionMargin" type="number" min="0" max="1000" step="0.01" value="5" inputmode="decimal" oninput="billingCompetitionUseCustomMargin()"></label><section id="billingCompetitionPreview" class="billing-competition-preview" aria-live="polite"></section><div class="billing-actions billing-competition-actions"><button class="secondary" type="button" onclick="billingCompetitionClose()">Annuler</button><button id="billingCompetitionSubmit" type="submit">G\u00e9n\u00e9rer la concurrence</button></div></form></dialog>`);
  dialog=document.getElementById("billingCompetitionDialog");
  dialog.querySelector("#billingCompetitionForm").onsubmit=billingSubmitCompetition;
  dialog.addEventListener("close",()=>{billingState.competition=null});
  return dialog;
}
function billingCompetitionClose(){const dialog=document.getElementById("billingCompetitionDialog");if(dialog?.open)dialog.close()}
function billingCompetitionMargin(){const value=Number(document.getElementById("billingCompetitionMargin")?.value);return Number.isFinite(value)?value:NaN}
function billingCompetitionSetMargin(value,button){const input=document.getElementById("billingCompetitionMargin");if(input)input.value=value;document.querySelectorAll("#billingCompetitionDialog [data-competition-margin]").forEach(item=>item.classList.toggle("active",item===button));billingCompetitionRefresh()}
function billingCompetitionUseCustomMargin(){document.querySelectorAll("#billingCompetitionDialog [data-competition-margin]").forEach(item=>item.classList.remove("active"));billingCompetitionRefresh()}
function billingCompetitionRefresh(){
  const state=billingState.competition,preview=document.getElementById("billingCompetitionPreview"),select=document.getElementById("billingCompetitionHeader");if(!state||!preview||!select)return;
  const header=state.headers.find(item=>item.id===select.value),margin=billingCompetitionMargin();
  if(!header||!Number.isFinite(margin)||margin<0||margin>1000){preview.innerHTML='<p class="billing-competition-invalid">Choisissez un ent\u00eate et une marge entre 0 et 1 000 %.</p>';return}
  const originalHt=state.invoice.lines.reduce((sum,line)=>sum+Number(line.quantity||0)*Number(line.unit_amount||0),0);
  const newHt=state.invoice.lines.reduce((sum,line)=>sum+Number(line.quantity||0)*Math.round(Number(line.unit_amount||0)*(1+margin/100)*100)/100,0);
  const tax=header.isb_enabled?0:(header.tax_enabled?Math.round(newHt*Number(header.tax_rate||0))/100:0);
  const isb=header.isb_enabled?Math.round(newHt*Number(header.isb_rate||0))/100:0;
  const total=newHt+tax-isb,customer=state.invoice.customer?.name||"Client comptant";
  preview.innerHTML='<div><small>DOCUMENT ORIGINAL</small><b>'+esc(state.invoice.number)+'</b><span>'+esc(customer)+' \u00b7 '+billingCurrency(originalHt)+' HT</span></div><div><small>NOUVEL ENT\u00caTE</small><b>'+esc(header.company_name)+'</b><span>Marge appliqu\u00e9e : +'+margin.toLocaleString("fr-FR",{maximumFractionDigits:2})+' %</span></div><div class="billing-competition-total"><small>NOUVEAU TOTAL PR\u00c9VISIONNEL</small><b>'+billingCurrency(total)+'</b><span>'+billingCurrency(newHt)+' HT'+(tax?' + TVA '+billingCurrency(tax):isb?' - ISB '+billingCurrency(isb):'')+'</span></div>';
}
billingCompetition=async function(id){
  const started=showFusaaOperation("Pr\u00e9paration de la concurrence...");
  try{
    const [invoice,allHeaders]=await Promise.all([api("/api/v1/billing/invoices/"+encodeURIComponent(id)),api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org))]);
    const headers=allHeaders.filter(item=>item.id!==invoice.billing_header_id);
    if(!headers.length)throw Error("Ajoutez d'abord un autre ent\u00eate avant de cr\u00e9er une concurrence.");
    billingState.competition={invoice,headers};
    const dialog=billingCompetitionDialog(),select=dialog.querySelector("#billingCompetitionHeader");
    select.innerHTML=headers.map(item=>'<option value="'+esc(item.id)+'">'+esc(item.company_name)+(item.is_default?" (par d\u00e9faut)":"")+'</option>').join("");
    select.value=headers.find(item=>item.is_default)?.id||headers[0].id;
    billingCompetitionSetMargin(5,dialog.querySelector('[data-competition-margin="5"]'));
    if(!dialog.open)dialog.showModal();
  }catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}
};
async function billingSubmitCompetition(event){
  event.preventDefault();const state=billingState.competition,headerId=document.getElementById("billingCompetitionHeader")?.value,margin=billingCompetitionMargin();
  if(!state||!headerId)return;
  if(!Number.isFinite(margin)||margin<0||margin>1000){tell("La marge doit \u00eatre comprise entre 0 et 1 000 %.");return}
  const button=document.getElementById("billingCompetitionSubmit"),started=showFusaaOperation("G\u00e9n\u00e9ration du devis concurrence...");if(button)button.disabled=true;
  try{
    const result=await api("/api/v1/billing/invoices/"+encodeURIComponent(state.invoice.id)+"/competition",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({billing_header_id:headerId,margin_percent:margin})});
    billingCompetitionClose();billingClosePopup();
    const created=await api("/api/v1/billing/invoices/"+encodeURIComponent(result.id));
    billingState.editingInvoice=created;billingState.documentType=created.document_type||"QUOTE";
    tell(result.number+" cr\u00e9\u00e9 : vous pouvez maintenant le relire avant impression.");
    await billingOpen("new");
  }catch(error){tell(error.message)}finally{if(button)button.disabled=false;await hideFusaaOperation(started)}
}

async function billingLoadReference(){
  const [headers,customers]=await Promise.all([api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org)),api("/api/v1/customers?organization_id="+encodeURIComponent(org))]);
  billingState.headers=headers;billingState.customers=customers;
}
async function billingNew(){
  await billingLoadReference();billingState.productPage=1;billingState.productSearch="";const editing=billingState.editingInvoice;
  const documentType=billingState.documentType||"INVOICE",documentLabel=billingDocumentLabel(documentType);
  const newDocumentTitle=documentType==="INVOICE"||documentType==="PROFORMA"?"Nouvelle "+documentLabel.toLowerCase():"Nouveau "+documentLabel.toLowerCase();
  billingSet(billingHero(newDocumentTitle,"Créez un document avec l’entête et les produits de votre choix.",'<div class="billing-selected-type"><span>Type choisi</span><b>'+esc(documentLabel)+'</b><button class="secondary" type="button" onclick="billingChooseDocumentType()">Modifier</button></div>')+`
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
        <input id="billingNewCsv" class="hidden" type="file" accept=".csv,text/csv" onchange="billingQuickImportCsv()"><div id="billingNewImportStatus" class="billing-import-inline" aria-live="polite"></div>
        <div id="billingNewCatalog"></div>
      </section>
      <section class="billing-panel billing-lines-panel">
        <div class="billing-actions billing-lines-title"><h2>Lignes de facture</h2><button class="secondary" type="button" onclick="billingAddLine()">＋ Ajouter une ligne</button></div>
        <div class="billing-line-head"><span>N°</span><span>Désignation</span><span>Quantité</span><span>Prix unitaire</span><span>Actions</span></div>
        <div id="billingLines"></div><div id="billingDraftTotal" class="billing-total">Total HT : 0 FCFA</div>
        <div class="billing-actions billing-submit-row"><button type="submit" form="billingNewForm">↧ Enregistrer la facture</button></div>
      </section>
    </div>
    <form id="billingNewForm" class="billing-panel"><h2>Informations générales</h2><p class="billing-note">Le client se crée avec le bouton <b>＋ Client</b> au-dessus. Il est enregistré immédiatement dans le répertoire partagé avant d’être sélectionné pour ce document.</p><div class="billing-form-grid"><label>Date<input id="billingNewDate" type="date"></label><label>Remise FCFA<input id="billingNewDiscount" type="number" min="0" value="0"></label><label class="wide">Pour / objet<input id="billingNewSubject" placeholder="Objet du document"></label><label class="wide">Notes<textarea id="billingNewNotes" placeholder="Mentions complémentaires"></textarea></label></div></form>
    <dialog id="billingQuickProductDialog" class="billing-quick-dialog"><form method="dialog"><div class="billing-actions billing-lines-title"><h2>Ajouter un produit de facturation</h2><button class="secondary" type="submit" aria-label="Fermer">×</button></div></form><form id="billingQuickProductForm" class="billing-form-grid"><label>Désignation<input name="name" required></label><label>Prix FCFA<input name="unit_price" type="number" min="0" required></label><label>Unité<input name="unit" value="piece"></label><label>Code<input name="sku"></label><button type="submit">Enregistrer le produit</button></form></dialog>`);
  document.getElementById("billingNewHeader").value=editing?.billing_header_id||billingState.headers.find(item=>item.is_default)?.id||billingState.headers[0]?.id||"";
  document.getElementById("billingNewDate").value=editing?.issued_on?String(editing.issued_on).slice(0,10):new Date().toISOString().slice(0,10);
  if(editing){document.querySelector("#billingWorkspaceContent .billing-hero h1").textContent="Modifier "+billingDocumentLabel(documentType).toLowerCase();document.querySelector("#billingWorkspaceContent .billing-hero p").textContent="Corrigez les informations puis enregistrez la facture mise a jour.";document.getElementById("billingNewCustomer").value=editing.customer?.id||"";document.getElementById("billingNewSubject").value=editing.subject||"";document.getElementById("billingNewNotes").value=editing.notes||"";document.getElementById("billingNewDiscount").value=editing.discount_amount||0;const submit=document.querySelector("[form='billingNewForm']");if(submit)submit.textContent="Enregistrer les modifications"}
  document.getElementById("billingNewForm").onsubmit=billingSaveDocument;
  document.getElementById("billingHeaderSearch").oninput=event=>billingFilterSelect("billingNewHeader",billingState.headers,event.target.value,"company_name");
  document.getElementById("billingCustomerSearch").oninput=event=>billingFilterSelect("billingNewCustomer",billingState.customers,event.target.value,"name");
  document.getElementById("billingQuickProductForm").onsubmit=billingSaveQuickProduct;
  billingMoveCustomerFields();
  if(editing){document.querySelector(".billing-selected-type")?.insertAdjacentHTML("beforeend",'<button class="secondary" type="button" onclick="billingCancelDocumentEdit()">Annuler</button>')}
  if(editing?.lines?.length)editing.lines.forEach(line=>billingAddLine({id:line.product_id||line.shop_product_id||line.billing_product_id||"",name:line.description,quantity:line.quantity,price_xof:line.unit_amount,unit:line.unit||"piece"}));else billingAddLine();
  if(billingState.pendingAssistantDraft){const draft=billingState.pendingAssistantDraft;billingState.pendingAssistantDraft=null;billingApplyAssistantDraftToForm(draft)}
  await billingProductSearch(true);
}
function billingMoveCustomerFields(){const header=document.getElementById("billingNewHeader"),customer=document.getElementById("billingNewCustomer");if(header&&!document.getElementById("billingAddHeader")){header.insertAdjacentHTML("afterend",'<button id="billingAddHeader" class="secondary billing-quick-reference" type="button" onclick="billingHeaderQuickPopup()">＋ Entête</button>')}if(customer&&!document.getElementById("billingAddCustomer")){customer.insertAdjacentHTML("afterend",'<button id="billingAddCustomer" class="secondary billing-quick-reference" type="button" onclick="billingCustomerPopup()">＋ Client</button>')}}
function billingChooseDocumentType(){billingPopup("documents")}
function billingStartDocument(){const select=document.getElementById("billingDocumentType");billingState.editingInvoice=null;billingState.documentType=select?.value||"INVOICE";billingClosePopup();billingOpen("new")}
function billingReferenceSelect(id,items,placeholder,selected){const select=document.getElementById(id);if(!select)return;select.innerHTML=billingSelect(items,placeholder);if(selected&&items.some(item=>item.id===selected))select.value=selected}
function billingCustomerPopup(){
  let dialog=document.getElementById("billingCustomerDialog");
  if(!dialog){
    document.body.insertAdjacentHTML("beforeend",'<dialog id="billingCustomerDialog" class="billing-quick-dialog billing-reference-dialog"><div class="billing-dialog-heading"><span class="billing-eyebrow">FACTURATION FUSAA</span><button class="secondary" type="button" aria-label="Fermer" onclick="billingCustomerDialog.close()">×</button></div><form id="billingCustomerPopupForm" class="billing-form-grid"><h2 class="wide">Nouveau client</h2><p class="wide muted">La fiche est enregistrée dans le répertoire partagé, puis sélectionnée automatiquement pour cette facture.</p><label>Nom et prénom<input name="name" required maxlength="160" autocomplete="name"></label><label>Téléphone<input name="phone" maxlength="50" autocomplete="tel"></label><label>E-mail<input name="email" type="email" maxlength="320" autocomplete="email"></label><label>Adresse<input name="address" autocomplete="street-address"></label><label class="wide">Notes client<textarea name="notes" placeholder="Informations utiles pour la facturation"></textarea></label><div class="billing-actions wide"><button type="submit">Enregistrer et sélectionner</button><button class="secondary" type="button" onclick="billingCustomerDialog.close()">Annuler</button></div></form></dialog>');
    dialog=document.getElementById("billingCustomerDialog");
    document.getElementById("billingCustomerPopupForm").onsubmit=async event=>{
      event.preventDefault();const form=new FormData(event.currentTarget),started=showFusaaOperation("Enregistrement du client...");
      try{
        const saved=await api("/api/v1/customers",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:String(form.get("name")||"").trim(),phone:String(form.get("phone")||"").trim()||null,email:String(form.get("email")||"").trim()||null,address:String(form.get("address")||"").trim()||null,notes:String(form.get("notes")||"").trim()||null})});
        billingState.customers=[...billingState.customers.filter(item=>item.id!==saved.id),saved].sort((left,right)=>left.name.localeCompare(right.name,"fr"));
        billingReferenceSelect("billingNewCustomer",billingState.customers,"Nouveau ou à préciser",saved.id);
        dialog.close();event.currentTarget.reset();tell("Client enregistré et sélectionné pour le document.");
      }catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}
    };
  }
  dialog.showModal();dialog.querySelector("[name='name']")?.focus();
}
function billingHeaderStyleOptions(selected="standard"){const styles={standard:"Standard",scan_gauche:"Référence 1 · gauche",scan_alasko:"Référence 2 · Alasko",scan_centre:"Référence 3 · centre",scan_compact:"Référence 4 · compact",scan_facture_simple:"Référence 5 · facture simple",ultra_compact:"Ultra compact · 30 lignes A4",moderne_clair:"Moderne clair",moderne_bandeau:"Moderne bandeau",moderne_minimal:"Moderne minimal"};return Object.entries(styles).map(([key,label])=>'<option value="'+key+'" '+(selected===key?"selected":"")+'>'+label+'</option>').join("")}
function billingHeaderQuickPopup(){
  let dialog=document.getElementById("billingHeaderQuickDialog");
  if(!dialog){
    document.body.insertAdjacentHTML("beforeend",'<dialog id="billingHeaderQuickDialog" class="billing-quick-dialog billing-reference-dialog"><div class="billing-dialog-heading"><span class="billing-eyebrow">FACTURATION FUSAA</span><button class="secondary" type="button" aria-label="Fermer" onclick="billingHeaderQuickDialog.close()">×</button></div><form id="billingHeaderQuickForm" class="billing-form-grid"><h2 class="wide">Nouvelle entête</h2><p class="wide muted">Même modèle d’entête et mêmes options PDF que l’import Boulangerie. L’entête est enregistrée avant sa sélection dans le document.</p><label class="wide">Nom de l’entreprise<input name="company_name" required maxlength="255"></label><label class="wide">Adresse<textarea name="address"></textarea></label><label>Téléphone<input name="phone" maxlength="50"></label><label>E-mail<input name="email" type="email" maxlength="320"></label><label>NIF<input name="nif" maxlength="80"></label><label>RCCM<input name="rccm" maxlength="80"></label><label class="wide">URL du logo<input name="logo_url" type="url" placeholder="https://..."></label><label>Style PDF<select name="document_style">'+billingHeaderStyleOptions()+ '</select></label><label>Police tableau<select name="table_font_family"><option value="">Style par défaut</option><option value="times">Times</option><option value="arial">Arial</option><option value="calibri">Calibri</option><option value="segoe">Segoe</option><option value="courier">Courier</option><option value="trebuchet">Trebuchet</option></select></label><label>Taille police tableau<input name="table_font_size" type="number" min="8" max="14" step=".5" placeholder="10"></label><label>Taux TVA (%)<input name="tax_rate" type="number" min="0" max="100" step=".01" value="19"></label><label><input name="tax_enabled" type="checkbox"> TVA applicable</label><label>Taux ISB (%)<input name="isb_rate" type="number" min="0" max="100" step=".01" value="3"></label><label><input name="isb_enabled" type="checkbox"> ISB applicable</label><label class="wide"><input name="is_default" type="checkbox"> Utiliser comme entête par défaut</label><div class="billing-actions wide"><button type="submit">Enregistrer et sélectionner</button><button class="secondary" type="button" onclick="billingHeaderQuickDialog.close()">Annuler</button></div></form></dialog>');
    dialog=document.getElementById("billingHeaderQuickDialog");
    document.getElementById("billingHeaderQuickForm").onsubmit=async event=>{
      event.preventDefault();const form=new FormData(event.currentTarget),started=showFusaaOperation("Enregistrement de l’entête...");
      const value=name=>String(form.get(name)||"").trim()||null;
      try{
        const saved=await api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({company_name:value("company_name"),address:value("address"),phone:value("phone"),email:value("email"),nif:value("nif"),rccm:value("rccm"),logo_url:value("logo_url"),document_style:form.get("document_style"),table_font_family:value("table_font_family"),table_font_size:value("table_font_size")?Number(value("table_font_size")):null,tax_enabled:form.has("tax_enabled"),tax_rate:Number(form.get("tax_rate")||0),isb_enabled:form.has("isb_enabled"),isb_rate:Number(form.get("isb_rate")||0),is_default:form.has("is_default")})});
        billingState.headers=[...billingState.headers.filter(item=>item.id!==saved.id),saved].sort((left,right)=>left.company_name.localeCompare(right.company_name,"fr"));billingState.selectedHeader=saved.id;
        billingReferenceSelect("billingNewHeader",billingState.headers,"Choisir dans la demande",saved.id);
        dialog.close();event.currentTarget.reset();tell("Entête enregistrée et sélectionnée pour le document.");
      }catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}
    };
  }
  dialog.showModal();dialog.querySelector("[name='company_name']")?.focus();
}
function billingFacturationAssistantContext(){return {billing_header_id:document.getElementById("billingNewHeader")?.value||null,customer_id:document.getElementById("billingNewCustomer")?.value||null}}
function billingAskAi(){billingFacturationAssistantOpen(document.getElementById("billingAiPrompt")?.value.trim()||"")}
function billingFacturationAssistantOpen(prefill=""){
  let dialog=document.getElementById("billingFacturationAssistantDialog");
  if(!dialog){
    document.body.insertAdjacentHTML("beforeend",'<dialog id="billingFacturationAssistantDialog" class="billing-assistant-dialog"><div class="billing-assistant-head"><div><span class="billing-eyebrow">AGENT SECONDAIRE · FACTURATION</span><h2>Assistant IA de facturation</h2></div><button class="secondary" type="button" aria-label="Fermer" onclick="billingFacturationAssistantDialog.close()">×</button></div><div class="billing-assistant-context" id="billingAssistantContext"></div><div id="billingAssistantMessages" class="billing-assistant-messages" aria-live="polite"></div><div class="billing-assistant-suggestions"><button class="secondary" type="button" onclick="billingFacturationAssistantSuggest(\'Fais un devis avec les produits disponibles\')">Créer un devis</button><button class="secondary" type="button" onclick="billingFacturationAssistantSuggest(\'Liste les produits disponibles\')">Produits</button><button class="secondary" type="button" onclick="billingFacturationAssistantSuggest(\'Explique les types de document\')">Types de document</button></div><form id="billingAssistantForm" class="billing-assistant-composer"><input id="billingAssistantInput" autocomplete="off" placeholder="Ex. Fais une proforma : 2 x Ramette A4 à 3 500"><button type="submit">Envoyer ↑</button></form><p class="muted billing-assistant-foot">Cet assistant est réservé à la facturation. Il prépare un brouillon depuis vos données FUSAA ; aucun document n’est enregistré sans validation.</p></dialog>');
    dialog=document.getElementById("billingFacturationAssistantDialog");
    document.getElementById("billingAssistantForm").onsubmit=event=>{event.preventDefault();billingFacturationAssistantSend(document.getElementById("billingAssistantInput").value)};
  }
  const context=billingFacturationAssistantContext(),header=billingState.headers.find(item=>item.id===context.billing_header_id),customer=billingState.customers.find(item=>item.id===context.customer_id);
  document.getElementById("billingAssistantContext").innerHTML='<span>Entête <b>'+esc(header?.company_name||"à choisir")+'</b></span><span>Client <b>'+esc(customer?.name||"à choisir")+'</b></span>';
  document.getElementById("billingAssistantMessages").innerHTML='<article class="billing-assistant-message assistant"><b>Assistant Facturation FUSAA</b><p>Je suis distinct de l’assistant Boutique. Je peux préparer une facture, un devis, une proforma, un bon de livraison ou un reçu à partir du catalogue et du client choisis.</p></article>';
  dialog.showModal();document.getElementById("billingAssistantInput").value=prefill;document.getElementById("billingAssistantInput").focus();if(prefill)billingFacturationAssistantSend(prefill);
}
function billingFacturationAssistantSuggest(text){const input=document.getElementById("billingAssistantInput");if(input){input.value=text;billingFacturationAssistantSend(text)}}
function billingFacturationAssistantMessage(role,title,text,draft){const target=document.getElementById("billingAssistantMessages");if(!target)return;const body=esc(text||"").replace(/\\n/g,"<br>");let draftHtml="";if(draft){const lines=draft.lines.map(line=>'<li>'+esc(line.description)+' · '+esc(line.quantity)+' × '+billingCurrency(line.unit_amount)+'</li>').join("");draftHtml='<section class="billing-assistant-draft"><span class="billing-type-badge">'+esc(billingDocumentLabel(draft.document_type))+'</span><strong>Total : '+billingCurrency(draft.total_amount)+'</strong><ul>'+lines+'</ul><button type="button" onclick="billingFacturationAssistantApplyDraft()">Appliquer au brouillon</button></section>'}target.insertAdjacentHTML("beforeend",'<article class="billing-assistant-message '+role+'"><b>'+esc(title)+'</b><p>'+body+'</p>'+draftHtml+'</article>');target.scrollTop=target.scrollHeight}
async function billingFacturationAssistantSend(message){const text=String(message||"").trim();if(!text)return;const input=document.getElementById("billingAssistantInput"),messages=document.getElementById("billingAssistantMessages");billingFacturationAssistantMessage("user","Vous",text);if(input){input.value="";input.disabled=true}messages?.insertAdjacentHTML("beforeend",'<article id="billingAssistantTyping" class="billing-assistant-typing"><i></i><i></i><i></i> Analyse du catalogue et du brouillon…</article>');try{const data=await api("/api/v1/billing/assistant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,message:text,...billingFacturationAssistantContext()})});billingState.assistantDraft=data.draft||null;billingFacturationAssistantMessage("assistant",data.title||"Assistant Facturation",data.answer||"",data.draft||null)}catch(error){billingFacturationAssistantMessage("assistant","Assistant Facturation",error.message||"La demande n’a pas pu être traitée.")}finally{document.getElementById("billingAssistantTyping")?.remove();if(input){input.disabled=false;input.focus()}}}
async function billingFacturationAssistantApplyDraft(){const draft=billingState.assistantDraft;if(!draft){tell("Aucun brouillon IA à appliquer.");return}billingState.documentType=draft.document_type||"INVOICE";billingState.pendingAssistantDraft=draft;billingState.editingInvoice=null;document.getElementById("billingFacturationAssistantDialog")?.close();await billingOpen("new");tell("Brouillon IA appliqué. Vérifiez les lignes puis enregistrez le document.")}
function billingApplyAssistantDraftToForm(draft){if(!draft)return;billingReferenceSelect("billingNewHeader",billingState.headers,"Choisir dans la demande",draft.billing_header_id);billingReferenceSelect("billingNewCustomer",billingState.customers,"Nouveau ou à préciser",draft.customer_id);document.getElementById("billingNewSubject").value=draft.subject||"";document.getElementById("billingNewNotes").value=draft.notes||"";const box=document.getElementById("billingLines");if(box)box.innerHTML="";(draft.lines||[]).forEach(line=>billingAddLine({id:line.product_id,name:line.description,quantity:line.quantity,price_xof:line.unit_amount,unit:line.unit||"piece"}));billingUpdateTotal()}

const billingImportSlots=[
  ["headers","Entêtes / entreprises","facturation_entreprises.csv","Nom, adresse, téléphone, NIF, RCCM et styles PDF"],
  ["clients","Clients","facturation_clients.csv","Clients, téléphone, e-mail, adresse et notes"],
  ["categories","Catégories","facturation_categories.csv","Catégories avant les produits"],
  ["products","Produits de facturation","facturation_produits.csv","Produits internes uniquement : jamais ajoutés à la Boutique"],
  ["invoices","Historique des factures","facturation_factures.csv","Numéro, client, entête, date, statut et total"]
];
function billingImportAssistantOpen(){
  let dialog=document.getElementById("billingImportAssistantDialog");
  if(!dialog){
    document.body.insertAdjacentHTML("beforeend",'<dialog id="billingImportAssistantDialog" class="billing-import-dialog"><div class="billing-assistant-head"><div><span class="billing-eyebrow">ASSISTANT D’IMPORT · FACTURATION</span><h2>Importer les exports Boulangerie</h2></div><button class="secondary" type="button" aria-label="Fermer" onclick="billingImportAssistantDialog.close()">×</button></div><div class="billing-import-body"><p class="billing-note">Choisissez un ou plusieurs CSV. L’assistant les analyse d’abord : séparateur <b>;</b> ou <b>,</b>, colonnes et aperçu. Rien n’est enregistré avant le clic sur <b>Importer les fichiers analysés</b>.</p><div class="billing-import-slots">'+billingImportSlots.map(([kind,title,example,description])=>'<label class="billing-import-slot"><span><b>'+title+'</b><small>'+description+'<br>Exemple : '+example+'</small></span><input id="billingImportFile-'+kind+'" data-import-kind="'+kind+'" type="file" accept=".csv,text/csv"></label>').join("")+'</div><div class="billing-actions billing-import-actions"><button type="button" onclick="billingImportAssistantAnalyze()">Analyser les CSV</button><button id="billingImportExecute" class="secondary" type="button" disabled onclick="billingImportAssistantExecute()">Importer les fichiers analysés</button></div><div id="billingImportResults" class="billing-import-results" aria-live="polite"><p class="muted">Ajoutez les CSV puis lancez l’analyse.</p></div></div></dialog>');
    dialog=document.getElementById("billingImportAssistantDialog");
  }
  billingState.importAnalysis={};dialog.showModal();
}
function billingImportFiles(){return [...document.querySelectorAll("#billingImportAssistantDialog input[type='file']")].map(input=>({slot:input.dataset.importKind,file:input.files?.[0]||null})).filter(item=>item.file)}
function billingImportResultCard(result,state="analysis"){const warning=result.warning?'<p class="billing-import-warning">⚠ '+esc(result.warning)+'</p>':"";const errors=result.errors?.length?'<p class="billing-import-error">'+result.errors.map(item=>'Ligne '+esc(item.line)+': '+esc(item.error)).join('<br>')+'</p>':"";const counters=state==="done"?'<div class="billing-import-counts"><span>Créés <b>'+Number(result.created||0)+'</b></span><span>Doublons ignorés <b>'+Number(result.skipped||0)+'</b></span></div>':'<div class="billing-import-counts"><span>'+Number(result.rows||0)+' ligne(s)</span><span>Séparateur : '+esc(result.delimiter||"—")+'</span><span>Doublons : '+Number(result.duplicates||0)+'</span></div>';const samples=result.samples?.length?'<ul>'+result.samples.map(sample=>'<li>'+esc(Object.values(sample).filter(value=>value!==undefined&&value!=="").join(" · "))+'</li>').join("")+'</ul>':"";return '<article class="billing-import-result '+state+'"><div><span class="billing-type-badge">'+esc(result.kind||"CSV")+'</span><b>'+esc(result.filename||result.kind||"CSV")+'</b></div>'+counters+warning+errors+samples+'</article>'}
async function billingImportAssistantAnalyze(){
  const files=billingImportFiles(),target=document.getElementById("billingImportResults");if(!files.length){tell("Choisissez au moins un CSV Boulangerie.");return}
  billingState.importAnalysis={};target.innerHTML='<p class="billing-assistant-typing"><i></i><i></i><i></i> Analyse des fichiers CSV…</p>';const cards=[];
  for(const item of files){const body=new FormData();body.append("file",item.file);body.append("kind",item.slot);try{const result=await api("/api/v1/billing/import/analyze?organization_id="+encodeURIComponent(org),{method:"POST",body});billingState.importAnalysis[item.slot]={file:item.file,kind:result.kind,result};cards.push(billingImportResultCard(result))}catch(error){cards.push('<article class="billing-import-result error"><b>'+esc(item.file.name)+'</b><p>'+esc(error.message)+'</p></article>')}}
  target.innerHTML=cards.join("")||'<p class="muted">Aucun fichier analysable.</p>';document.getElementById("billingImportExecute").disabled=!Object.keys(billingState.importAnalysis).length;
}
async function billingImportAssistantExecute(){
  const analysis=billingState.importAnalysis||{},target=document.getElementById("billingImportResults"),order=["headers","clients","categories","products","invoices"],entries=order.map(slot=>analysis[slot]).filter(Boolean);if(!entries.length){tell("Analysez les fichiers avant de les importer.");return}
  const button=document.getElementById("billingImportExecute"),dialog=document.getElementById("billingImportAssistantDialog"),started=showFusaaOperation("Import Boulangerie en cours…");button.disabled=true;target.innerHTML=billingImportProgress("Initialisation de l’import…",6);const cards=[];
  try{for(const [index,item] of entries.entries()){const progress=10+Math.round((index/entries.length)*78);target.innerHTML=billingImportProgress("Importation : "+item.file.name,progress);await billingPause(180);const body=new FormData();body.append("file",item.file);body.append("kind",item.kind);const result=await api("/api/v1/billing/import/execute?organization_id="+encodeURIComponent(org),{method:"POST",body});cards.push(billingImportResultCard(result,"done"))}await billingLoadReference();target.innerHTML=billingImportProgress("Import terminé · données enregistrées",100);await billingPause(850);dialog?.close();await billingOpen("dashboard");tell("Import Boulangerie terminé. Les compteurs Facturation ont été actualisés.")}catch(error){target.innerHTML='<article class="billing-import-result error"><b>Import interrompu</b><p>'+esc(error.message)+'</p></article>';tell(error.message)}finally{button.disabled=false;await hideFusaaOperation(started)}
}
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
  const started=showFusaaOperation("Importation des produits…");try{const result=await billingImportProductsWithProgress(file,"billingNewImportStatus");tell(result.created+" produit(s) importé(s) pour la facturation.");await billingProductSearch(true)}catch(error){document.getElementById("billingNewImportStatus").innerHTML='<p class="billing-import-error">'+esc(error.message)+'</p>';tell(error.message)}finally{await hideFusaaOperation(started)}
}
function billingAddLine(item){
  const box=document.getElementById("billingLines");if(!box)return;
  const row=document.createElement("div");row.className="billing-line";row.dataset.productId=item?.id||"";row.dataset.unit=item?.unit||"piece";
  row.innerHTML='<span class="billing-line-number"></span><input class="bill-designation" placeholder="Désignation" required value="'+esc(item?.name||"")+'"><input class="bill-quantity" type="number" min="0.01" step="0.01" value="'+esc(item?.quantity??1)+'" aria-label="Quantité"><input class="bill-price" type="number" min="0" step="0.01" value="'+esc(item?.price_xof??"")+'" placeholder="Prix" aria-label="Prix unitaire"><button class="danger" type="button" aria-label="Supprimer la ligne">×</button>';
  const removeButton=row.querySelector("button");removeButton.onclick=()=>{row.remove();billingUpdateTotal()};removeButton.insertAdjacentHTML("beforebegin",'<button class="secondary" type="button" aria-label="Enregistrer ce produit">＋</button>');row.querySelector("button.secondary").onclick=()=>billingSaveLineProduct(row);row.querySelectorAll("input").forEach(input=>input.addEventListener("input",billingUpdateTotal));box.append(row);billingUpdateTotal();
}
function billingSaveLineProduct(row){const name=row.querySelector(".bill-designation")?.value.trim(),price=Number(row.querySelector(".bill-price")?.value);if(!name||!Number.isFinite(price)){tell("Renseignez la désignation et le prix du produit.");return}billingQuickProduct();const form=document.getElementById("billingQuickProductForm");form.querySelector('[name="name"]').value=name;form.querySelector('[name="unit_price"]').value=price;window.billingLineTarget=row}
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
  const body={organization_id:org,billing_header_id:document.getElementById("billingNewHeader").value,customer_id:customerId||null,customer_name:customerId?null:document.getElementById("billingNewCustomerName").value.trim(),customer_phone:document.getElementById("billingNewCustomerPhone").value.trim()||null,customer_address:document.getElementById("billingNewCustomerAddress").value.trim()||null,issued_on:document.getElementById("billingNewDate").value+"T12:00:00Z",document_type:billingState.documentType||"INVOICE",subject:document.getElementById("billingNewSubject").value.trim()||null,notes:document.getElementById("billingNewNotes").value.trim()||null,discount_amount:Number(document.getElementById("billingNewDiscount").value||0),lines};
  try{const result=await api("/api/v1/billing/documents",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});tell(result.number+" enregistré.");await billingOpen("documents");openBillingInvoice(result.id)}catch(error){tell(error.message)}
}

billingSaveDocument=async function(event){
  event.preventDefault();const rows=[...document.querySelectorAll("#billingLines .billing-line")];
  const lines=rows.map(row=>({product_id:row.dataset.productId||null,description:row.querySelector(".bill-designation").value.trim(),quantity:Number(row.querySelector(".bill-quantity").value),unit_amount:Number(row.querySelector(".bill-price").value),unit:row.dataset.unit||"piece"})).filter(item=>item.description);
  if(!lines.length){tell("Ajoutez au moins une ligne.");return}
  const headerId=document.getElementById("billingNewHeader").value;if(!headerId){tell("Choisissez une entete d entreprise.");document.getElementById("billingNewHeader").focus();return}
  const customerId=document.getElementById("billingNewCustomer").value,editing=billingState.editingInvoice;
  const body={organization_id:org,billing_header_id:headerId,customer_id:customerId||null,customer_name:null,customer_phone:null,customer_address:null,issued_on:document.getElementById("billingNewDate").value+"T12:00:00Z",document_type:billingState.documentType||"INVOICE",subject:document.getElementById("billingNewSubject").value.trim()||null,notes:document.getElementById("billingNewNotes").value.trim()||null,discount_amount:Number(document.getElementById("billingNewDiscount").value||0),lines};
  const started=showFusaaOperation(editing?"Mise a jour de la facture...":"Enregistrement de la facture...");
  try{
    const result=await api(editing?"/api/v1/billing/invoices/"+encodeURIComponent(editing.id):"/api/v1/billing/documents",{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    billingState.editingInvoice=null;tell(result.number+(editing?" modifiee.":" enregistre."));await billingOpen("documents");openBillingInvoice(result.id);
  }catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}
};
async function billingDocuments(){
  const documentPageSize=12,items=await api("/api/v1/billing/invoices?organization_id="+encodeURIComponent(org)+"&page="+billingState.page+"&page_size="+documentPageSize);
  billingSet(billingHero("Documents","Chaque ligne possède son type de génération. L’aperçu et le PDF utilisent ce choix sans modifier le document enregistré.",'<label class="billing-document-picker">Type du nouveau document<select id="billingDocumentType" onchange="billingState.documentType=this.value">'+billingDocumentTypeOptions(billingState.documentType||"INVOICE")+'</select></label><button type="button" onclick="billingStartDocument()">+ Créer le document</button>')+
    '<section class="billing-panel">'+billingInvoiceTable(items)+'<div class="billing-pagination"><button class="secondary" type="button" '+(billingState.page<=1?"disabled":"")+' onclick="billingState.page--;billingOpen(\'documents\')">← Précédent</button><span>Page '+billingState.page+'</span><button class="secondary" type="button" '+(items.length<25?"disabled":"")+' onclick="billingState.page++;billingOpen(\'documents\')">Suivant →</button></div></section>');
}

billingDocuments=async function(){
  const pageSize=12,items=await api("/api/v1/billing/invoices?organization_id="+encodeURIComponent(org)+"&page="+billingState.page+"&page_size="+pageSize);
  billingSet(billingHero("Documents","Liste allegee : seuls les documents de cette page sont charges. Le PDF est genere uniquement si vous le demandez.",'<label class="billing-document-picker">Type du nouveau document<select id="billingDocumentType" onchange="billingState.documentType=this.value">'+billingDocumentTypeOptions(billingState.documentType||"INVOICE")+'</select></label><button type="button" onclick="billingStartDocument()">+ Creer le document</button>')+'<section class="billing-panel">'+billingInvoiceTable(items)+'<div class="billing-pagination"><button class="secondary" type="button" '+(billingState.page<=1?"disabled":"")+' onclick="billingState.page--;billingOpen(\'documents\')">Precedent</button><span>Page '+billingState.page+'</span><button class="secondary" type="button" '+(items.length<pageSize?"disabled":"")+' onclick="billingState.page++;billingOpen(\'documents\')">Suivant</button></div></section>');
};
async function billingClients(){
  const items=await billingRequest("/api/v1/customers?organization_id="+encodeURIComponent(org));billingState.customers=items;
  billingSet(billingHero("Clients","Répertoire partagé par la Boutique et la facturation.")+'<section class="billing-panel"><h2>Ajouter un client</h2><form id="billClientForm" class="billing-form-grid"><label>Nom<input name="name" required></label><label>Téléphone<input name="phone"></label><label>E-mail<input name="email" type="email"></label><label>Adresse<input name="address"></label><button>Ajouter</button></form></section><section class="billing-panel"><h2>Comptes clients</h2><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Nom</th><th>Téléphone</th><th>E-mail</th><th>Actions</th></tr></thead><tbody>'+items.map(item=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.phone||"—")+'</td><td>'+esc(item.email||"—")+'</td><td><button class="secondary" type="button" onclick="billingEditClient(\''+esc(item.id)+'\')">Modifier</button><button class="danger" type="button" onclick="billingRemoveClient(\''+esc(item.id)+'\')">Supprimer</button></td></tr>').join("")+'</tbody></table></div></section>');
  document.getElementById("billClientForm").onsubmit=async event=>{event.preventDefault();const form=new FormData(event.target);try{await api("/api/v1/customers",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:form.get("name"),phone:form.get("phone")||null,email:form.get("email")||null,address:form.get("address")||null})});tell("Client ajouté.");billingClients()}catch(error){tell(error.message)}};
}
async function billingEditClient(id){const item=billingState.customers.find(value=>value.id===id);if(!item)return;const name=prompt("Nom",item.name);if(name===null||!name.trim())return;const phone=prompt("Téléphone",item.phone||"");if(phone===null)return;try{await api("/api/v1/billing/customers/"+id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({...item,organization_id:org,name:name.trim(),phone:phone.trim()||null})});tell("Client modifié.");billingClients()}catch(error){tell(error.message)}}
async function billingRemoveClient(id){if(!confirm("Supprimer ce client ? Son historique de factures sera protégé."))return;try{await api("/api/v1/billing/customers/"+id+"?organization_id="+encodeURIComponent(org),{method:"DELETE"});tell("Client supprimé.");billingClients()}catch(error){tell(error.message)}}

async function billingProducts(){
  const [categories,data]=await Promise.all([api("/api/v1/billing/categories?organization_id="+encodeURIComponent(org)),api("/api/v1/billing/catalog/page?organization_id="+encodeURIComponent(org)+"&page="+billingState.productPage+"&page_size=20&q="+encodeURIComponent(billingState.productSearch))]);
  billingState.categories=categories;billingState.products=data.items;
  billingSet(billingHero("Produits","Le catalogue de facturation réunit les articles Boutique et les articles internes.",'<button type="button" onclick="billingOpen(\'new\')">+ Nouvelle facture</button>')+
    '<section class="billing-panel"><h2>Ajouter un produit réservé à la facturation</h2><form id="billProductForm" class="billing-form-grid"><label>Désignation<input name="name" required></label><label>Prix FCFA<input name="unit_price" type="number" min="0" required></label><label>Code<input name="sku"></label><label>Catégorie<select name="billing_category_id">'+billingSelect(categories,"Sans catégorie")+'</select></label><label>Unité<input name="unit" value="piece"></label><label>Stock initial<input name="stock_quantity" type="number" min="0" value="0"></label><label>Seuil d’alerte<input name="stock_minimum" type="number" min="0" value="3"></label><label>Coût d’achat<input name="cost_xof" type="number" min="0" value="0"></label><button>Enregistrer le produit</button></form><div class="billing-actions"><input id="billCsvFile" type="file" accept=".csv,text/csv"><button class="secondary" type="button" onclick="billingImportCsv()">Importer la liste CSV</button></div><div id="billProductImportStatus" class="billing-import-inline" aria-live="polite"></div></section>'+
    '<section class="billing-panel"><div class="billing-toolbar"><input id="billProductsSearch" placeholder="Rechercher" value="'+esc(billingState.productSearch)+'"><button class="secondary" type="button" onclick="billingState.productSearch=document.getElementById(\'billProductsSearch\').value.trim();billingState.productPage=1;billingProducts()">Rechercher</button></div><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Produit</th><th>Source</th><th>Prix</th><th>Stock</th><th>Actions</th></tr></thead><tbody>'+data.items.map((item,index)=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.source)+'</td><td>'+billingCurrency(item.price_xof)+'</td><td>'+esc(item.stock_quantity)+'</td><td>'+(item.source==="FACTURATION"?'<button class="secondary" type="button" onclick="billingEditProduct('+index+')">Modifier</button><button class="danger" type="button" onclick="billingRemoveProduct('+index+')">Archiver</button>':'<span class="muted">Gérer dans Boutique</span>')+'</td></tr>').join("")+'</tbody></table></div><div class="billing-pagination"><button class="secondary" type="button" '+(data.page<=1?"disabled":"")+' onclick="billingState.productPage--;billingProducts()">←</button><span>'+data.page+' / '+Math.max(1,Math.ceil(data.total/20))+'</span><button class="secondary" type="button" '+(!data.has_more?"disabled":"")+' onclick="billingState.productPage++;billingProducts()">→</button></div></section>');
  document.getElementById("billProductForm").onsubmit=async event=>{event.preventDefault();const f=new FormData(event.target);try{await api("/api/v1/billing/products",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:f.get("name"),unit_price:Number(f.get("unit_price")),sku:f.get("sku")||null,billing_category_id:f.get("billing_category_id")||null,unit:f.get("unit")||"piece",stock_quantity:Number(f.get("stock_quantity")||0),stock_minimum:Number(f.get("stock_minimum")||3),cost_xof:Number(f.get("cost_xof")||0)})});tell("Produit enregistré.");billingProducts()}catch(error){tell(error.message)}};
}
async function billingImportCsv(){const file=document.getElementById("billCsvFile")?.files[0];if(!file){tell("Choisissez un fichier CSV.");return}const started=showFusaaOperation("Importation des produits…");try{const result=await billingImportProductsWithProgress(file,"billProductImportStatus");tell(result.created+" produit(s) importé(s)"+(result.errors.length?" · "+result.errors.length+" ligne(s) ignorée(s)":""));await billingPause(650);await billingProducts()}catch(error){const target=document.getElementById("billProductImportStatus");if(target)target.innerHTML='<p class="billing-import-error">'+esc(error.message)+'</p>';tell(error.message)}finally{await hideFusaaOperation(started)}}
async function billingEditProduct(index){const item=billingState.products[index];if(!item||item.source!=="FACTURATION")return;const name=prompt("Désignation",item.name);if(name===null||!name.trim())return;const price=prompt("Prix FCFA",item.price_xof);if(price===null)return;try{await api("/api/v1/billing/products/"+item.id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:name.trim(),unit_price:Number(price),sku:item.sku,billing_category_id:item.billing_category_id,unit:item.unit,stock_quantity:item.stock_quantity,stock_minimum:item.stock_minimum,cost_xof:item.cost_xof})});tell("Produit modifié.");billingProducts()}catch(error){tell(error.message)}}
async function billingRemoveProduct(index){const item=billingState.products[index];if(!item||!confirm("Archiver ce produit de facturation ?"))return;try{await api("/api/v1/billing/products/"+item.id,{method:"DELETE"});tell("Produit archivé ; les anciennes factures sont conservées.");billingProducts()}catch(error){tell(error.message)}}

async function billingHeaders(){
  const items=await api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org));billingState.headers=items;
  const current=items.find(item=>item.id===billingState.selectedHeader)||items.find(item=>item.is_default)||items[0];billingState.selectedHeader=current?.id||null;
  billingSet(billingHero("Entêtes d’entreprise","Les coordonnées, la TVA ou l’ISB et le style choisis apparaissent sur les PDF.")+
    '<div class="billing-split"><section class="billing-panel"><div class="billing-actions" style="justify-content:space-between"><h2>Entêtes disponibles</h2><button class="secondary" type="button" onclick="billingState.selectedHeader=null;billingHeaderForm(null)">+ Ajouter</button></div>'+items.map(item=>'<button class="billing-kpi" style="min-height:70px;margin:5px 0" type="button" onclick="billingState.selectedHeader=\''+esc(item.id)+'\';billingHeaderForm(billingState.headers.find(h=>h.id===billingState.selectedHeader))"><b style="font-size:1rem">'+esc(item.company_name)+'</b><small>'+esc(item.document_style)+(item.is_default?" · Par défaut":"")+'</small></button>').join("")+'</section><section id="billingHeaderFormHost" class="billing-panel"></section></div>');
  billingHeaderForm(current);
  const headerTools=document.querySelector("#billingGlassContent .billing-split > section:first-child .billing-actions");
  if(headerTools&&!document.getElementById("billingHeadersCsv"))headerTools.insertAdjacentHTML("beforeend",'<input id="billingHeadersCsv" class="hidden" type="file" accept=".csv,text/csv" onchange="billingImportHeaders()"><button class="secondary" type="button" onclick="document.getElementById(\'billingHeadersCsv\').click()">Importer Boulangerie (CSV)</button>');
}
async function billingImportHeaders(){const file=document.getElementById("billingHeadersCsv")?.files[0];if(!file)return;const body=new FormData();body.append("file",file);const started=showFusaaOperation("Importation des entêtes…");try{const result=await api("/api/v1/billing/headers/import?organization_id="+encodeURIComponent(org),{method:"POST",body});tell(result.created+" entête(s) importée(s)"+(result.errors?.length?" · "+result.errors.length+" ligne(s) ignorée(s)":""));billingClosePopup();await billingOpen("dashboard")}catch(error){tell(error.message)}finally{await hideFusaaOperation(started)}}
function billingHeaderForm(item){const host=document.getElementById("billingHeaderFormHost");if(!host)return;const styles={standard:"Standard",scan_gauche:"Référence 1 · gauche",scan_alasko:"Référence 2 · Alasko",scan_centre:"Référence 3 · centre",scan_compact:"Référence 4 · compact",scan_facture_simple:"Référence 5 · facture simple",ultra_compact:"Ultra compact · 30 lignes A4",moderne_clair:"Moderne clair",moderne_bandeau:"Moderne bandeau",moderne_minimal:"Moderne minimal"};
  host.innerHTML='<h2>'+(item?"Modifier l’entête":"Nouvel entête")+'</h2><form id="billHeaderForm" class="billing-form-grid"><label class="wide">URL du logo (facultative)<input name="logo_url" value="'+esc(item?.logo_url?.startsWith("storage://")?"":item?.logo_url||"")+'" placeholder="https://…"></label><label class="wide">Nom de l’entreprise<input name="company_name" required value="'+esc(item?.company_name||"")+'"></label><label class="wide">Adresse<textarea name="address">'+esc(item?.address||"")+'</textarea></label><label>Téléphone<input name="phone" value="'+esc(item?.phone||"")+'"></label><label>E-mail<input name="email" type="email" value="'+esc(item?.email||"")+'"></label><label>NIF<input name="nif" value="'+esc(item?.nif||"")+'"></label><label>RCCM<input name="rccm" value="'+esc(item?.rccm||"")+'"></label><label>Style PDF<select name="document_style">'+Object.entries(styles).map(([key,label])=>'<option value="'+key+'" '+(item?.document_style===key?"selected":"")+'>'+label+'</option>').join("")+'</select></label><label>Police du tableau<select name="table_font_family">'+["","times","arial","calibri","segoe","courier","trebuchet"].map(font=>'<option value="'+font+'" '+(item?.table_font_family===font?"selected":"")+'>'+(font||"Style par défaut")+'</option>').join("")+'</select></label><label>Taille police du tableau<input name="table_font_size" type="number" min="8" max="14" step=".5" value="'+esc(item?.table_font_size??"")+'"></label><label>Taux TVA (%)<input name="tax_rate" type="number" min="0" max="100" step=".01" value="'+esc(item?.tax_rate??19)+'"></label><label><input name="tax_enabled" type="checkbox" '+(item?.tax_enabled?"checked":"")+'> TVA applicable</label><label>Taux ISB (%)<input name="isb_rate" type="number" min="0" max="100" step=".01" value="'+esc(item?.isb_rate??3)+'"></label><label><input name="isb_enabled" type="checkbox" '+(item?.isb_enabled?"checked":"")+'> ISB applicable</label><label><input name="is_default" type="checkbox" '+(item?.is_default?"checked":"")+'> Entête par défaut</label><div class="billing-actions wide"><button>Enregistrer l’entête</button>'+(item?'<button class="danger" type="button" onclick="billingDeleteHeader(\''+esc(item.id)+'\')">Supprimer</button>':"")+'</div></form>';
  const logoField=host.querySelector('input[name="logo_url"]').closest("label");
  logoField.insertAdjacentHTML("afterend",item?'<div class="billing-header-logo wide">'+(item.logo_preview_url||item.logo_url?'<img src="'+esc(item.logo_preview_url||item.logo_url)+'" alt="Logo de '+esc(item.company_name)+'">':'<span class="muted">Aucun logo enregistré</span>')+'<div><label>Importer un logo (PNG, JPEG ou WebP)<input id="billingHeaderLogoFile" type="file" accept="image/png,image/jpeg,image/webp"></label><button class="secondary" type="button" onclick="billingUploadHeaderLogo(\''+esc(item.id)+'\')">Envoyer le logo</button></div></div>':'<p class="muted wide">Enregistrez l’entête, puis importez son logo.</p>');
  const headerForm=document.getElementById("billHeaderForm");headerForm.dataset.existingLogoUrl=item?.logo_url||"";headerForm.onsubmit=event=>billingSaveHeader(event,item?.id||null);
}
async function billingUploadHeaderLogo(id){
  const file=document.getElementById("billingHeaderLogoFile")?.files[0];if(!file){tell("Choisissez un logo.");return}
  const body=new FormData();body.append("file",file);
  try{await api("/api/v1/billing/headers/"+encodeURIComponent(id)+"/logo",{method:"POST",body});tell("Logo enregistré sur l’entête.");await billingHeaders()}catch(error){tell(error.message)}
}
async function billingSaveHeader(event,id){event.preventDefault();const f=new FormData(event.target);const body={company_name:String(f.get("company_name")).trim(),address:f.get("address")||null,phone:f.get("phone")||null,email:f.get("email")||null,nif:f.get("nif")||null,rccm:f.get("rccm")||null,logo_url:f.get("logo_url")||event.target.dataset.existingLogoUrl||null,document_style:f.get("document_style"),table_font_family:f.get("table_font_family")||null,table_font_size:f.get("table_font_size")?Number(f.get("table_font_size")):null,tax_enabled:f.has("tax_enabled"),tax_rate:Number(f.get("tax_rate")||0),isb_enabled:f.has("isb_enabled"),isb_rate:Number(f.get("isb_rate")||0),is_default:f.has("is_default")};try{const saved=await api("/api/v1/billing/headers"+(id?"/"+id:"?organization_id="+encodeURIComponent(org)),{method:id?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});billingState.selectedHeader=saved.id;tell("Entête enregistré.");billingHeaders()}catch(error){tell(error.message)}}
async function billingDeleteHeader(id){if(!confirm("Supprimer cet entête ? Les entêtes utilisés dans les factures sont protégés."))return;try{await api("/api/v1/billing/headers/"+id,{method:"DELETE"});billingState.selectedHeader=null;tell("Entête supprimé.");billingHeaders()}catch(error){tell(error.message)}}

async function billingCategoryPage(){const items=await api("/api/v1/billing/categories?organization_id="+encodeURIComponent(org));billingState.categories=items;billingSet(billingHero("Catégories","Organisation du catalogue réservé à la facturation.")+'<section class="billing-panel"><form id="billCategoryForm" class="billing-form-grid"><label>Nom<input name="name" required></label><label>Description<input name="description"></label><button>Ajouter la catégorie</button></form></section><section class="billing-panel"><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Catégorie</th><th>Description</th><th>Actions</th></tr></thead><tbody>'+items.map((item,index)=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.description||"—")+'</td><td><button class="secondary" type="button" onclick="billingEditCategory('+index+')">Modifier</button><button class="danger" type="button" onclick="billingDeleteCategory('+index+')">Supprimer</button></td></tr>').join("")+'</tbody></table></div></section>');document.getElementById("billCategoryForm").onsubmit=async event=>{event.preventDefault();const f=new FormData(event.target);try{await api("/api/v1/billing/categories?organization_id="+encodeURIComponent(org),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:f.get("name"),description:f.get("description")||null})});tell("Catégorie créée.");billingCategoryPage()}catch(error){tell(error.message)}}}
async function billingEditCategory(index){const item=billingState.categories[index],name=prompt("Nom de catégorie",item.name);if(name===null||!name.trim())return;try{await api("/api/v1/billing/categories/"+item.id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:name.trim(),description:item.description})});tell("Catégorie modifiée.");billingCategoryPage()}catch(error){tell(error.message)}}
async function billingDeleteCategory(index){const item=billingState.categories[index];if(!confirm("Supprimer cette catégorie ? Les produits seront conservés."))return;try{await api("/api/v1/billing/categories/"+item.id,{method:"DELETE"});tell("Catégorie supprimée.");billingCategoryPage()}catch(error){tell(error.message)}}

async function billingReports(){const [summary,credits]=await Promise.all([api("/api/v1/billing/reports/summary?organization_id="+encodeURIComponent(org)+"&days=30"),api("/api/v1/billing/customers/credits?organization_id="+encodeURIComponent(org))]);billingSet(billingHero("Rapports","Chiffres des 30 derniers jours et soldes clients.")+'<div class="billing-kpis">'+[["Facturé",billingCurrency(summary.invoiced)],["Encaissé",billingCurrency(summary.paid)],["À recevoir",billingCurrency(summary.outstanding)],["Clients débiteurs",credits.items.filter(item=>item.balance>0).length]].map(item=>'<div class="billing-kpi"><small>'+item[0]+'</small><b>'+esc(item[1])+'</b></div>').join("")+'</div><section class="billing-panel"><h2>Clients débiteurs</h2><div class="billing-table-wrap"><table class="billing-table"><thead><tr><th>Client</th><th>Téléphone</th><th>Factures</th><th>Reste</th></tr></thead><tbody>'+credits.items.filter(item=>item.balance>0).map(item=>'<tr><td>'+esc(item.name)+'</td><td>'+esc(item.phone||"—")+'</td><td>'+item.invoices+'</td><td>'+billingCurrency(item.balance)+'</td></tr>').join("")+'</tbody></table></div></section>')}
async function billingMaintenance(){const items=await api("/api/v1/billing/invoices?organization_id="+encodeURIComponent(org)+"&page_size=25");billingSet(billingHero("Maintenance","Les PDF peuvent être régénérés depuis leurs données enregistrées.")+'<section class="billing-panel"><h2>Documents récents</h2><p>Ouvrez un PDF pour le générer à nouveau ou le télécharger. Les données et les entêtes restent protégés dans la base.</p>'+billingInvoiceTable(items)+'</section>')}
async function billingSettings(){const headers=await api("/api/v1/billing/headers?organization_id="+encodeURIComponent(org));billingSet(billingHero("Paramètres","Configuration de la facturation FUSAA.")+'<section class="billing-panel"><h2>Configuration active</h2><p>Entête par défaut : <b>'+esc(headers.find(item=>item.is_default)?.company_name||"Aucun")+'</b></p><p>Devise : <b>FCFA (XOF)</b></p><div class="billing-actions"><button type="button" onclick="billingOpen(\'headers\')">Configurer les entêtes</button><button class="secondary" type="button" onclick="billingOpen(\'categories\')">Catégories</button><button class="secondary" type="button" onclick="billingOpen(\'products\')">Produits</button></div></section>')}
