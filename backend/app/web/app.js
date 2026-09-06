let token=localStorage.token||"",org=localStorage.org||"",workshop=localStorage.workshop||"";
let docs={},jobs=[],socket,aiPlan=null,aiBusy=false,chatHistory=[],flushing=false,workshopSettings={},knownActivityIds=new Set(),activityPrimed=false;
const $=id=>document.getElementById(id);
function newId(){if(globalThis.crypto?.randomUUID)return globalThis.crypto.randomUUID();const bytes=globalThis.crypto?.getRandomValues?globalThis.crypto.getRandomValues(new Uint8Array(16)):Array.from({length:16},()=>Math.floor(Math.random()*256));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const hex=Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`}
const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const userId=()=>{try{return JSON.parse(atob(token.split(".")[1])).sub}catch{return null}};
function tell(value){
  if($("message"))$("message").textContent=value||"";
  if($("globalMessage")){$("globalMessage").textContent=value||"";$("globalMessage").hidden=!value}
}
function friendlyPrintError(value){
  const text=String(value||"");
  if(text.includes("Driver changed requested settings")||text.includes("printing aborted"))return "Le pilote Windows a ajuste automatiquement un reglage. L'impression n'a pas ete lancee : choisissez les reglages proposes par l'imprimante puis reessayez.";
  if(text.includes("Driver refused print settings"))return "Le pilote de l'imprimante a refuse ces reglages. Utilisez le format ou le mode couleur indique par l'imprimante.";
  if(text.includes("does not support duplex"))return "Le recto-verso n'est pas disponible sur cette imprimante. Desactivez cette option.";
  return text;
}
function readableApiError(detail){
  if(Array.isArray(detail))return detail.map(item=>{if(typeof item==="string")return item;const field=Array.isArray(item?.loc)?item.loc[item.loc.length-1]:"";return field&&item?.msg?field+" : "+item.msg:item?.msg||"Données invalides."}).join("\n");
  if(detail&&typeof detail==="object")return detail.message||detail.msg||"Données invalides.";
  return String(detail||"La demande a échoué.");
}
function network(){
  const online=navigator.onLine;
  $("network").textContent=online?"● Connecté":"● Hors ligne — envois en attente";
  $("network").className=online?"network online":"network offline";
}
function state(){
  const on=Boolean(token);
  $("auth").classList.toggle("hidden",on);$("app").classList.toggle("hidden",!on);
  $("org").textContent=org||"—";$("workshop").textContent=workshop||"—";network();
}
async function api(path,options={}){
  if(!navigator.onLine)throw Error("Connexion absente.");
  const response=await fetch(path,{...options,headers:{...(options.headers||{}),Authorization:"Bearer "+token}});
  let data={};try{data=await response.json()}catch{}
  if(response.status===401){logout();throw Error("Session expirée. Reconnectez-vous.")}
  if(!response.ok)throw Error(friendlyPrintError(readableApiError(data.detail)));
  return data;
}
async function restoreWorkspace(){
  if(!token)return;
  const spaces=await api("/api/v1/workspaces");
  const item=spaces.find(x=>x.organization_id===org&&x.workshop_id===workshop)||spaces[0];
  if(!item){org="";workshop="";localStorage.removeItem("org");localStorage.removeItem("workshop");return}
  org=localStorage.org=item.organization_id;workshop=localStorage.workshop=item.workshop_id;
}
async function auth(path,extra){
  try{
    const data=await api(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:$("email").value,password:$("password").value,...extra})});
    token=localStorage.token=data.access_token;await restoreWorkspace();state();await refresh();connectEvents();
  }catch(error){alert(error.message)}
}
function login(){auth("/api/v1/auth/login",{})}
function registerUser(){auth("/api/v1/auth/register",{display_name:$("email").value})}
function logout(){
  ["token","org","workshop"].forEach(key=>localStorage.removeItem(key));
  token="";org="";workshop="";jobs=[];docs={};chatHistory=[];aiPlan=null;socket?.close();state();
}
async function createOrg(){
  try{const item=await api("/api/v1/organizations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:$("orgName").value})});org=localStorage.org=item.id;await restoreWorkspace();state();tell("Organisation créée.")}catch(error){tell(error.message)}
}
async function createWorkshop(){
  try{const item=await api("/api/v1/workshops",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({organization_id:org,name:$("workshopName").value})});workshop=localStorage.workshop=item.id;state();tell("Atelier créé.")}catch(error){tell(error.message)}
}
async function createAgent(){
  try{const item=await api("/api/v1/agents",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({workshop_id:workshop,name:$("agentName").value})});$("agentResult").textContent="Jeton d’enrôlement :\n"+item.enrollment_token}catch(error){$("agentResult").textContent=error.message}
}
function localDb(){
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open("fusaa-offline",2);
    request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains("uploads"))request.result.createObjectStore("uploads",{keyPath:"id"})};
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
}
async function queueUpload(file){
  const database=await localDb(),id=newId();
  await new Promise((resolve,reject)=>{const tx=database.transaction("uploads","readwrite");tx.objectStore("uploads").put({id,file,org,workshop,owner:userId()});tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});
  database.close();
}
async function flushUploads(){
  if(!token||!navigator.onLine||flushing)return;flushing=true;
  try{
    const database=await localDb(),owner=userId();
    const rows=await new Promise((resolve,reject)=>{const req=database.transaction("uploads","readonly").objectStore("uploads").getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});
    let synced=0;
    for(const row of rows){
      if(row.owner!==owner)continue;
      const body=new FormData();body.append("file",row.file);
      await api("/api/v1/documents/upload?organization_id="+encodeURIComponent(row.org)+"&workshop_id="+encodeURIComponent(row.workshop),{method:"POST",headers:{"X-Upload-ID":row.id},body});
      await new Promise((resolve,reject)=>{const tx=database.transaction("uploads","readwrite");tx.objectStore("uploads").delete(row.id);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});
      synced++;
    }
    database.close();if(synced)tell(`${synced} document(s) hors ligne synchronisé(s).`);
  }catch(error){tell(error.message)}finally{flushing=false}
}
async function upload(){
  try{
    const file=$("file").files[0];if(!file)throw Error("Choisissez un fichier.");
    await restoreWorkspace();if(!org||!workshop)throw Error("Aucun atelier n’est disponible pour ce compte.");
    if(!navigator.onLine){await queueUpload(file);tell("Le document sera envoyé au retour du réseau.");return}
    const body=new FormData(),id=newId();body.append("file",file);
    const item=await api("/api/v1/documents/upload?organization_id="+encodeURIComponent(org)+"&workshop_id="+encodeURIComponent(workshop),{method:"POST",headers:{"X-Upload-ID":id},body});
    tell("Travail "+item.id.slice(0,8)+" créé.");await refresh();$("job").value=item.id;showJob();selectView("print");
  }catch(error){tell(error.message)}
}
const card=(label,value)=>'<div class="card"><b>'+esc(value)+'</b><span class="muted">'+esc(label)+"</span></div>";
async function refresh(){
  if(!token)return;
  try{
    await restoreWorkspace();state();
    const savedJob=$("job").value,savedPrinter=$("printer").value;
    const results=await Promise.all([api("/api/v1/dashboard"),api("/api/v1/jobs"),api("/api/v1/printers"),api("/api/v1/documents"),api("/api/v1/audit"),api("/api/v1/activities"),api("/api/v1/local-monitor/status"),api("/api/v1/settings")]);
    const dashboard=results[0],printers=results[2],documents=results[3];
    jobs=results[1];docs=Object.fromEntries(documents.map(item=>[item.id,item]));
    $("stats").innerHTML=card("Agents",dashboard.agents_online)+card("Imprimantes",dashboard.printers_available)+card("À valider",dashboard.jobs_waiting)+card("En cours",dashboard.jobs_printing)+card("Terminés",dashboard.jobs_completed)+card("Erreurs",dashboard.jobs_failed);
    $("job").innerHTML=jobs.map(item=>'<option value="'+esc(item.id)+'">'+esc(item.status)+" · "+esc(docs[item.document_id]?.original_name||item.id)+"</option>").join("");
    $("printer").innerHTML=printers.map(item=>'<option value="'+esc(item.id)+'" '+(["ONLINE","PRINTING","READY","IDLE"].includes(item.status)?"":"disabled")+">"+esc(item.name)+" — "+esc(item.status)+"</option>").join("");
    $("jobs").innerHTML=jobs.map(item=>'<div class="job"><b>'+esc(item.status)+" · "+esc(docs[item.document_id]?.original_name||item.document_id)+'<br><span class="muted">'+esc(friendlyPrintError(item.error_message||""))+"</span></div>").join("");
    $("historyText").textContent=results[4].map(item=>item.timestamp+" — "+item.action+" — "+item.result).join("\n");
    if($("processDocument"))$("processDocument").innerHTML=documents.map(item=>'<option value="'+esc(item.id)+'">'+esc(item.original_name)+"</option>").join("");
    if(jobs.some(item=>item.id===savedJob))$("job").value=savedJob;
    if(printers.some(item=>item.id===savedPrinter))$("printer").value=savedPrinter;
    workshopSettings=results[7]||{};applyWorkshopSettings();showJob();renderActivities(results[5]);renderMonitor(results[6]);checkPushAvailability();
  }catch(error){tell(error.message)}
}
async function showJob(){
  const job=jobs.find(item=>item.id===$("job").value),document=job&&docs[job.document_id];
  const confirmButton=globalThis.document.querySelector('button[onclick="confirmJob()"]');
  if(confirmButton){confirmButton.id="confirmPrintBtn";confirmButton.disabled=!job||job.status!=="READY";confirmButton.title=confirmButton.disabled?"Préparez d’abord le travail":"Confirmer l’impression"}
  if(!document){$("inspection").textContent="Aucun travail sélectionné.";$("preview").classList.add("hidden");return}
  const meta=document.metadata_json||{};
  const details=[document.original_name,meta.pages?`${meta.pages} page(s)`:null,meta.orientation?`Orientation : ${meta.orientation.toLowerCase()}`:null,meta.width_points&&meta.height_points?`Format detecte : ${Math.round(meta.width_points)} x ${Math.round(meta.height_points)} pt`:null].filter(Boolean);
  $("inspection").textContent=details.join("\n")||"Document pret a etre configure.";
  try{
    const response=await fetch("/api/v1/documents/"+encodeURIComponent(document.id)+"/preview",{headers:{Authorization:"Bearer "+token}});
    if(!response.ok)throw Error();$("preview").src=URL.createObjectURL(await response.blob());$("preview").classList.remove("hidden");
  }catch{$("preview").classList.add("hidden")}
}
function printOptions(){return {printer_id:$("printer").value,copies:Number($("copies").value),paper_size:$("paper").value||null,orientation:$("orientation").value||null,color_mode:$("color").value||null,duplex:$("duplex").checked,pages:$("pages").value||null,instructions:$("instructions").value||null}}
async function prepare(){try{await api("/api/v1/jobs/"+encodeURIComponent($("job").value)+"/prepare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(printOptions())});tell("Travail préparé. Vérifiez-le puis confirmez l’impression.");await refresh()}catch(error){tell(error.message)}}
async function confirmJob(){const job=jobs.find(item=>item.id===$("job").value);if(job&&job.status==="WAITING_APPROVAL"){tell("Ce travail doit d’abord être préparé. Cliquez sur 'Préparer' avant de confirmer l’impression.");return}if(!confirm("Envoyer cette impression au PC Windows ?"))return;try{await api("/api/v1/jobs/"+encodeURIComponent($("job").value)+"/confirm",{method:"POST"});tell("Commande envoyée à l’agent Windows.");await refresh()}catch(error){tell(error.message)}}
async function cancelJob(){if(!confirm("Annuler ce travail ?"))return;try{await api("/api/v1/jobs/"+encodeURIComponent($("job").value)+"/cancel",{method:"POST"});tell("Annulation demandée.");await refresh()}catch(error){tell(error.message)}}
function renderAssistant(data){
  const steps=(data.steps||[]).map(item=>"<li>"+esc(item)+"</li>").join("");
  const next=data.next_view?'<button class="secondary" onclick="selectView(\''+esc(data.next_view)+"')\">"+esc(data.next_label||"Continuer")+"</button>":"";
  $("aiResult").innerHTML='<article class="ai-response"><p class="eyebrow">'+esc(data.title||"Assistant FUSAA")+"</p><h3>"+esc(data.answer||"")+"</h3>"+(steps?"<ol>"+steps+"</ol>":"")+next+"</article>";
  const call=(data.tool_calls||[]).find(item=>item.safety!=="SAFE");
  aiPlan=call?{call,data}:null;$("aiConfirm").classList.toggle("hidden",!aiPlan||!data.requires_confirmation);
  $("aiConfirm").textContent=call?.name==="request_print"?"Confirmer l’impression":call?.name==="cancel_print_job"?"Confirmer l’annulation":"Confirmer l’action";
}
async function askAssistant(){
  if(aiBusy)return;aiBusy=true;aiPlan=null;$("aiConfirm").classList.add("hidden");$("aiResult").innerHTML='<p class="muted">Ollama prépare une réponse…</p>';
  try{
    const content=$("aiMessage").value.trim();if(!content)throw Error("Écrivez votre demande.");
    const data=await api("/api/v1/assistant/understand",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:content,history:chatHistory.slice(-8),selected_job_id:$("job").value||null})});
    chatHistory=[...chatHistory,{role:"user",content},{role:"assistant",content:data.answer}].slice(-8);renderAssistant(data);
  }catch(error){$("aiResult").textContent=error.message}finally{aiBusy=false}
}
async function executeAssistant(){
  const call=aiPlan?.call;if(!call)return;
  try{
    const result=await api("/api/v1/assistant/execute",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:call.name,arguments:call.arguments,confirmed:true})});
    $("aiResult").innerHTML='<article class="ai-response"><p class="eyebrow">ACTION ENREGISTRÉE</p><h3>'+esc(result.status||"La demande est traitée.")+"</h3></article>";$("aiConfirm").classList.add("hidden");aiPlan=null;await refresh();
  }catch(error){$("aiResult").textContent=error.message}
}
function renderActivities(items){
  const target=$("activityList");if(!target)return;
  target.innerHTML=items.length?items.map(item=>'<article class="arrival"><div><span class="arrival-source">'+(item.source==="WHATSAPP"?"WhatsApp":"Bureau")+"</span><b>"+esc(item.title)+"</b><p>"+esc(item.detail)+"</p></div><time>"+new Date(item.created_at).toLocaleString("fr-FR")+"</time></article>").join(""):'<p class="muted">Aucune nouvelle arrivée pour le moment.</p>';
}
function renderMonitor(item){
  const target=$("monitorStatus");if(!target)return;
  const desktop=item.desktop||{},whatsapp=item.whatsapp||"not_paired";
  target.innerHTML='<div class="status-card"><b>Bureau</b><span>'+esc(desktop.state||"not_started")+'</span></div><div class="status-card"><b>WhatsApp Web / Brave</b><span>'+esc(whatsapp)+"</span></div>";
}
async function startPairing(){try{await restoreWorkspace();if(!workshop)throw Error("Choisissez d’abord un atelier.");const result=await api("/api/v1/browser-link/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({workshop_id:workshop})});$("pairCode").textContent=result.code;$("pairCodeBox").classList.remove("hidden");tell("Copiez ce code dans l’extension Brave dans les 10 minutes.")}catch(error){tell(error.message)}}
async function revokePairing(){try{await api("/api/v1/browser-link/revoke",{method:"POST"});tell("La liaison Brave est désactivée.");await refresh()}catch(error){tell(error.message)}}
async function loadActivities(){try{renderActivities(await api("/api/v1/activities"));await loadMonitor()}catch(error){tell(error.message)}}
async function loadMonitor(){try{renderMonitor(await api("/api/v1/local-monitor/status"))}catch(error){tell(error.message)}}
function b64(value){return Uint8Array.from(atob(value.replace(/-/g,"+").replace(/_/g,"/")),item=>item.charCodeAt(0))}
async function enablePush(){try{const key=(await api("/api/v1/push/public-key")).public_key,reg=await navigator.serviceWorker.ready,sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64(key)}),value=sub.toJSON();await api("/api/v1/push/subscriptions",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({endpoint:value.endpoint,p256dh:value.keys.p256dh,auth:value.keys.auth})});tell("Notifications activées.")}catch(error){tell("Notifications indisponibles : "+error.message)}}
async function checkPushAvailability(){const button=globalThis.document.querySelector('button[onclick="enablePush()"]');if(!button)return;try{await api("/api/v1/push/public-key");button.hidden=false}catch(error){if(String(error.message).includes("not configured")){button.hidden=true;button.title="Les alertes locales FUSAA restent actives"}else button.hidden=false}}
function connectEvents(){
  if(!token)return;socket?.close();const protocol=location.protocol==="https:"?"wss":"ws";
  socket=new WebSocket(protocol+"://"+location.host+"/ws/events?token="+encodeURIComponent(token));
  socket.onmessage=event=>{const item=JSON.parse(event.data);if(item.event==="LOCAL_ACTIVITY")loadActivities();else refresh()};
  socket.onclose=event=>{if(event.code===1008){logout();tell("Session expirée. Reconnectez-vous.");return}if(token)setTimeout(connectEvents,5000)};
}
function selectView(view){
  const target=$(view);if(!target)return;
  if(view==="arrivals")loadActivities();if(view==="connectors")loadMonitor();if(view==="processing")refresh();if(view==="business")loadBusiness();if(view==="supervision")loadSupervision();if(view==="system")loadSystemHealth();
  document.querySelectorAll(".view").forEach(item=>item.classList.toggle("active",item===target));
  document.querySelectorAll("#nav a").forEach(item=>item.classList.toggle("active",item.dataset.view===view));
  history.replaceState(null,"","#"+view);window.scrollTo({top:0,behavior:"smooth"});
}
async function processSelectedDocument(){try{const documentId=$("processDocument").value,operation=$("processOperation").value;if(!documentId)throw Error("Choisissez un document.");const payload={operation};if(operation==="rotate")payload.degrees=Number($("processDegrees").value)||90;const item=await api("/api/v1/documents/"+encodeURIComponent(documentId)+"/process",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});tell("Copie préparée : "+item.original_name);await refresh();selectView("print")}catch(error){tell(error.message)}}
async function loadBusiness(){const target=$("businessStats");if(!target||!org)return;try{const item=await api("/api/v1/business/stats?organization_id="+encodeURIComponent(org));target.innerHTML=card("Clients",item.customers)+card("Factures",item.invoices)+card("Revenu encaissé",item.paid_revenue)+card("Travaux terminés",item.completed_jobs)}catch(error){target.textContent=error.message}}
async function loadSupervision(){const target=$("supervisionList");if(!target||!org)return;try{const item=await api("/api/v1/supervision?organization_id="+encodeURIComponent(org));target.innerHTML=item.workshops.map(site=>'<article class="arrival"><div><span class="arrival-source">ATELIER</span><b>'+esc(site.name)+"</b><p>Agents : "+esc(site.agents.filter(agent=>agent.online).length)+" en ligne · Imprimantes : "+esc(site.printers.length)+" · En attente : "+esc(site.jobs.waiting)+"</p></div></article>").join("")||'<p class="muted">Aucun atelier.</p>'}catch(error){target.textContent=error.message}}
function mountProcessing(){document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="processing" class="view"><div class="view-head"><div><p class="eyebrow">PRÉPARATION</p><h1>Préparer une copie</h1></div></div><div class="panel"><p class="muted">Les transformations créent une copie ; le document original reste intact.</p><select id="processDocument"></select><div class="grid"><select id="processOperation"><option value="rotate">Tourner</option><option value="fit_to_page">Adapter à la page</option><option value="convert_to_pdf">Convertir en PDF</option></select><input id="processDegrees" type="number" value="90" min="-360" max="360" aria-label="Degrés de rotation"></div><button onclick="processSelectedDocument()">Créer la copie préparée</button></div></section>')}
function mountBusiness(){document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="business" class="view"><div class="view-head"><div><p class="eyebrow">ACTIVITÉ</p><h1>Clients et tarifs</h1></div><button class="secondary" onclick="loadBusiness()">Actualiser</button></div><div id="businessStats" class="stats"></div></section>')}
function mountSupervision(){document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="supervision" class="view"><div class="view-head"><div><p class="eyebrow">MULTI-SITE</p><h1>État des ateliers</h1></div><button class="secondary" onclick="loadSupervision()">Actualiser</button></div><div id="supervisionList" class="activity-list"></div></section>')}
function mountAssistant(){document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="assistant" class="view"><div class="view-head"><div><p class="eyebrow">ASSISTANCE LOCALE</p><h1>Assistant IA</h1></div></div><div class="panel"><p class="muted">L’assistant vous conduit vers la prochaine étape. Une impression n’est proposée qu’après sélection d’un travail prêt.</p><textarea id="aiMessage" placeholder="Ex. Je voudrais imprimer un document"></textarea><button onclick="askAssistant()">Demander à FUSAA</button><div id="aiResult" class="ai-result" aria-live="polite"></div><button id="aiConfirm" class="hidden" onclick="executeAssistant()">Confirmer l’action</button></div></section>')}
function mountConnectors(){document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="connectors" class="view"><div class="view-head"><div><p class="eyebrow">ARRIVÉES LOCALES</p><h1>Surveiller Bureau et WhatsApp</h1></div></div><div class="panel"><p class="muted">FUSAA signale les nouveaux PDF, JPG et PNG du Bureau. L’extension Brave signale une arrivée WhatsApp sans lire le texte, les contacts ou les fichiers.</p><div id="monitorStatus" class="status-grid"></div><button onclick="startPairing()">Créer un code pour l’extension Brave</button><div id="pairCodeBox" class="hidden"><p class="field-label">CODE À COLLER DANS L’EXTENSION</p><pre id="pairCode" class="code"></pre></div><button class="secondary" onclick="revokePairing()">Désactiver la liaison Brave</button><p class="notice">Le contenu de vos messages reste dans Brave. FUSAA reçoit seulement l’alerte d’arrivée.</p></div></section>')}
function mountArrivals(){document.querySelector("#nav").insertAdjacentHTML("beforeend",'<a href="#arrivals" data-view="arrivals">◉ Arrivées</a>');document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="arrivals" class="view"><div class="view-head"><div><p class="eyebrow">BOÎTE D’ARRIVÉE</p><h1>Nouveaux fichiers et messages</h1></div><button class="secondary" onclick="loadActivities()">Actualiser</button></div><div id="activityList" class="activity-list"></div></section>')}
function mountSystem(){document.querySelector("#nav").insertAdjacentHTML("beforeend",'<a href="#system" data-view="system">⚙ État du système</a>');document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="system" class="view"><div class="view-head"><div><p class="eyebrow">INSTALLATION WINDOWS</p><h1>État du système</h1></div></div><div class="panel"><div id="systemStatus"></div><button onclick="loadSystemHealth()">Vérifier maintenant</button></div></section>')}
async function loadSystemHealth(){try{const data=await api("/api/v1/system/health");$("systemStatus").textContent="Superviseur : "+data.supervisor+" · API : "+(data.api?"OK":"à vérifier")+" · Agent : "+(data.agent?"OK":"à vérifier")+" · Ollama : "+(data.ollama?"OK":"à vérifier")+" · Sauvegarde : "+(data.backup_today?"vérifiée":"en attente")}catch(error){$("systemStatus").textContent=error.message}}
function mountStyle(){document.head.insertAdjacentHTML("beforeend",'<style>.ai-result{margin-top:14px}.ai-response{padding:16px;border:1px solid #27cdb94d;border-radius:13px;background:#071a28}.ai-response h3{font-size:1rem;line-height:1.6;margin:5px 0 10px}.ai-response ol{padding-left:22px;color:#c9d9e6}.ai-response li{margin:7px 0}.activity-list{display:grid;gap:11px}.arrival{display:flex;justify-content:space-between;gap:18px;padding:16px;border:1px solid #ffffff14;border-radius:15px;background:linear-gradient(130deg,#112b42,#0d1c2e)}.arrival b{display:block;margin:3px 0}.arrival p{margin:0;color:#a9bfd0;font-size:.88rem}.arrival time{color:#86a1b8;font-size:.78rem;white-space:nowrap}.arrival-source{display:inline-block;color:#2fe0c6;font-size:.69rem;font-weight:800;letter-spacing:.09em}.status-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}.status-card{border:1px solid #ffffff16;border-radius:11px;padding:12px;background:#071522}.status-card b,.status-card span{display:block}.status-card span{color:#4cdfbd;margin-top:4px}@media(max-width:680px){.arrival{flex-direction:column;gap:7px}.status-grid{grid-template-columns:1fr}}</style>')}
function applyWorkshopSettings(){const s=workshopSettings||{};if($("org"))$("org").textContent="FUSAA INFORMATIQUE";if($("workshop"))$("workshop").textContent=s.workshop_name||"FUSAA INFORMATIQUE";const fields={settingWorkshopName:s.workshop_name||"FUSAA INFORMATIQUE",settingCopies:s.default_copies||1,settingPaper:s.default_paper_size||"A4",settingOrientation:s.default_orientation||"PORTRAIT",settingColor:s.default_color_mode||"COLOR",settingDuplex:Boolean(s.default_duplex),settingPopup:Boolean(s.popup_enabled!==false),settingSmart:Boolean(s.smart_suggestions!==false)};Object.entries(fields).forEach(([id,value])=>{const node=$(id);if(!node)return;if(node.type==="checkbox")node.checked=value;else if(document.activeElement!==node)node.value=value});if($("copies")&&!$("copies").matches(":focus"))$("copies").value=s.default_copies||1;if($("paper")&&!$("paper").matches(":focus"))$("paper").value=s.default_paper_size||"A4";if($("orientation")&&!$("orientation").matches(":focus"))$("orientation").value=s.default_orientation||"PORTRAIT";if($("color")&&!$("color").matches(":focus"))$("color").value=s.default_color_mode||"COLOR";if($("duplex")&&!$("duplex").matches(":focus"))$("duplex").checked=Boolean(s.default_duplex)}
async function saveSettings(event){event?.preventDefault();try{const data=await api("/api/v1/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({workshop_name:$("settingWorkshopName").value,default_copies:Number($("settingCopies").value),default_paper_size:$("settingPaper").value,default_orientation:$("settingOrientation").value,default_color_mode:$("settingColor").value,default_duplex:$("settingDuplex").checked,popup_enabled:$("settingPopup").checked,smart_suggestions:$("settingSmart").checked})});workshopSettings=data;applyWorkshopSettings();tell("Paramètres de FUSAA INFORMATIQUE enregistrés.")}catch(error){tell(error.message)}}
function closeArrivalPopup(){$("arrivalPopup")?.classList.add("hidden")}
function openArrivalPopup(item){if(!workshopSettings.popup_enabled||item.source!=="DESKTOP")return;const target=$("arrivalPopup");if(!target)return;$("popupFile").textContent=item.detail||item.title;$("popupSettings").textContent=["Format "+(workshopSettings.default_paper_size||"A4"),"Orientation "+(workshopSettings.default_orientation||"PORTRAIT"),"Couleur "+(workshopSettings.default_color_mode||"COLOR"),String(workshopSettings.default_copies||1)+" exemplaire(s)",workshopSettings.default_duplex?"Recto-verso":"Recto"].join(" · ");target.classList.remove("hidden")}
function chooseArrivalPrint(){closeArrivalPopup();selectView("upload");tell("Sélectionnez le fichier signalé pour appliquer les réglages recommandés.");$("file")?.focus()}
function renderActivities(items){const target=$("activityList");const incoming=items.filter(item=>item&&item.id);if(activityPrimed){const fresh=incoming.filter(item=>!knownActivityIds.has(item.id));if(fresh.length)openArrivalPopup(fresh[0])}incoming.forEach(item=>knownActivityIds.add(item.id));activityPrimed=true;if(!target)return;target.innerHTML=items.length?items.map(item=>'<article class="arrival"><div><span class="arrival-source">'+(item.source==="WHATSAPP"?"WhatsApp":"Bureau")+'</span><b>'+esc(item.title)+'</b><p>'+esc(item.detail)+'</p></div><time>'+new Date(item.created_at).toLocaleString("fr-FR")+'</time></article>').join(""): '<p class="muted">Aucune nouvelle arrivée pour le moment.</p>'}
function appendChatBubble(role,title,body,steps=[]){const target=$("chatMessages");if(!target)return null;const bubble=document.createElement("article");bubble.className="chat-bubble "+role;const heading=document.createElement("div");heading.className="chat-bubble-head";heading.textContent=title;const text=document.createElement("p");text.textContent=body;bubble.append(heading,text);if(steps.length){const list=document.createElement("ol");steps.forEach(item=>{const li=document.createElement("li");li.textContent=item;list.append(li)});bubble.append(list)}target.append(bubble);target.scrollTop=target.scrollHeight;return bubble}
function chatPrompt(value){$("aiMessage").value=value;$("aiMessage").focus()}
function renderAssistant(data){const bubble=appendChatBubble("assistant",data.title||"Assistant FUSAA",data.answer||"",data.steps||[]);if(data.next_view&&bubble){const next=document.createElement("button");next.className="chat-next";next.textContent=data.next_label||"Continuer";next.onclick=()=>selectView(data.next_view);bubble.append(next)}const call=(data.tool_calls||[]).find(item=>item.safety!=="SAFE");aiPlan=call?{call,data}:null;$("aiConfirm")?.classList.toggle("hidden",!aiPlan||!data.requires_confirmation);if($("aiConfirm"))$("aiConfirm").textContent=call?.name==="request_print"?"Confirmer l’impression":call?.name==="cancel_print_job"?"Confirmer l’annulation":"Confirmer l’action"}
async function askAssistant(event){event?.preventDefault();if(aiBusy)return;aiBusy=true;aiPlan=null;$("aiConfirm")?.classList.add("hidden");const content=$("aiMessage").value.trim();if(!content){aiBusy=false;return}$("aiMessage").value="";appendChatBubble("user","Vous",content);const typing=appendChatBubble("assistant typing","FUSAA","Réflexion locale…");try{const data=await api("/api/v1/assistant/understand",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:content,history:chatHistory.slice(-8),selected_job_id:$("job").value||null})});typing?.remove();chatHistory=[...chatHistory,{role:"user",content},{role:"assistant",content:data.answer}].slice(-8);renderAssistant(data)}catch(error){typing?.remove();appendChatBubble("assistant","FUSAA",error.message)}finally{aiBusy=false}}
async function executeAssistant(){const call=aiPlan?.call;if(!call)return;try{const result=await api("/api/v1/assistant/execute",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:call.name,arguments:call.arguments,confirmed:true})});appendChatBubble("assistant","Action FUSAA",result.status||"La demande est traitée.");$("aiConfirm")?.classList.add("hidden");aiPlan=null;await refresh()}catch(error){appendChatBubble("assistant","FUSAA",error.message)}}
function selectView(view){const target=$(view);if(!target)return;if(view==="arrivals")loadActivities();if(view==="settings"){loadMonitor();loadSystemHealth()}document.querySelectorAll(".view").forEach(item=>item.classList.toggle("active",item===target));document.querySelectorAll("#nav a").forEach(item=>item.classList.toggle("active",item.dataset.view===view));history.replaceState(null,"","#"+view);window.scrollTo({top:0,behavior:"smooth"})}
function mountAssistant(){document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="assistant" class="view"><div class="view-head"><div><p class="eyebrow">ASSISTANCE LOCALE</p><h1>Assistant FUSAA</h1><p class="muted">Une conversation claire, des étapes visibles et aucune impression sans confirmation.</p></div></div><div class="chat-shell"><div id="chatMessages" class="chat-messages"><article class="chat-welcome"><span class="assistant-orb">F</span><div><b>Bonjour, je suis FUSAA.</b><p>Je peux retrouver un travail, expliquer les réglages et vous guider jusqu’à l’impression.</p></div></article></div><div class="chat-suggestions"><button type="button" class="chip" onclick="chatPrompt(&quot;Je voudrais imprimer un document&quot;)">Imprimer un document</button><button type="button" class="chip" onclick="chatPrompt(&quot;Quels travaux sont en attente ?&quot;)">Travaux en attente</button><button type="button" class="chip" onclick="chatPrompt(&quot;Quelles imprimantes sont disponibles ?&quot;)">Imprimantes disponibles</button></div><form class="chat-composer" onsubmit="askAssistant(event)"><textarea id="aiMessage" rows="1" placeholder="Écrivez votre demande…" aria-label="Message à FUSAA"></textarea><button type="submit" aria-label="Envoyer">↑</button></form><button id="aiConfirm" class="hidden chat-confirm" onclick="executeAssistant()">Confirmer l’action</button></div></section>')}
function mountSettings(){document.querySelector("#nav").insertAdjacentHTML("beforeend",'<a href="#settings" data-view="settings">⚙ Settings</a>');document.querySelector("main").insertAdjacentHTML("beforeend",'<section id="settings" class="view"><div class="view-head"><div><p class="eyebrow">CONFIGURATION LOCALE</p><h1>Settings · FUSAA INFORMATIQUE</h1><p class="muted">Un seul atelier, des réglages simples et réutilisés automatiquement.</p></div></div><form id="settingsForm" class="panel" onsubmit="saveSettings(event)"><h2>Atelier et impression</h2><label class="field-label">NOM DE L’ATELIER</label><input id="settingWorkshopName" required maxlength="160"><div class="grid"><div><label class="field-label">EXEMPLAIRES PAR DÉFAUT</label><input id="settingCopies" type="number" min="1" max="999" required></div><div><label class="field-label">FORMAT</label><select id="settingPaper"><option>A4</option><option>A3</option><option>A5</option></select></div><div><label class="field-label">ORIENTATION</label><select id="settingOrientation"><option value="PORTRAIT">Portrait</option><option value="LANDSCAPE">Paysage</option></select></div><div><label class="field-label">COULEUR</label><select id="settingColor"><option value="COLOR">Couleur</option><option value="MONOCHROME">Noir et blanc</option></select></div></div><label class="muted"><input id="settingDuplex" type="checkbox" style="width:auto"> Recto-verso par défaut</label><label class="muted"><input id="settingPopup" type="checkbox" style="width:auto"> Popup lorsqu’un fichier arrive sur le Bureau</label><label class="muted"><input id="settingSmart" type="checkbox" style="width:auto"> Proposer automatiquement les meilleurs réglages</label><button type="submit">Enregistrer les paramètres</button></form><div class="panel"><h2>WhatsApp dans Brave</h2><div id="monitorStatus" class="status-grid"></div><button onclick="startPairing()">Créer un code de liaison</button><div id="pairCodeBox" class="hidden"><p class="field-label">CODE À COLLER DANS L’EXTENSION</p><pre id="pairCode" class="code"></pre></div><button type="button" class="secondary" onclick="revokePairing()">Désactiver la liaison Brave</button><p class="notice">FUSAA reçoit uniquement un signal d’arrivée, jamais le texte, le contact ou le fichier WhatsApp.</p></div><div class="panel"><h2>État du service</h2><div id="systemStatus" class="statusline"></div><button type="button" class="secondary" onclick="loadSystemHealth()">Vérifier maintenant</button><input id="agentName" placeholder="Nom du PC Windows"><button type="button" class="secondary" onclick="createAgent()">Générer un enrôlement agent</button><pre id="agentResult" class="code"></pre></div></section>')}
function mountArrivalPopup(){document.body.insertAdjacentHTML("beforeend",'<div id="arrivalPopup" class="arrival-popup hidden" role="dialog" aria-modal="true"><button class="popup-close" onclick="closeArrivalPopup()" aria-label="Fermer">×</button><span class="eyebrow">NOUVEAU FICHIER DÉTECTÉ</span><h2>Prêt pour l’impression</h2><p id="popupFile" class="popup-file"></p><p class="muted">Réglages recommandés pour FUSAA INFORMATIQUE :</p><div id="popupSettings" class="popup-settings"></div><button onclick="chooseArrivalPrint()">Choisir le fichier et préparer</button><button class="secondary" onclick="closeArrivalPopup()">Plus tard</button></div>')}
function compactNavigation(){const keep=new Set(["dashboard","upload","print","arrivals","assistant","settings"]);document.querySelectorAll("#nav a").forEach(link=>link.classList.toggle("hidden",!keep.has(link.dataset.view)));["orgName","workshopName"].forEach(id=>$(id)?.parentElement?.remove());$("agentName")?.remove();document.querySelector('button[onclick="createAgent()"]')?.remove();$("agentResult")?.remove();document.querySelectorAll("#dashboard .grid").forEach(grid=>{if(!grid.querySelector("input,button,select,textarea"))grid.remove()})}
function addExtensionDownload(){const actions=document.querySelector("#dashboard .view-head .inline-actions");if(!actions||$("extensionDownload"))return;actions.insertAdjacentHTML("beforeend",'<a id="extensionDownload" class="secondary" href="/browser-extension.zip" download>Installer WhatsApp</a>')}
function mountChatStyle(){document.head.insertAdjacentHTML("beforeend",'<style>.chat-shell{max-width:900px;min-height:560px;display:flex;flex-direction:column;border:1px solid #ffffff16;border-radius:24px;background:linear-gradient(150deg,#0d1d30f2,#071522f5);box-shadow:0 22px 60px #0005;overflow:hidden}.chat-messages{flex:1;min-height:360px;max-height:58vh;overflow:auto;padding:24px;display:flex;flex-direction:column;gap:14px}.chat-welcome{display:flex;gap:13px;align-items:flex-start;color:#dceaf6;max-width:600px;margin:10px auto 20px}.assistant-orb{width:34px;height:34px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,#18c9b0,#3276f3);font-weight:900;box-shadow:0 0 22px #18c9b055}.chat-welcome p{margin:4px 0;color:#8faac0}.chat-bubble{max-width:78%;padding:13px 15px;border-radius:18px;line-height:1.55;animation:panelIn .25s ease both}.chat-bubble.user{align-self:flex-end;color:#fff;background:linear-gradient(135deg,#176eaa,#3151ad);border-bottom-right-radius:5px}.chat-bubble.assistant{align-self:flex-start;background:#10243a;border:1px solid #ffffff16;color:#dceaf6;border-bottom-left-radius:5px}.chat-bubble-head{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:#39d6bd;font-weight:800;margin-bottom:5px}.chat-bubble p{margin:0}.chat-bubble ol{margin:9px 0 0;padding-left:22px;color:#c3d7e7}.chat-bubble li{margin:5px 0}.typing{opacity:.65}.chat-next,.chat-confirm{width:auto}.chat-next{margin-top:10px;padding:8px 12px}.chat-confirm{margin:0 20px 14px;width:calc(100% - 40px)}.chat-suggestions{display:flex;gap:8px;flex-wrap:wrap;padding:0 20px 12px}.chip{width:auto;margin:0;padding:8px 11px;border-radius:999px;background:#ffffff0a;border:1px solid #ffffff1c;color:#bed2e1;font-size:.78rem;box-shadow:none}.chat-composer{display:flex;gap:10px;align-items:end;padding:14px 16px;background:#07121f;border-top:1px solid #ffffff12}.chat-composer textarea{min-height:45px;max-height:140px;margin:0;resize:none;border-radius:15px}.chat-composer button{width:48px;height:45px;margin:0;border-radius:14px;font-size:1.2rem}.arrival-popup{position:fixed;right:24px;bottom:24px;z-index:60;width:min(410px,calc(100vw - 32px));padding:22px;border:1px solid #2ee2c588;border-radius:22px;background:linear-gradient(145deg,#102d43f5,#0a1728f8);box-shadow:0 22px 70px #0009;animation:panelIn .3s ease both}.popup-close{position:absolute;right:12px;top:10px;width:32px;height:32px;border-radius:50%;padding:0;background:#ffffff10;box-shadow:none}.popup-file{font-weight:750;word-break:break-word}.popup-settings{padding:12px;border:1px solid #ffffff15;border-radius:12px;color:#9fe9db;background:#081722;margin:10px 0 14px;font-size:.84rem}@media(max-width:680px){.chat-bubble{max-width:92%}.chat-messages{padding:16px}.arrival-popup{right:16px;bottom:16px}}</style>')}
mountAssistant();mountSettings();mountArrivals();mountArrivalPopup();mountChatStyle();mountStyle();compactNavigation();addExtensionDownload();
document.querySelector("main").insertAdjacentHTML("afterbegin",'<p id="globalMessage" role="status" hidden></p>');
document.querySelectorAll("#nav a").forEach(link=>link.addEventListener("click",event=>{event.preventDefault();selectView(link.dataset.view)}));
window.addEventListener("online",()=>{network();flushUploads();refresh()});window.addEventListener("offline",network);
function syncViewFromHash(){const view=location.hash.replace(/^#/,"");if(view&&$(view))selectView(view)}
window.addEventListener("hashchange",syncViewFromHash);
syncViewFromHash();
if(token)restoreWorkspace().then(()=>{state();refresh();connectEvents();flushUploads();syncViewFromHash()}).catch(error=>tell(error.message));
