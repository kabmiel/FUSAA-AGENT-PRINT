let token=localStorage.token||"",org=localStorage.org||"",workshop=localStorage.workshop||"";
let docs={},jobs=[],socket,aiPlan=null,aiBusy=false,chatHistory=[],flushing=false,workshopSettings={},knownActivityIds=new Set(),activityPrimed=false;
const $=id=>document.getElementById(id);
function newId(){if(globalThis.crypto?.randomUUID)return globalThis.crypto.randomUUID();const bytes=globalThis.crypto?.getRandomValues?globalThis.crypto.getRandomValues(new Uint8Array(16)):Array.from({length:16},()=>Math.floor(Math.random()*256));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const hex=Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`}
const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const userId=()=>{try{return JSON.parse(atob(token.split(".")[1])).sub}catch{return null}};
function tell(value){
  if($("jobGlass")?.open)$("glassFeedback").textContent=value||"";
  if($("message"))$("message").textContent=value||"";
  if($("globalMessage")){$("globalMessage").textContent=value||"";$("globalMessage").hidden=!value}
}
function operationError(error,stage){const message=error?.message||String(error||"Erreur inconnue");tell(stage+" : "+message);setPrintProgress("error",100,"Échec · "+stage,message);return message}
function setPrintProgress(status,percent,stage,detail=""){const bar=$("printBar"),label=$("printStage"),value=$("printPercent"),info=$("printDetail");if(!bar||!label)return;bar.style.width=Math.max(0,Math.min(100,percent))+"%";bar.className=status||"";label.textContent=stage;value.textContent=Math.round(percent)+"%";info.textContent=detail;const step=percent>=100?5:percent>=80?4:percent>=55?3:percent>=25?2:1;document.querySelectorAll("#printSteps span").forEach(item=>item.classList.toggle("done",Number(item.dataset.step)<=step))}
function setUploadProgress(percent,stage,detail=""){const box=$("uploadProgress"),bar=$("uploadBar");if(!box||!bar)return;box.classList.remove("hidden");bar.style.width=Math.max(0,Math.min(100,percent))+"%";$("uploadPercent").textContent=Math.round(percent)+"%";$("uploadStage").textContent=stage;$("uploadDetail").textContent=detail}
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
function registerUser(){
  const email=$("email").value.trim(),password=$("password").value,name=$("displayName")?.value.trim()||email;
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){alert("Saisissez une adresse e-mail valide.");return}
  if(password.length<12){alert("Le mot de passe doit contenir au moins 12 caractères.");return}
  if(!name){alert("Saisissez votre nom.");return}
  auth("/api/v1/auth/register",{display_name:name})
}
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
  const button=$("uploadButton");try{
    const file=$("file").files[0];if(!file)throw Error("Choisissez un fichier.");
    await restoreWorkspace();if(!org||!workshop)throw Error("Aucun atelier n’est disponible pour ce compte.");
    if(!navigator.onLine){await queueUpload(file);tell("Le document sera envoyé au retour du réseau.");return}
    button.disabled=true;setUploadProgress(2,"Préparation du fichier",file.name);setPrintProgress("busy",12,"Fichier sélectionné","Envoi sécurisé vers FUSAA");
    const item=await uploadWithProgress(file);
    setUploadProgress(100,"Fichier reçu","Inspection du document terminée");setPrintProgress("busy",35,"Inspection terminée","Le travail est prêt à être configuré");
    tell("Travail "+item.id.slice(0,8)+" créé.");await refresh();$("job").value=item.id;showJob();selectView("print");openJobGlass(item.id,"prepare");
  }catch(error){operationError(error,"Chargement du fichier")}finally{if(button)button.disabled=false}
}
function uploadWithProgress(file){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest(),id=newId();xhr.open("POST","/api/v1/documents/upload?organization_id="+encodeURIComponent(org)+"&workshop_id="+encodeURIComponent(workshop));xhr.setRequestHeader("Authorization","Bearer "+token);xhr.setRequestHeader("X-Upload-ID",id);xhr.upload.onprogress=event=>{if(event.lengthComputable){const p=Math.max(3,Math.round(event.loaded/event.total*92));setUploadProgress(p,"Chargement du fichier",`${Math.round(event.loaded/1024/1024*100)/100} / ${Math.round(event.total/1024/1024*100)/100} Mo`);setPrintProgress("busy",12+p*.18,"Chargement","Transmission en cours…")}};xhr.onerror=()=>reject(Error("Le réseau a interrompu l’envoi du fichier."));xhr.onload=()=>{let data={};try{data=JSON.parse(xhr.responseText||"{}")}catch{}if(xhr.status>=200&&xhr.status<300)resolve(data);else reject(Error(readableApiError(data.detail)||`Erreur serveur HTTP ${xhr.status}`))};const body=new FormData();body.append("file",file);xhr.send(body)})}
const card=(label,value)=>'<div class="card"><b>'+esc(value)+'</b><span class="muted">'+esc(label)+"</span></div>";
function jobMeta(status){return ({WAITING_APPROVAL:[35,"À préparer","En attente"],READY:[58,"Prêt","Réglages validés"],QUEUED:[76,"En file","Commande envoyée"],PRINTING:[90,"Impression","En cours"],COMPLETED:[100,"Terminé","Succès"],FAILED:[100,"Échec","À relancer"],CANCELLED:[100,"Annulé","Arrêté"],IGNORED:[100,"Ignoré","Non lancé"]}[status]||[10,status,"État inconnu"])}
function renderJobCards(items,documents){
  const target=$("jobs");if(!target)return;
  const existing=new Map(Array.from(target.children).map(node=>[node.dataset.jobId,node]));
  for(const item of items){
    const meta=jobMeta(item.status),name=documents[item.document_id]?.original_name||item.document_id;
    const done=item.status==="COMPLETED",stopped=["FAILED","CANCELLED","IGNORED"].includes(item.status);
    const count=done?5:({WAITING_APPROVAL:2,READY:3,QUEUED:3,PRINTING:4}[item.status]||0);
    const id=esc(item.id);
    const steps=["Fichier","Inspection","Préparation","Impression","Terminé"].map((label,index)=>'<span class="'+(index<count?'done':'')+'">'+(index<count?'✓':index+1)+' · '+label+'</span>').join("");
    const content='<div class="job-card-head"><div><span class="job-badge">'+esc(meta[1])+'</span><h3>'+esc(name)+'</h3></div><strong>'+(stopped?'Arrêté':meta[0]+'%')+'</strong></div>'+
      '<div class="job-mini-track"><i style="width:'+(stopped?0:meta[0])+'%"></i></div><div class="job-card-meta"><span>'+esc(meta[2])+'</span><span>Progression par étapes</span></div>'+
      '<div class="print-steps">'+steps+'</div>'+
      (item.error_message?'<p class="job-error">'+esc(friendlyPrintError(item.error_message))+'</p>':'')+
      (done?'<p class="job-finish-note">Terminé · reste visible jusqu’à votre confirmation.</p>':'')+
      '<div class="job-actions"><button class="secondary" onclick="openJobGlass(\''+id+'\',\'view\')">Voir</button>'+
      (item.status==="WAITING_APPROVAL"?'<button onclick="openJobGlass(\''+id+'\',\'prepare\')">Préparer</button>':'')+
      (stopped?'<button class="secondary" onclick="openJobGlass(\''+id+'\',\'retry\')">Relancer</button>':'')+
      (done?'<button class="finish-action" onclick="openJobGlass(\''+id+'\',\'finish\')">✓ Confirmer la fin du travail</button>':'')+
      (stopped||["WAITING_APPROVAL","READY"].includes(item.status)?'<button class="danger" onclick="openJobGlass(\''+id+'\',\'delete\')">Supprimer</button>':'')+'</div>';
    let node=existing.get(item.id);
    if(!node){node=document.createElement("article");node.dataset.jobId=item.id;target.append(node)}
    existing.delete(item.id);
    node.className="job-card "+item.status.toLowerCase();
    if(node._content!==content){node.innerHTML=content;node._content=content}
  }
  for(const node of existing.values())node.remove();
  if(!items.length){target.innerHTML='<p class="muted">Aucun travail actif. Les travaux dont la fin a été confirmée restent dans l’historique.</p>'}
}
async function confirmFinish(id,button){
  if(button)button.disabled=true;
  try{await api("/api/v1/jobs/"+encodeURIComponent(id)+"/finish",{method:"POST"});tell("Fin confirmée. Le travail est retiré de la liste et conservé dans l’historique.");await refresh()}
  catch(error){tell("Confirmation de fin : "+error.message)}
  finally{if(button?.isConnected)button.disabled=false}
}
function selectJob(id){openJobGlass(id,"view")}
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
    $("historyText").textContent=results[4].map(item=>item.timestamp+" — "+item.action+" — "+item.result).join("\n");
    if($("processDocument"))$("processDocument").innerHTML=documents.map(item=>'<option value="'+esc(item.id)+'">'+esc(item.original_name)+"</option>").join("");
    if(jobs.some(item=>item.id===savedJob))$("job").value=savedJob;
    if(printers.some(item=>item.id===savedPrinter))$("printer").value=savedPrinter;
    const formValues=$("jobGlass")?.open?Object.fromEntries(["printer","copies","paper","orientation","color","pages","instructions","duplex"].map(id=>[id,$(id).type==="checkbox"?$(id).checked:$(id).value])):null;
    workshopSettings=results[7]||{};applyWorkshopSettings();
    if(formValues)for(const [id,value] of Object.entries(formValues)){if($(id).type==="checkbox")$(id).checked=value;else $(id).value=value}
    showJob();renderJobCards(jobs,docs);renderActivities(results[5]);renderMonitor(results[6]);checkPushAvailability();
  }catch(error){tell(error.message)}
}
async function showJob(){
  const job=jobs.find(item=>item.id===$("job").value),document=job&&docs[job.document_id];
  if(!job)setPrintProgress("",0,"Aucun travail sélectionné","Choisissez un travail ou envoyez un nouveau document.");
  const progress={WAITING_APPROVAL:[35,"En attente de préparation","Choisissez l’imprimante et les réglages."],READY:[58,"Prêt à confirmer","Les réglages sont validés. Confirmez pour envoyer au PC."],QUEUED:[76,"Commande en file d’attente","Le PC Windows va récupérer la commande."],PRINTING:[90,"Impression en cours","L’agent Windows a lancé l’impression."],COMPLETED:[100,"Impression terminée","Le document a été traité avec succès."],FAILED:[100,"Échec de l’impression",friendlyPrintError(job?.error_message||"Le serveur ou l’agent a signalé une erreur.")],CANCELLED:[100,"Travail annulé","Aucune impression ne sera lancée."]};
  if(job){const current=progress[job.status]||[10,job.status,"État reçu du serveur."];setPrintProgress(job.status==="FAILED"?"error":job.status==="COMPLETED"?"done":"busy",current[0],current[1],current[2])}
  const prepareButton=globalThis.document.querySelector('button[onclick="prepare()"]');
  const confirmButton=globalThis.document.querySelector('button[onclick="confirmJob()"]');
  const deleteButton=$("deleteJobBtn");
  if(prepareButton){prepareButton.disabled=!job||job.status!=="WAITING_APPROVAL";prepareButton.title=prepareButton.disabled?"Ce travail est déjà préparé ou envoyé":"Choisissez les réglages puis préparez le travail"}
  if(confirmButton){confirmButton.id="confirmPrintBtn";confirmButton.disabled=!job||job.status!=="READY";confirmButton.title=confirmButton.disabled?"Préparez d’abord le travail":"Confirmer l’impression"}
  if(deleteButton)deleteButton.classList.toggle("hidden",!job||!["WAITING_APPROVAL","READY","FAILED","CANCELLED","COMPLETED","IGNORED"].includes(job.status));
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
async function prepare(){const job=jobs.find(item=>item.id===$("job").value);if(!job||job.status!=="WAITING_APPROVAL"){tell(job?.status==="QUEUED"?"Ce travail est déjà envoyé à l’agent Windows.":"Ce travail n’est plus en attente de préparation.");return}setPrintProgress("busy",45,"Préparation des réglages","Vérification de l’imprimante et du format…");try{await api("/api/v1/jobs/"+encodeURIComponent($("job").value)+"/prepare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(printOptions())});setPrintProgress("busy",58,"Travail prêt","Réglages acceptés. Confirmation requise.");tell("Travail préparé. Vérifiez-le puis confirmez l’impression.");await refresh()}catch(error){operationError(error,"Préparation du travail")}}
async function confirmJob(){const job=jobs.find(item=>item.id===$("job").value);if(!job||job.status!=="READY"){tell(job?.status==="QUEUED"?"Commande déjà envoyée : le PC Windows va traiter ce travail.":"Préparez d’abord le travail avant de confirmer l’impression.");return}if(!confirm("Envoyer cette impression au PC Windows ?"))return;setPrintProgress("busy",78,"Envoi au PC Windows","Création de la commande d’impression…");try{await api("/api/v1/jobs/"+encodeURIComponent($("job").value)+"/confirm",{method:"POST"});setPrintProgress("busy",82,"Commande envoyée","En attente de prise en charge par l’agent.");tell("Commande envoyée à l’agent Windows.");await refresh()}catch(error){operationError(error,"Envoi de la commande")}}
async function cancelJob(){if(!confirm("Annuler ce travail ?"))return;setPrintProgress("busy",50,"Annulation en cours","Transmission de la demande au PC Windows…");try{await api("/api/v1/jobs/"+encodeURIComponent($("job").value)+"/cancel",{method:"POST"});setPrintProgress("done",100,"Travail annulé","La demande a été enregistrée.");tell("Annulation demandée.");await refresh()}catch(error){operationError(error,"Annulation du travail")}}
async function deleteJob(){const id=$("job").value;if(!id||!confirm("Supprimer définitivement ce travail de la liste ? Le document source sera conservé."))return;try{await api("/api/v1/jobs/"+encodeURIComponent(id),{method:"DELETE"});tell("Travail supprimé.");await refresh()}catch(error){tell(error.message)}}
async function deleteSpecificJob(id){if(!confirm("Supprimer définitivement ce travail ? Le document source sera conservé."))return;try{await api("/api/v1/jobs/"+encodeURIComponent(id),{method:"DELETE"});tell("Travail supprimé.");await refresh()}catch(error){operationError(error,"Suppression du travail")}}
async function retryJob(id){if(!confirm("Relancer ce travail et le remettre en attente de préparation ?"))return;setPrintProgress("busy",25,"Relance du travail","Nettoyage de l’ancienne commande…");try{const item=await api("/api/v1/jobs/"+encodeURIComponent(id)+"/retry",{method:"POST"});tell("Travail relancé : choisissez l’imprimante puis préparez-le.");await refresh();$("job").value=item.id;showJob();selectView("print")}catch(error){operationError(error,"Relance du travail")}}
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
function mountRegistrationField(){const password=$("password");if(password&&!$("displayName"))password.insertAdjacentHTML("afterend",'<label class="field-label" for="displayName">VOTRE NOM</label><input id="displayName" autocomplete="name" placeholder="Votre nom">')}
function addExtensionDownload(){const actions=document.querySelector("#dashboard .view-head .inline-actions");if(!actions||$("extensionDownload"))return;actions.insertAdjacentHTML("beforeend",'<a id="extensionDownload" class="secondary" href="/browser-extension.zip" download>Installer WhatsApp</a>')}
function mountChatStyle(){document.head.insertAdjacentHTML("beforeend",'<style>.chat-shell{max-width:900px;min-height:560px;display:flex;flex-direction:column;border:1px solid #ffffff16;border-radius:24px;background:linear-gradient(150deg,#0d1d30f2,#071522f5);box-shadow:0 22px 60px #0005;overflow:hidden}.chat-messages{flex:1;min-height:360px;max-height:58vh;overflow:auto;padding:24px;display:flex;flex-direction:column;gap:14px}.chat-welcome{display:flex;gap:13px;align-items:flex-start;color:#dceaf6;max-width:600px;margin:10px auto 20px}.assistant-orb{width:34px;height:34px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,#18c9b0,#3276f3);font-weight:900;box-shadow:0 0 22px #18c9b055}.chat-welcome p{margin:4px 0;color:#8faac0}.chat-bubble{max-width:78%;padding:13px 15px;border-radius:18px;line-height:1.55;animation:panelIn .25s ease both}.chat-bubble.user{align-self:flex-end;color:#fff;background:linear-gradient(135deg,#176eaa,#3151ad);border-bottom-right-radius:5px}.chat-bubble.assistant{align-self:flex-start;background:#10243a;border:1px solid #ffffff16;color:#dceaf6;border-bottom-left-radius:5px}.chat-bubble-head{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:#39d6bd;font-weight:800;margin-bottom:5px}.chat-bubble p{margin:0}.chat-bubble ol{margin:9px 0 0;padding-left:22px;color:#c3d7e7}.chat-bubble li{margin:5px 0}.typing{opacity:.65}.chat-next,.chat-confirm{width:auto}.chat-next{margin-top:10px;padding:8px 12px}.chat-confirm{margin:0 20px 14px;width:calc(100% - 40px)}.chat-suggestions{display:flex;gap:8px;flex-wrap:wrap;padding:0 20px 12px}.chip{width:auto;margin:0;padding:8px 11px;border-radius:999px;background:#ffffff0a;border:1px solid #ffffff1c;color:#bed2e1;font-size:.78rem;box-shadow:none}.chat-composer{display:flex;gap:10px;align-items:end;padding:14px 16px;background:#07121f;border-top:1px solid #ffffff12}.chat-composer textarea{min-height:45px;max-height:140px;margin:0;resize:none;border-radius:15px}.chat-composer button{width:48px;height:45px;margin:0;border-radius:14px;font-size:1.2rem}.arrival-popup{position:fixed;right:24px;bottom:24px;z-index:60;width:min(410px,calc(100vw - 32px));padding:22px;border:1px solid #2ee2c588;border-radius:22px;background:linear-gradient(145deg,#102d43f5,#0a1728f8);box-shadow:0 22px 70px #0009;animation:panelIn .3s ease both}.popup-close{position:absolute;right:12px;top:10px;width:32px;height:32px;border-radius:50%;padding:0;background:#ffffff10;box-shadow:none}.popup-file{font-weight:750;word-break:break-word}.popup-settings{padding:12px;border:1px solid #ffffff15;border-radius:12px;color:#9fe9db;background:#081722;margin:10px 0 14px;font-size:.84rem}@media(max-width:680px){.chat-bubble{max-width:92%}.chat-messages{padding:16px}.arrival-popup{right:16px;bottom:16px}}</style>')}
function applyTheme(mode){const theme=mode==="light"?"light":"dark";document.documentElement.dataset.theme=theme;localStorage.setItem("fusaa-theme",theme);const select=$("themeMode");if(select)select.value=theme;const button=$("themeToggle");if(button){button.textContent=theme==="light"?"☾ Sombre":"☀ Clair";button.setAttribute("aria-label",theme==="light"?"Activer le thème sombre":"Activer le thème clair")}}
function toggleTheme(){applyTheme(document.documentElement.dataset.theme==="light"?"dark":"light")}
function mountThemeControls(){const actions=document.querySelector(".top-actions");if(actions&&!$("themeToggle"))actions.insertAdjacentHTML("afterbegin",'<button id="themeToggle" class="signout theme-toggle" type="button" onclick="toggleTheme()"></button>');const settings=$("settings");if(settings&&!$("themeMode")){const head=settings.querySelector(".view-head");head?.insertAdjacentHTML("afterend",'<div class="panel theme-panel"><h2>Apparence</h2><p class="muted">Choisissez le thème de FUSAA sur toutes les pages.</p><label class="field-label" for="themeMode">THÈME</label><select id="themeMode" onchange="applyTheme(this.value)"><option value="dark">Sombre</option><option value="light">Clair</option></select></div>')}applyTheme(localStorage.getItem("fusaa-theme")||"dark")}
function mountThemeStyle(){document.head.insertAdjacentHTML("beforeend",'<style>.theme-toggle{width:auto;margin:0;padding:8px 11px;font-size:.78rem}.theme-panel{margin-bottom:16px}:root[data-theme="light"]{color-scheme:light}:root[data-theme="light"] body{background:radial-gradient(circle at 78% -10%,#cbeee955,transparent 32rem),#eef4f8;color:#172b3f}:root[data-theme="light"] .topbar{background:#ffffffed;border-color:#d9e4ec}:root[data-theme="light"] .sidebar{background:#f7fafc;border-color:#d9e4ec}:root[data-theme="light"] .nav a{color:#496275}:root[data-theme="light"] .nav a:hover,:root[data-theme="light"] .nav a.active{color:#12324a;background:linear-gradient(90deg,#17b6a71c,#2a73ee18)}:root[data-theme="light"] .view h1,:root[data-theme="light"] .view h2,:root[data-theme="light"] .view h3{color:#172b3f}:root[data-theme="light"] .panel{background:linear-gradient(145deg,#fffffffa,#f5f9fc);border-color:#d9e4ec;box-shadow:0 16px 42px #52708918}:root[data-theme="light"] input,:root[data-theme="light"] select,:root[data-theme="light"] textarea{color:#172b3f;background:#fff;border-color:#b8cbd8}:root[data-theme="light"] .muted{color:#5e7586}:root[data-theme="light"] .card{background:linear-gradient(135deg,#e8f4fa,#f7fbfd);border-color:#d5e3eb}:root[data-theme="light"] .card b{color:#172b3f}:root[data-theme="light"] .job,:root[data-theme="light"] .arrival{background:#f5f9fc;border-color:#d9e4ec;color:#172b3f}:root[data-theme="light"] .code{background:#eef4f8;color:#27475d;border-color:#d9e4ec}:root[data-theme="light"] .secondary{background:#eef4f8;color:#29475c;border-color:#cbdbe5}:root[data-theme="light"] .chat-shell{background:linear-gradient(150deg,#ffffff,#f3f8fb);border-color:#d9e4ec;box-shadow:0 22px 60px #52708922}:root[data-theme="light"] .chat-welcome{color:#172b3f}:root[data-theme="light"] .chat-welcome p,:root[data-theme="light"] .chat-bubble ol{color:#5e7586}:root[data-theme="light"] .chat-bubble.assistant{background:#edf5f9;border-color:#d9e4ec;color:#172b3f}:root[data-theme="light"] .chat-composer{background:#f3f7fa;border-color:#d9e4ec}:root[data-theme="light"] .chip{background:#eaf2f6;border-color:#cbdbe5;color:#36556b}:root[data-theme="light"] .arrival-popup{background:linear-gradient(145deg,#ffffff,#edf7f8);border-color:#24bca588;box-shadow:0 22px 70px #52708933}:root[data-theme="light"] .popup-settings{background:#eff8f7;border-color:#c7e7e1;color:#26766d}:root[data-theme="light"] .auth{background:linear-gradient(145deg,#fffffffa,#f5f9fc)}</style>')}
function mountProgressStyle(){document.head.insertAdjacentHTML("beforeend",'<style>.operation-progress,.print-progress{margin:16px 0;padding:16px;border:1px solid #25d2bb44;border-radius:16px;background:linear-gradient(135deg,#0a2132,#0b1828);box-shadow:0 0 30px #18c9b01c}.operation-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.operation-head b{display:block;font-size:.95rem}.operation-head strong,.operation-head span{color:#35dfc2;font-variant-numeric:tabular-nums}.progress-track{height:9px;margin:13px 0 8px;border-radius:999px;background:#ffffff12;overflow:hidden}.progress-track i{display:block;width:0;height:100%;border-radius:999px;background:linear-gradient(90deg,#18c9b0,#347bf5);box-shadow:0 0 18px #22d9c088;transition:width .45s ease;position:relative}.progress-track i:after{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent 20%,#ffffffaa 50%,transparent 80%);animation:progressShine 1.2s linear infinite}.progress-track i.error{background:linear-gradient(90deg,#e25762,#ff9c55);box-shadow:0 0 18px #e2576266}.progress-track i.done{background:linear-gradient(90deg,#25cfa4,#53df88)}@keyframes progressShine{from{transform:translateX(-100%)}to{transform:translateX(100%)}}.operation-progress small{color:#91b3c7}.print-steps{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin-top:13px}.print-steps span{padding:7px 4px;text-align:center;border-radius:8px;color:#7893a7;background:#ffffff08;font-size:.68rem;transition:all .3s ease}.print-steps span.done{color:#dffff8;background:#18c9b033;box-shadow:inset 0 -2px #25d2bb}.print-progress{animation:progressPulse 3s ease-in-out infinite}.print-progress .eyebrow{margin-bottom:3px}@keyframes progressPulse{50%{box-shadow:0 0 35px #18c9b02b}}:root[data-theme="light"] .operation-progress,:root[data-theme="light"] .print-progress{background:linear-gradient(135deg,#f4fbfc,#eef5fa);border-color:#8adfd1}:root[data-theme="light"] .print-steps span{color:#668093;background:#dceaf0}:root[data-theme="light"] .print-steps span.done{color:#17675d;background:#c9f0e8}@media(max-width:680px){.print-steps span{font-size:.58rem;padding:6px 2px}.operation-head{align-items:flex-start;flex-direction:column;gap:3px}}</style>')}
function mountJobStyle(){document.head.insertAdjacentHTML("beforeend",'<style>#jobs{display:grid;gap:12px;margin-top:18px}.job-card{position:relative;padding:16px;border:1px solid #ffffff14;border-radius:17px;background:linear-gradient(135deg,#0d2539,#0a1728);overflow:hidden;animation:panelIn .35s ease both}.job-card:before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:#22d5bd}.job-card.failed:before{background:#ef6570}.job-card.completed:before{background:#55dc8d}.job-card-head{display:flex;justify-content:space-between;align-items:start;gap:10px}.job-card-head h3{margin:7px 0 0;font-size:.96rem;word-break:break-word}.job-card-head strong{color:#41dfc4;font-size:1.1rem}.job-badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#20cdb52b;color:#64ead1;font-size:.66rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.failed .job-badge{background:#ef65702b;color:#ff9ca3}.completed .job-badge{background:#55dc8d2b;color:#8bf0ac}.job-mini-track{height:6px;margin:13px 0 7px;background:#ffffff12;border-radius:99px;overflow:hidden}.job-mini-track i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#20cdb5,#347bf5);transition:width .6s ease}.failed .job-mini-track i{background:#ef6570}.completed .job-mini-track i{background:#55dc8d}.job-card-meta{display:flex;justify-content:space-between;color:#8da8ba;font-size:.73rem}.job-error{margin:10px 0;color:#ff9ca3;font-size:.78rem;line-height:1.4}.job-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.job-actions button{width:auto;margin:0;padding:7px 10px;font-size:.74rem}.job-card.selected{box-shadow:0 0 0 2px #22d5bd66}@media(max-width:680px){.job-card-head h3{font-size:.86rem}}</style>')}
mountAssistant();mountSettings();mountArrivals();mountArrivalPopup();mountChatStyle();mountStyle();compactNavigation();addExtensionDownload();mountRegistrationField();applyTheme(localStorage.getItem("fusaa-theme")||"dark");mountThemeStyle();mountThemeControls();mountProgressStyle();mountJobStyle();
document.querySelector("#print .view-head").insertAdjacentElement("afterend", $("jobs"));
document.head.insertAdjacentHTML("beforeend", `<style>
#jobs{margin:0 0 24px;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr))}
.job-card{padding:22px;border-radius:22px;border-color:#36ddc34d;box-shadow:0 14px 36px #00132125}
.job-card .print-steps{grid-template-columns:repeat(5,minmax(0,1fr));margin:16px 0}
.job-card .print-steps span{white-space:normal;overflow-wrap:anywhere}
.job-card .job-actions{gap:10px}
.job-card .job-finish-note{font-size:.82rem;color:#86e4c3}
.job-card .finish-action{background:linear-gradient(115deg,#08795c,#126baf);color:white}
.job-card.queued .job-mini-track i,.job-card.printing .job-mini-track i{background-size:200% 100%;animation:jobFlow 2s linear infinite}
@keyframes jobFlow{to{background-position:200% 0}}
:root[data-theme="light"] .job-card{background:linear-gradient(135deg,#fff,#eaf6fa);border-color:#96d5d0;box-shadow:0 14px 34px #36596f15}
:root[data-theme="light"] .job-card h3{color:#173c50}
:root[data-theme="light"] .job-card-head strong,:root[data-theme="light"] .job-badge{color:#006858}
:root[data-theme="light"] .job-card-meta{color:#46667a}
:root[data-theme="light"] .job-error,:root[data-theme="light"] .failed .job-badge{color:#a12c3b}
:root[data-theme="light"] .job-card .job-finish-note{color:#17654e}
:root[data-theme="light"] .job-mini-track{background:#cadde5}
button:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}
@media(prefers-reduced-motion:reduce){.job-card,.print-progress,.progress-track i:after,.job-mini-track i{animation:none!important;transition:none!important}}
</style>`);
let glassAction=null,glassBusy=false;
function mountJobGlass(){
  const editor=document.querySelector("#print > .panel");
  document.body.insertAdjacentHTML("beforeend",'<dialog id="jobGlass" aria-labelledby="glassTitle"><header class="glass-header"><div><span class="eyebrow">FUSAA · ATELIER</span><h2 id="glassTitle"></h2></div><button type="button" class="secondary glass-close" aria-label="Fermer">×</button></header><p id="glassFile"></p><p id="glassFeedback" role="status"></p><div id="glassEditor"></div><section id="glassDecision" hidden><p id="glassExplanation"></p><div class="inline-actions"><button id="glassExecute" type="button"></button><button id="glassBack" type="button" class="secondary">Retour</button></div></section></dialog>');
  $("glassEditor").append(editor);
  $("jobGlass").querySelector(".glass-close").onclick=closeJobGlass;
  $("glassBack").onclick=closeJobGlass;
  $("glassExecute").onclick=executeGlassAction;
  $("jobGlass").addEventListener("cancel",event=>{if(glassBusy)event.preventDefault()});
  $("jobGlass").addEventListener("close",()=>{document.body.classList.remove("glass-open");glassAction=null});
}
function closeJobGlass(){if(!glassBusy)$("jobGlass").close()}
function openJobGlass(id,mode="view"){
  if(glassBusy)return;
  const job=jobs.find(item=>item.id===id);if(!job)return;
  glassAction={id,mode};
  $("job").value=id;
  $("glassFeedback").textContent="";
  $("glassFile").textContent=docs[job.document_id]?.original_name||id;
  const decision=["finish","retry","delete"].includes(mode);
  $("glassEditor").hidden=decision;
  $("glassDecision").hidden=!decision;
  const titles={view:"Aperçu et suivi",prepare:"Paramétrer l’impression",finish:"Confirmer la fin du travail",retry:"Relancer le travail",delete:"Supprimer le travail"};
  $("glassTitle").textContent=titles[mode]||titles.view;
  $("glassExecute").textContent=titles[mode]||"Confirmer";
  $("glassExplanation").textContent=mode==="finish"?"Confirmez que le travail est terminé. Il sera retiré de la liste active et conservé dans l’historique.":mode==="delete"?"Ce travail sera supprimé de la liste. Le document source sera conservé.":mode==="retry"?"Le travail sera remis en préparation. Vérifiez la sortie papier avant de relancer une impression échouée.":"";
  // Reuse the existing form and its IDs; no duplicate print controls.
  for(const [field,key] of [["printer","printer_id"],["copies","copies"],["paper","paper_size"],["orientation","orientation"],["color","color_mode"],["pages","pages"],["instructions","instructions"]]){
    if(job[key]!=null)$(field).value=job[key];
  }
  if(job.duplex!=null)$("duplex").checked=job.duplex;
  showJob();
  if(!$("jobGlass").open)$("jobGlass").showModal();
  document.body.classList.add("glass-open");
}
async function executeGlassAction(){
  if(glassBusy||!glassAction)return;
  const {id,mode}=glassAction;
  if(!["finish","retry","delete"].includes(mode))return;
  glassBusy=true;$("glassExecute").disabled=true;
  $("glassFeedback").textContent="Traitement en cours…";
  try{
    await api("/api/v1/jobs/"+encodeURIComponent(id)+(mode==="delete"?"":mode==="retry"?"/retry":"/finish"),{method:mode==="delete"?"DELETE":"POST"});
    await refresh();
    glassBusy=false;
    if(mode==="retry")openJobGlass(id,"prepare");
    else{$("jobGlass").close();tell(mode==="finish"?"Fin confirmée : travail retiré de la liste active.":"Travail supprimé.")}
  }catch(error){$("glassFeedback").textContent=error.message}
  finally{glassBusy=false;$("glassExecute").disabled=false}
}
mountJobGlass();
document.head.insertAdjacentHTML("beforeend",`<style>
body.glass-open{overflow:hidden}
#jobGlass{color:#e9f4ff;width:min(920px,calc(100vw - 28px));max-height:88dvh;overflow:auto;padding:26px;border:1px solid #b2ffed55;border-radius:26px;background:linear-gradient(135deg,#133045ed,#081827eb);backdrop-filter:blur(26px) saturate(150%);box-shadow:inset 0 1px 0 #ffffff50,0 32px 100px #0008}
#jobGlass::backdrop{background:#04111b70;backdrop-filter:blur(8px)}
#jobGlass[open]{animation:glassEntrance .24s ease-out}
.glass-header{display:flex;align-items:center;justify-content:space-between;gap:16px}
.glass-header h2{margin:0;font-size:1.35rem}.glass-close{width:40px;height:40px;padding:4px;font-size:1.5rem}
#glassFile{overflow-wrap:anywhere;color:#7de4d0}
#glassFeedback{white-space:pre-wrap;color:#ffbe90}
#glassFeedback:empty{display:none}
#glassEditor>.panel{background:transparent;border:0;padding:0;box-shadow:none;animation:none}
#glassEditor .preview{max-height:240px}
#glassEditor #job{display:none}
#glassEditor label:has(+ #job){display:none}
#glassDecision{padding:18px 0}
:root[data-theme="light"] #jobGlass{color:#16374c;background:linear-gradient(135deg,#ffffffed,#e6f3f6ed);border-color:#ffffffd0}
:root[data-theme="light"] #glassFile{color:#176b60}
:root[data-theme="light"] #glassFeedback{color:#9c3b17}
@keyframes glassEntrance{from{opacity:0;transform:translateY(14px) scale(.98)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){#jobGlass[open]{animation:none}}
@media(max-width:600px){#jobGlass{padding:16px;border-radius:20px;max-height:92dvh}}
</style>`);
document.querySelector("main").insertAdjacentHTML("afterbegin",'<p id="globalMessage" role="status" hidden></p>');
document.querySelectorAll("#nav a").forEach(link=>link.addEventListener("click",event=>{event.preventDefault();selectView(link.dataset.view)}));
window.addEventListener("online",()=>{network();flushUploads();refresh()});window.addEventListener("offline",network);
function syncViewFromHash(){const view=location.hash.replace(/^#/,"");if(view&&$(view))selectView(view)}
window.addEventListener("hashchange",syncViewFromHash);
syncViewFromHash();
if(token)restoreWorkspace().then(()=>{state();refresh();connectEvents();flushUploads();syncViewFromHash()}).catch(error=>tell(error.message));
