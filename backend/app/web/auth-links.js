"use strict";
(async function(){
  const get=id=>document.getElementById(id),form=get("authLinkForm"),button=get("authSubmit"),status=get("authStatus");
  try{document.documentElement.dataset.theme=localStorage.getItem("fusaa-theme")||"dark"}catch{}
  const purpose=document.body.dataset.authPurpose,query=new URLSearchParams(location.search),fragment=new URLSearchParams(location.hash.slice(1));
  const actionToken=fragment.get("token")||query.get("token")||"";
  if(actionToken){query.delete("token");history.replaceState(null,"",location.pathname+(query.toString()?"?"+query.toString():""))}
  let pending=false,ready=!actionToken;
  function message(text,error=false){status.textContent=text;status.classList.toggle("error",error)}
  function busy(value){button.disabled=value;button.setAttribute("aria-busy",String(value));form.setAttribute("aria-busy",String(value))}
  function apiError(detail){return Array.isArray(detail)?detail.map(e=>e.msg||"Donnée invalide").join(" · "):typeof detail==="string"?detail:"La demande a échoué."}
  async function post(path,data){const response=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(apiError(result.detail));return result}
  if(actionToken){
    busy(true);message("Vérification du lien…");
    try{const info=await post("/api/v1/auth/action/inspect",{token:actionToken,purpose});get("authEmail").value=info.email;get("authEmail").readOnly=true;if(get("authName")&&info.display_name!=="Invitation FUSAA en attente")get("authName").value=info.display_name;form.hidden=false;ready=true;message("");busy(false)}
    catch(error){message(error.message,true);form.hidden=true;ready=false}
  }else if(purpose==="RESET"){
    get("recoveryHelp").hidden=false;form.hidden=true;ready=false;
  }else if(query.get("email")){
    message("Ce lien d’activation est ancien ou incomplet. Demandez à l’administrateur de renvoyer un lien depuis Équipe.",true);form.hidden=true;ready=false;
  }else{
    document.querySelector("h1").textContent="Créer votre accès";get("authDescription").textContent="Choisissez un mot de passe simple et personnel. Un minimum de 4 caractères suffit.";button.textContent="Créer mon compte";
  }
  form.onsubmit=async event=>{
    event.preventDefault();if(pending||!ready||!form.reportValidity())return;
    const password=get("authPassword").value;
    if(!password.trim()){message("Choisissez un mot de passe qui ne contient pas seulement des espaces.",true);return}
    if(password!==get("authConfirm").value){message("Les deux mots de passe doivent être identiques.",true);get("authConfirm").focus();return}
    pending=true;busy(true);message(purpose==="RESET"?"Enregistrement du nouveau mot de passe…":"Activation du compte…");
    try{
      const body=purpose==="RESET"?{token:actionToken,password}:{email:get("authEmail").value.trim(),password,display_name:get("authName").value.trim(),invitation_token:actionToken||null};
      const result=await post(purpose==="RESET"?"/api/v1/auth/password/reset":"/api/v1/auth/register",body);
      // Never inherit the inviter's workspace selection when changing identity.
      ["org","workshop"].forEach(key=>localStorage.removeItem(key));localStorage.setItem("token",result.access_token);
      message("Compte prêt. Ouverture de votre espace…");location.assign("/admin");
    }catch(error){message(error.message,true);pending=false;busy(false)}
  };
})();
