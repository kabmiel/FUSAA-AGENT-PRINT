/* Boutique: local CSV review and photo previews; publication is explicit. */
(()=>{
  const MAX_ROWS=500,MAX_FILE=10*1024*1024;
  const icon=paths=>'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+paths+'</svg>';
  const icons={upload:icon('<path d="M12 16V3m-4 4 4-4 4 4M4 16v5h16v-5"/>'),photo:icon('<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 3-3 6 6"/>'),check:icon('<path d="m5 12 4 4L19 6"/>'),trash:icon('<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>')};
  const state={rows:[],categories:[],requestId:null,organization:null,busy:false,done:false,cancel:false,xhr:null};
  const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('fr').replace(/[^a-z0-9]/g,'');
  const imageName=value=>normalize(String(value||'').replace(/\.[^.]+$/,''));
  const node=id=>document.getElementById(id);
  function mount(){
    if(node('shopBulkImport'))return;
    document.querySelector('main')?.insertAdjacentHTML('beforeend',`<section id="shopBulkImport" class="view"><div class="view-head"><div><p class="eyebrow">BOUTIQUE FUSAA · IMPORT PAR LOT</p><h1>Préparer mes produits</h1></div><button type="button" class="secondary" onclick="selectView('shopProductsManage')">Retour au catalogue</button></div><div class="shop-bulk-steps"><span>1 · Charger la liste</span><span>2 · Vérifier et ajouter les photos</span><span>3 · Enregistrer le lot</span></div><section class="panel shop-bulk-source"><div><h2>Une liste, puis les images</h2><p>CSV, TSV ou liste copiée depuis Excel. Rien n’est publié avant votre validation.</p></div><div class="shop-bulk-source-actions"><button type="button" id="bulkChooseList">${icons.upload} Charger la liste</button><button type="button" class="secondary" id="bulkTemplate">Modèle CSV</button><button type="button" class="secondary" id="bulkPasteToggle">Coller une liste</button><input id="bulkListFile" type="file" accept=".csv,.tsv,.txt,text/csv,text/tab-separated-values" hidden></div><div id="bulkPasteBox" hidden><textarea id="bulkPaste" rows="4" placeholder="Produit;Prix;Stock\nRamette A4;3500;10"></textarea><button type="button" id="bulkReadPaste">Analyser la liste</button></div><p id="bulkSourceMessage" class="shop-bulk-message" role="status"></p></section><div id="bulkReview" hidden><div class="shop-bulk-toolbar"><div id="bulkCounters" class="shop-bulk-counters" aria-live="polite"></div><input id="bulkSearch" type="search" placeholder="Rechercher dans le récapitulatif" aria-label="Rechercher un produit"><button type="button" class="secondary" id="bulkChooseImages">${icons.photo} Ajouter plusieurs photos</button><input id="bulkImages" type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple hidden></div><p class="shop-bulk-hint">Ajoutez une photo à côté de chaque produit, ou choisissez plusieurs photos nommées comme vos produits.</p><div id="bulkRows" class="shop-bulk-rows"></div><div class="shop-bulk-footer panel"><label><input id="bulkRequireImages" type="checkbox"> Exiger une image pour chaque produit</label><div><button type="button" id="bulkSave">${icons.check} Enregistrer le lot</button><button type="button" class="secondary" id="bulkClear">Vider la préparation</button></div></div></div><section id="bulkProgress" class="panel shop-bulk-progress" hidden aria-live="polite"><div><b id="bulkProgressLabel"></b><strong id="bulkPercent">0 %</strong></div><progress id="bulkProgressBar" max="100" value="0"></progress><p id="bulkProgressDetail"></p><button type="button" class="secondary" id="bulkStop">Interrompre l’envoi</button></section><section id="bulkSuccess" class="panel" hidden><h2>Lot enregistré</h2><p id="bulkSuccessMessage"></p><button type="button" onclick="selectView('shopProductsManage')">Voir les produits</button></section><dialog id="bulkConfirm" class="shop-bulk-dialog"><h2 id="bulkConfirmTitle"></h2><p id="bulkConfirmText"></p><div><button type="button" data-confirm>Confirmer</button><button type="button" class="secondary" data-cancel>Annuler</button></div></dialog><dialog id="bulkPhotoDialog" class="shop-bulk-dialog shop-bulk-photo-dialog"><button type="button" class="secondary" aria-label="Fermer l’aperçu" onclick="document.getElementById('bulkPhotoDialog').close()">×</button><img id="bulkPhotoLarge" alt="Aperçu de l’image du produit"></dialog></section>`);
    node('bulkChooseList').onclick=()=>node('bulkListFile').click();
    node('bulkListFile').onchange=event=>readFile(event.target.files[0]);
    node('bulkTemplate').onclick=downloadTemplate;
    node('bulkPasteToggle').onclick=()=>{node('bulkPasteBox').hidden=!node('bulkPasteBox').hidden;if(!node('bulkPasteBox').hidden)node('bulkPaste').focus()};
    node('bulkReadPaste').onclick=()=>loadText(node('bulkPaste').value);
    node('bulkSearch').oninput=()=>{const query=normalize(node('bulkSearch').value);state.rows.forEach(row=>{row.element.hidden=!normalize(row.name).includes(query)})};
    node('bulkChooseImages').onclick=()=>node('bulkImages').click();
    node('bulkImages').onchange=event=>matchImages([...event.target.files]);
    node('bulkRequireImages').onchange=refresh;
    node('bulkSave').onclick=save;
    node('bulkClear').onclick=async()=>{if(await confirmAction('Vider la préparation ?','Aucun produit ne sera supprimé du catalogue.'))clearDraft()};
    node('bulkStop').onclick=()=>{state.cancel=true;state.xhr?.abort()};
    document.querySelector('#shopProductsManage .view-head .inline-actions')?.insertAdjacentHTML('beforeend','<button type="button" class="secondary" onclick="openShopBulkImport()">'+icons.upload+' Importer par lot</button>');
    window.addEventListener('beforeunload',event=>{if(state.rows.length&&!state.done){event.preventDefault();event.returnValue=''}});
  }
  async function open(){
    mount();if(!org){tell('Connectez-vous avant de préparer les produits.');return}
    if(state.organization&&state.organization!==org)clearDraft();state.organization=org;
    selectView('shopBulkImport');
    if(!state.categories.length){try{state.categories=shopProductPage.categories?.length?shopProductPage.categories:await api('/api/v1/shop/admin/categories?organization_id='+encodeURIComponent(org));shopProductPage.categories=state.categories}catch(error){message(error.message)}}
  }
  function message(text){node('bulkSourceMessage').textContent=text||''}
  function confirmAction(title,text){
    return new Promise(resolve=>{const dialog=node('bulkConfirm');node('bulkConfirmTitle').textContent=title;node('bulkConfirmText').textContent=text;let settled=false;const finish=value=>{if(settled)return;settled=true;dialog.close();resolve(value)};dialog.querySelector('[data-confirm]').onclick=()=>finish(true);dialog.querySelector('[data-cancel]').onclick=()=>finish(false);dialog.oncancel=event=>{event.preventDefault();finish(false)};dialog.showModal()});
  }
  function clearDraft(){
    state.rows.forEach(row=>{if(row.objectUrl)URL.revokeObjectURL(row.objectUrl)});state.rows=[];state.requestId=null;state.done=false;
    node('bulkRows').replaceChildren();node('bulkReview').hidden=true;node('bulkProgress').hidden=true;node('bulkSuccess').hidden=true;node('bulkSearch').value='';node('bulkListFile').value='';message('');
  }
  function parseCsv(text){
    text=String(text||'').replace(/^\uFEFF/,'');
    if(text.length>5*1024*1024)throw Error('La liste est limitée à 5 Mo.');
    const line=text.split(/\r?\n/).find(value=>value.trim())||'';
    const counts=[';','\t',','].map(separator=>{let count=0,quoted=false;for(let i=0;i<line.length;i++){if(line[i]==='"'){if(quoted&&line[i+1]==='"')i++;else quoted=!quoted}else if(!quoted&&line[i]===separator)count++}return {separator,count}}).sort((a,b)=>b.count-a.count);
    const separator=counts[0].count?counts[0].separator:';';
    const rows=[];let fields=[],value='',quoted=false;
    const finishRow=()=>{fields.push(value.trim());if(fields.some(cell=>cell!==''))rows.push(fields);fields=[];value='';if(rows.length>MAX_ROWS+1)throw Error('Maximum 500 produits par lot.')};
    for(let index=0;index<text.length;index++){
      const char=text[index];
      if(char==='"'){if(quoted&&text[index+1]==='"'){value+='"';index++}else if(quoted||value.trim()==='')quoted=!quoted;else value+=char}
      else if(!quoted&&char===separator){fields.push(value.trim());value=''}
      else if(!quoted&&(char==='\n'||char==='\r')){if(char==='\r'&&text[index+1]==='\n')index++;finishRow()}
      else value+=char;
    }
    if(quoted)throw Error('Une cellule contient des guillemets non fermés.');
    if(value!==''||fields.length)finishRow();
    if(!rows.length)throw Error('La liste ne contient aucun produit.');
    return rows;
  }
  const aliases={name:['produit','nom','nomduproduit','designation','name','product'],price_xof:['prix','prixfcfa','prixunitaire','prixdevente','prixvente','prixventeFCFA','unitprice','unitamount','price','pricexof'],stock_quantity:['stock','quantite','stockinitial','quantiteenstock','stockquantity'],brand:['marque','brand'],category:['categorie','category','categoryid'],description:['description','designationcomplete'],original_price_xof:['prixnormal','ancienprix','prixavantreduction','originalpricexof'],condition:['etat','condition'],image:['image','photo','imageurl','urlimage','imagefile','fichierimage']};
  function numberValue(value){
    let text=String(value??'').trim().replace(/(?:f\s*cfa|xof)/gi,'').replace(/[\s\u00a0\u202f]/g,'');
    if(!text)return '';
    if(/^\d{1,3}([.,]\d{3})+$/.test(text))text=text.replace(/[.,]/g,'');
    else if(text.includes(',')&&text.includes('.'))text=text.lastIndexOf(',')>text.lastIndexOf('.')?text.replace(/\./g,'').replace(',','.'):text.replace(/,/g,'');
    else text=text.replace(',','.');
    return /^\d+(\.\d+)?$/.test(text)&&Number.isFinite(Number(text))?Number(text):'';
  }
  function prepareRows(cells){
    const headings=cells[0].map(normalize),columns={};
    Object.entries(aliases).forEach(([key,values])=>{const index=headings.findIndex(value=>values.some(alias=>normalize(alias)===value));if(index>=0)columns[key]=index});
    const hasHeader=columns.name!==undefined;
    if(hasHeader&&columns.price_xof===undefined)throw Error('Ajoutez une colonne Prix ou Prix unitaire dans la liste.');
    if(!hasHeader)Object.assign(columns,{name:0,price_xof:1,stock_quantity:2});
    const rows=(hasHeader?cells.slice(1):cells).map((values,index)=>{
      const get=key=>columns[key]===undefined?'':values[columns[key]]||'';
      const category=get('category'),match=state.categories.find(item=>item.id===category||normalize(item.name)===normalize(category)),image=get('image');
      return {client_key:newId(),name:get('name'),price_xof:numberValue(get('price_xof')),stock_quantity:get('stock_quantity')===''?0:numberValue(get('stock_quantity')),brand:get('brand'),description:get('description'),original_price_xof:numberValue(get('original_price_xof')),category_id:match?.id||'',categoryProblem:category&&!match?'Catégorie « '+category+' » inconnue : choisissez une catégorie ou Sans catégorie.':'',condition:/^(occasion|used)$/i.test(get('condition'))?'USED':'NEW',image_url:/^https?:\/\//i.test(image)?image:'',imageHint:image&&!/^https?:\/\//i.test(image)?image:'',file:null,objectUrl:null,uploaded:null,errors:[],serverErrors:[],sourceLine:index+(hasHeader?2:1)};
    });
    if(!rows.length||rows.length>MAX_ROWS)throw Error('La liste doit contenir de 1 à 500 produits.');return rows;
  }
  async function readFile(file){
    if(!file)return;if(file.size>5*1024*1024){message('Le fichier est limité à 5 Mo.');return}
    if(!/\.(csv|tsv|txt)$/i.test(file.name)){message('Enregistrez votre liste Excel au format CSV, puis chargez ce fichier.');return}
    try{const buffer=await file.arrayBuffer();let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(buffer)}catch{text=new TextDecoder('windows-1252').decode(buffer)}await loadText(text)}catch(error){message(error.message)}
  }
  async function loadText(text){
    if(state.busy)return;
    try{const rows=prepareRows(parseCsv(text));if(state.rows.length&&!state.done&&!await confirmAction('Remplacer la préparation ?','Les photos de la préparation actuelle seront retirées, sans toucher aux produits existants.'))return;clearDraft();state.rows=rows;state.requestId=newId();state.organization=org;node('bulkReview').hidden=false;render();message(rows.length+' produits analysés. Vérifiez les champs et ajoutez les photos avant d’enregistrer.')}catch(error){message(error.message)}
  }
  function downloadTemplate(){
    const blob=new Blob(['\uFEFFProduit;Prix;Stock;Marque;Categorie;Description;Prix normal;Etat;Image\r\nRamette A4;3500;10;;;Papier A4;4000;Neuf;ramette-a4.jpg\r\n'],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='modele-produits-boutique.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function categoryOptions(row){return '<option value="">Sans catégorie</option>'+state.categories.map(item=>'<option value="'+esc(item.id)+'" '+(row.category_id===item.id?'selected':'')+'>'+esc(item.name)+'</option>').join('')}
  function field(key,label,value,type='text'){return '<label>'+label+'<input data-field="'+key+'" type="'+type+'" '+(type==='number'?'min="0" step="'+(key==='stock_quantity'?'1':'0.01')+'"':'')+' value="'+esc(value)+'"></label>'}
  function render(){
    node('bulkRows').innerHTML=state.rows.map((row,index)=>'<article class="shop-bulk-row" data-key="'+row.client_key+'"><div class="shop-bulk-row-photo"><button type="button" class="shop-bulk-thumb" data-action="preview" aria-label="Voir l’image du produit">'+icons.photo+'</button><button type="button" class="secondary shop-bulk-photo-button" data-action="image">'+icons.photo+' Ajouter photo</button><input data-file type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden><small class="shop-bulk-photo-name"></small><button type="button" class="shop-bulk-remove-photo secondary" data-action="remove-image" hidden>Retirer l’image</button></div><div class="shop-bulk-row-fields"><div class="shop-bulk-row-top"><b>Produit '+(index+1)+'</b><button type="button" class="secondary shop-bulk-remove" data-action="remove" aria-label="Retirer ce produit du lot">'+icons.trash+'</button></div><div class="shop-bulk-edit-grid">'+field('name','Produit',row.name)+field('price_xof','Prix FCFA',row.price_xof,'number')+field('stock_quantity','Stock',row.stock_quantity,'number')+'<label>Catégorie<select data-field="category_id">'+categoryOptions(row)+'</select></label></div><details><summary>Marque, description et autres options</summary><div class="shop-bulk-edit-grid">'+field('brand','Marque',row.brand)+field('original_price_xof','Prix normal avant réduction',row.original_price_xof,'number')+'<label>État<select data-field="condition"><option value="NEW">Neuf</option><option value="USED" '+(row.condition==='USED'?'selected':'')+'>Occasion</option></select></label>'+field('image_url','URL de l’image (facultative)',row.image_url,'url')+'<label class="wide">Description<textarea data-field="description" rows="2">'+esc(row.description)+'</textarea></label></div></details><p class="shop-bulk-row-status" role="status"></p></div></article>').join('');
    state.rows.forEach(row=>{
      row.element=node('bulkRows').querySelector('[data-key="'+row.client_key+'"]');updatePhoto(row);
      row.element.querySelectorAll('[data-field]').forEach(input=>input.oninput=()=>{row[input.dataset.field]=input.value;row.serverErrors=[];if(input.dataset.field==='category_id')row.categoryProblem='';if(input.dataset.field==='image_url'){row.uploaded=null;updatePhoto(row)}refresh()});
      row.element.querySelector('[data-file]').onchange=event=>chooseImage(row,event.target.files[0]);
      row.element.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>{
        const action=button.dataset.action;
        if(action==='image')row.element.querySelector('[data-file]').click();
        if(action==='preview'){const src=row.objectUrl||row.image_url;if(src){node('bulkPhotoLarge').src=src;node('bulkPhotoDialog').showModal()}}
        if(action==='remove-image'){if(row.objectUrl)URL.revokeObjectURL(row.objectUrl);Object.assign(row,{file:null,objectUrl:null,uploaded:null,image_url:'',imageError:'',imageHint:''});row.element.querySelector('[data-field="image_url"]').value='';updatePhoto(row);refresh()}
        if(action==='remove'){if(row.objectUrl)URL.revokeObjectURL(row.objectUrl);state.rows=state.rows.filter(item=>item!==row);row.element.remove();state.rows.forEach((item,index)=>item.element.querySelector('.shop-bulk-row-top>b').textContent='Produit '+(index+1));refresh()}
      });
    });refresh();
  }
  function updatePhoto(row){
    const source=row.objectUrl||(/^https?:\/\//i.test(row.image_url)?row.image_url:''),button=row.element.querySelector('.shop-bulk-thumb');
    button.innerHTML=source?'<img src="'+esc(source)+'" alt="'+esc(row.name)+'" loading="lazy" decoding="async">':icons.photo;
    const image=button.querySelector('img');if(image)image.onerror=()=>{button.innerHTML='<span>Image non disponible</span>'};
    row.element.querySelector('.shop-bulk-photo-name').textContent=row.file?.name||row.imageHint||'';
    row.element.querySelector('.shop-bulk-remove-photo').hidden=!source;
    row.element.querySelector('[data-action="image"]').innerHTML=icons.photo+(source?' Changer photo':' Ajouter photo');
  }
  async function chooseImage(row,file){
    if(!file||state.busy||state.done)return;
    try{
      if(!['image/jpeg','image/png','image/webp','image/gif'].includes(file.type)||file.size>MAX_FILE)throw Error('Choisissez JPG, PNG, WEBP ou GIF, de 10 Mo maximum.');
      row.decoding=true;refresh();const bitmap=await createImageBitmap(file);
      try{if(bitmap.width>1200||bitmap.height>1200){const scale=Math.min(1200/bitmap.width,1200/bitmap.height),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);if(file.type!=='image/gif'){const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',.86));if(blob)file=new File([blob],file.name.replace(/\.[^.]+$/,'')+'.webp',{type:blob.type})}}}finally{bitmap.close()}
      if(!state.rows.includes(row))return;if(row.objectUrl)URL.revokeObjectURL(row.objectUrl);
      row.file=file;row.objectUrl=URL.createObjectURL(file);row.uploaded=null;row.imageError='';row.serverErrors=[];row.element.querySelector('[data-file]').value='';updatePhoto(row);
    }catch(error){row.imageError=error.message||'Impossible de lire cette image.'}finally{row.decoding=false;refresh()}
  }
  async function matchImages(files){
    if(state.busy||state.done)return;let matched=0,unmatched=[];
    for(const file of files){const key=imageName(file.name),rows=state.rows.filter(row=>imageName(row.imageHint||row.name)===key);if(rows.length===1){await chooseImage(rows[0],file);matched++}else unmatched.push(file.name)}
    message(matched+' image(s) associée(s).'+(unmatched.length?' À ajouter manuellement : '+unmatched.slice(0,8).join(', '):''));node('bulkImages').value='';
  }
  function refresh(){
    const seen=new Map(),requireImages=node('bulkRequireImages').checked;
    state.rows.forEach(row=>{const key=normalize(row.name);if(key)seen.set(key,(seen.get(key)||0)+1)});
    let errorCount=0,images=0,bytes=0;
    state.rows.forEach(row=>{
      const errors=[],price=Number(row.price_xof),stock=Number(row.stock_quantity),normal=row.original_price_xof===''?null:Number(row.original_price_xof);
      if(!row.name.trim()||row.name.length>255)errors.push('Nom obligatoire, 255 caractères maximum.');
      if(seen.get(normalize(row.name))>1)errors.push('Produit en doublon dans la liste.');
      if(row.price_xof===''||!Number.isFinite(price)||price<0||price>9999999999.99)errors.push('Prix de vente invalide.');
      if(row.stock_quantity===''||!Number.isInteger(stock)||stock<0||stock>2147483647)errors.push('Le stock doit être un nombre entier valide, positif ou zéro.');
      if(normal!==null&&(!Number.isFinite(normal)||normal<price||normal>9999999999.99))errors.push('Le prix normal doit être valide et supérieur ou égal au prix de vente.');
      if(row.brand.length>100||row.description.length>12000)errors.push('Marque ou description trop longue.');
      if(row.categoryProblem)errors.push(row.categoryProblem);
      if(!row.file&&row.image_url&&!/^https?:\/\//i.test(row.image_url))errors.push('L’image doit être une URL HTTP ou HTTPS.');
      if(row.image_url.length>2048)errors.push('URL de l’image trop longue.');
      if(row.imageError)errors.push(row.imageError);
      const hasImage=!!(row.file||row.image_url);if(hasImage)images++;if(row.file)bytes+=row.file.size;
      if(requireImages&&!hasImage)errors.push('Ajoutez une image pour ce produit.');
      row.errors=[...errors,...row.serverErrors];if(row.errors.length)errorCount++;
      row.element.dataset.state=row.errors.length?'error':state.done?'saved':'ready';
      row.element.querySelector('.shop-bulk-row-status').textContent=row.errors.length?row.errors.join(' · '):state.done?'Enregistré dans la Boutique':row.decoding?'Préparation de la photo…':hasImage?'Prêt · image ajoutée':'Prêt · sans image';
    });
    node('bulkCounters').innerHTML='<span><b>'+state.rows.length+'</b> produits</span><span><b>'+images+'</b> avec image</span><span class="'+(errorCount?'has-errors':'')+'"><b>'+errorCount+'</b> à corriger</span>';
    node('bulkSave').disabled=state.busy||state.done||!state.rows.length||errorCount>0||state.rows.some(row=>row.decoding)||bytes>100*1024*1024;
    node('bulkSave').innerHTML=icons.check+(state.done?' Lot enregistré':' Enregistrer '+state.rows.length+' produits');
    if(bytes>100*1024*1024)message('Les photos dépassent 100 Mo. Préparez un lot plus petit.');
  }
  function payload(){return {request_id:state.requestId,items:state.rows.map(row=>({client_key:row.client_key,name:row.name.trim(),brand:row.brand.trim()||null,price_xof:Number(row.price_xof),original_price_xof:row.original_price_xof===''?null:Number(row.original_price_xof),stock_quantity:Number(row.stock_quantity),category_id:row.category_id||null,condition:row.condition,description:row.description.trim(),image_url:row.uploaded?.image_url||(row.file?null:row.image_url.trim()||null),cloudinary_public_id:row.uploaded?.cloudinary_public_id||null,enabled:true,specifications:{}}))}}
  function lock(busy){
    state.busy=busy;node('shopBulkImport').setAttribute('aria-busy',String(busy));
    node('shopBulkImport').querySelectorAll('button,input,select,textarea').forEach(element=>element.disabled=busy);
    node('bulkStop').disabled=false;node('bulkStop').hidden=!busy;
    if(state.done)state.rows.forEach(row=>row.element.querySelectorAll('button,input,select,textarea').forEach(element=>element.disabled=true));
    refresh();
  }
  function progress(percent,label,detail=''){
    node('bulkProgress').hidden=false;node('bulkProgressLabel').textContent=label;node('bulkProgressDetail').textContent=detail;node('bulkProgressBar').value=percent;node('bulkPercent').textContent=Math.round(percent)+' %';
  }
  function complete(result){
    state.done=true;progress(100,'Lot enregistré',result.created+' produit(s) dans la Boutique.');node('bulkSuccess').hidden=false;
    node('bulkSuccessMessage').textContent=result.created+' produit(s) enregistré(s).'+(result.already_saved?' Le lot avait déjà été enregistré : aucun doublon n’a été ajouté.':' Les images et les données ont été publiées ensemble.');
  }
  async function uploadImage(row,index,total){
    const signed=await api('/api/v1/shop/admin/cloudinary/signature?organization_id='+encodeURIComponent(state.organization),{method:'POST',silentOperation:true});
    if(state.cancel)throw Error('Envoi interrompu avant la publication.');
    const body=new FormData();body.append('file',row.file);
    for(const key of ['api_key','timestamp','signature','folder','public_id'])body.append(key,String(signed[key]));
    return await new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();state.xhr=xhr;xhr.open('POST','https://api.cloudinary.com/v1_1/'+encodeURIComponent(signed.cloud_name)+'/image/upload');xhr.timeout=120000;
      xhr.upload.onprogress=event=>{if(event.lengthComputable)progress(10+75*(index+event.loaded/event.total)/total,'Envoi de la photo '+(index+1)+' / '+total,row.name)};
      const fail=text=>{state.xhr=null;reject(Error(text))};
      xhr.onerror=()=>fail('Connexion interrompue pendant l’envoi de la photo.');xhr.ontimeout=()=>fail('L’envoi de la photo a pris trop de temps.');xhr.onabort=()=>fail('Envoi interrompu avant la publication.');
      xhr.onload=()=>{state.xhr=null;let result;try{result=JSON.parse(xhr.responseText)}catch{fail('Réponse photo invalide.');return}if(xhr.status<200||xhr.status>=300||!result.secure_url||!result.public_id){fail(result.error?.message||'La photo a été refusée.');return}resolve({image_url:result.secure_url,cloudinary_public_id:result.public_id})};
      xhr.send(body);
    });
  }
  async function save(){
    if(state.busy||state.done)return;refresh();if(node('bulkSave').disabled)return;
    if(state.organization!==org){message('Le compte actif a changé. Recommencez la préparation.');return}
    const photos=state.rows.filter(row=>row.file||row.image_url).length;
    if(!await confirmAction('Enregistrer '+state.rows.length+' produits ?',photos+' produit(s) avec image, '+(state.rows.length-photos)+' sans image. Les produits seront ajoutés à la Boutique sans remplacer les produits existants.'))return;
    if(state.organization!==org)return;
    state.cancel=false;lock(true);message('');
    try{
      progress(3,'Vérification finale','Contrôle des noms et catégories, sans création de produit.');
      const checked=await api('/api/v1/shop/admin/products/bulk/validate?organization_id='+encodeURIComponent(state.organization),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload()),silentOperation:true});
      if(checked.already_saved){complete({created:checked.products.length,already_saved:true});return}
      if(checked.errors.length){checked.errors.forEach(error=>{const row=state.rows.find(item=>item.client_key===error.client_key);if(row)row.serverErrors.push(error.message)});throw Error('Corrigez les lignes signalées avant de recommencer.')}
      const images=state.rows.filter(row=>row.file);
      for(let index=0;index<images.length;index++){
        if(state.cancel)throw Error('Envoi interrompu avant la publication.');
        const row=images[index];progress(10+75*index/Math.max(images.length,1),'Préparation de la photo '+(index+1)+' / '+images.length,row.name);
        if(!row.uploaded)row.uploaded=await uploadImage(row,index,images.length);
      }
      if(state.cancel)throw Error('Envoi interrompu avant la publication.');
      if(state.organization!==org)throw Error('Le compte actif a changé. Reconnectez-vous avant de publier.');
      node('bulkStop').hidden=true;progress(90,'Enregistrement du lot','Publication des produits en une seule opération.');
      const result=await api('/api/v1/shop/admin/products/bulk?organization_id='+encodeURIComponent(state.organization),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload()),silentOperation:true});
      complete(result);
    }catch(error){
      progress(node('bulkProgressBar').value,'Enregistrement non confirmé',error.message);message(error.message+' Vous pouvez corriger ou réessayer : les photos déjà envoyées seront réutilisées, et le même lot ne sera pas créé deux fois.');
    }finally{state.xhr=null;lock(false)}
  }
  window.openShopBulkImport=open;
  mount();
})();
