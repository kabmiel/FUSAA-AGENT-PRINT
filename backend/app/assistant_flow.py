"""Ground operational responses in real workflow state, not model speculation."""
import re
import unicodedata
from .assistant_schemas import AssistantResponse,ToolCall
from .ai import SafetyLevel,TOOL_SAFETY,resolve_job
from .models import Document,Printer,JobStatus,PriceRule,Workshop
from .access import accessible_workshop_ids

def safe_result_response(calls:list[ToolCall]):
    """Present read-only tool output deterministically instead of raw JSON."""
    if not calls:
        return AssistantResponse(
            title="Assistant FUSAA",
            answer="Je peux vous aider à retrouver un document, un travail ou une imprimante.",
            steps=["Essayez : « Quels travaux sont en attente ? » ou « Quelles imprimantes sont disponibles ? »"],
            tool_calls=[],
            requires_confirmation=False,
        )
    call=calls[0]
    result=call.result or {}
    if call.name=="list_print_jobs":
        jobs=result.get("jobs",[])
        return AssistantResponse(title="Travaux d’impression",answer="Voici les travaux accessibles." if jobs else "Aucun travail ne correspond à cette recherche.",steps=[f"{item.get('id','')[:8]} · {item.get('status','Statut inconnu')} · {item.get('copies',1)} exemplaire(s)" for item in jobs[:12]],next_view="print" if jobs else "upload",next_label="Ouvrir les impressions" if jobs else "Ajouter un document",tool_calls=calls,requires_confirmation=False)
    if call.name in {"list_printers","get_printer","get_printer_status"}:
        printers=result.get("printers",[])
        return AssistantResponse(title="Imprimantes",answer="Voici les imprimantes accessibles." if printers else "Aucune imprimante disponible n’a été trouvée.",steps=[f"{item.get('name','Imprimante')} · {item.get('status','Statut inconnu')}" for item in printers[:12]],next_view="print",next_label="Ouvrir les impressions",tool_calls=calls,requires_confirmation=False)
    if call.name in {"search_documents","get_document","preview_document"}:
        documents=result.get("documents",[])
        return AssistantResponse(title="Documents",answer="Voici les documents trouvés." if documents else "Aucun document ne correspond à cette recherche.",steps=[f"{item.get('name','Document')} · {item.get('mime_type','format inconnu')}" for item in documents[:12]],next_view="print" if documents else "upload",next_label="Choisir un travail" if documents else "Ajouter un document",tool_calls=calls,requires_confirmation=False)
    if call.name=="recommend_printer":
        items=result.get("recommendations",[])
        return AssistantResponse(title="Imprimante recommandée",answer="Voici les imprimantes compatibles d’après les profils synchronisés." if items else "Aucune imprimante compatible n’est actuellement disponible.",steps=[f"{item.get('printer','Imprimante')} · {', '.join(item.get('reasons',[])) or 'profil disponible'}" for item in items[:12]],next_view="print",next_label="Voir les paramètres",tool_calls=calls,requires_confirmation=False)
    if call.name in {"get_print_job","inspect_document"}:
        job=result.get("job")
        return AssistantResponse(title="Travail d’impression",answer="Voici l’état du travail sélectionné." if job else "Le travail demandé est introuvable ou inaccessible.",steps=[] if not job else [f"Statut : {job.get('status','inconnu')}",f"Document : {job.get('document_id','inconnu')[:8]}"],next_view="print",next_label="Ouvrir les impressions",tool_calls=calls,requires_confirmation=False)
    return AssistantResponse(title="Résultat FUSAA",answer="La recherche a été effectuée.",steps=["Aucune action n’a été lancée."],tool_calls=calls,requires_confirmation=False)

def workflow_response(data,db,user):
    text="".join(c for c in unicodedata.normalize("NFD",data.message.lower()) if not unicodedata.combining(c))
    if re.search(r"\b(prix|tarifs?|cout|devis|combien)\b",text):
        ids=accessible_workshop_ids(db,user,write=True)
        if not ids:
            return AssistantResponse(title="Tarifs FUSAA",answer="Votre rÃ´le permet de consulter les travaux, mais pas les tarifs de l'atelier.",tool_calls=[],requires_confirmation=False)
        org_ids=[item.organization_id for item in db.query(Workshop).filter(Workshop.id.in_(ids)).all()]
        rule=db.query(PriceRule).filter(PriceRule.organization_id.in_(org_ids),PriceRule.name=="Tarif public par dÃ©faut").order_by(PriceRule.priority).first()
        pricing=(rule.pricing if rule else {}) or {}
        def rate(prefix):
            standard=float(pricing.get(f"{prefix}_page") or pricing.get("per_page",0) or 0);threshold=int(pricing.get(f"{prefix}_discount_from",0) or 0);reduced=float(pricing.get(f"{prefix}_discount_page",standard) or standard)
            return standard,threshold,reduced
        mono=rate("monochrome");color=rate("color")
        def line(label,values):
            standard,threshold,reduced=values
            return f"{label} : {standard:,.0f} FCFA/page"+(f" ; {reduced:,.0f} FCFA/page Ã  partir de {threshold} pages" if threshold else "")
        amount_match=re.search(r"\b(\d+)\s*(?:page|pages|feuille|feuilles|copie|copies|impression|impressions)\b",text)
        wants_color="couleur" in text or "color" in text;wants_mono=any(word in text for word in ("noir","blanc","mono"))
        steps=[line("Noir et blanc",mono),line("Couleur",color)]
        if amount_match and (wants_color or wants_mono):
            sheets=int(amount_match.group(1));chosen=color if wants_color else mono;unit=chosen[2] if chosen[1] and sheets>=chosen[1] else chosen[0];mode="couleur" if wants_color else "noir et blanc"
            return AssistantResponse(title="Estimation FUSAA",answer=f"Pour {sheets} pages en {mode} : {unit*sheets:,.0f} FCFA.",steps=[f"Tarif appliquÃ© : {unit:,.0f} FCFA par page",f"QuantitÃ© : {sheets} pages",*steps],next_view="publicOrders",next_label="Configurer les tarifs",tool_calls=[],requires_confirmation=False)
        return AssistantResponse(title="Tarifs FUSAA",answer="Voici la grille de prix actuellement configurÃ©e.",steps=steps+["Dites par exemple : Â« combien pour 20 pages noir et blanc ? Â»"],next_view="publicOrders",next_label="Configurer les tarifs",tool_calls=[],requires_confirmation=False)
    if any(word in text for word in ("whatsapp","bureau","surveill","nouveau message","nouveau fichier")):
        return AssistantResponse(title="Vos nouvelles arrivées",answer="FUSAA peut vous avertir des nouveaux fichiers du Bureau et des arrivées détectées dans WhatsApp Web.",steps=["Bureau : les fichiers nouveaux sont signalés après la fin de leur copie.","WhatsApp : chargez et associez l’extension locale dans Brave, puis gardez WhatsApp Web ouvert.","Retrouvez les alertes dans Arrivées. Vous choisissez ensuite le document à importer."],next_view="settings",next_label="Configurer les alertes",tool_calls=[],requires_confirmation=False)
    if not re.search(r"imprim|prepar|annul|ignorer",text):return None
    # Queries about printers are read-only and belong to the normal tool layer.
    if re.search(r"imprimante",text) and not re.search(r"imprimer|imprime\b|prepar|annul",text):return None
    reference=re.search(r"\b[0-9a-f]{8}(?:-[0-9a-f-]{27})?\b",text)
    job=resolve_job(db,user,reference.group(0) if reference else data.selected_job_id)
    if not job:
        return AssistantResponse(title="Préparons votre impression",answer="Oui, je peux vous guider. Il faut d’abord choisir le document à imprimer.",steps=["Importez un PDF, une image JPG ou PNG, ou sélectionnez un travail existant.","Choisissez l’imprimante, les exemplaires et les pages.","Vérifiez l’aperçu ; l’impression démarre uniquement après votre confirmation."],next_view="upload",next_label="Choisir mon document",tool_calls=[],requires_confirmation=False)
    if job.workshop_id not in accessible_workshop_ids(db,user,write=True):
        return AssistantResponse(title="Accès en lecture seule",answer="Votre rôle permet de consulter ce travail. Un opérateur de cet atelier doit effectuer l’action.",tool_calls=[],requires_confirmation=False)
    doc=db.get(Document,job.document_id)
    name=doc.original_name if doc else "Document"
    action="cancel_print_job" if "annul" in text else "ignore_print_job" if "ignorer" in text else "request_print"
    allowed=(job.status==JobStatus.READY if action=="request_print" else job.status==JobStatus.WAITING_APPROVAL if action=="ignore_print_job" else job.status not in {JobStatus.CANCELLED,JobStatus.COMPLETED,JobStatus.FAILED,JobStatus.IGNORED})
    if not allowed or "prepar" in text:
        return AssistantResponse(title="Document sélectionné",answer=name,steps=["Ouvrez les paramètres d’impression pour vérifier l’aperçu et l’imprimante.", "Préparez le travail avant de confirmer son impression."],next_view="print",next_label="Vérifier les paramètres",tool_calls=[],requires_confirmation=False)
    printer=db.get(Printer,job.printer_id) if job.printer_id else None
    if action=="request_print" and not printer:
        return AssistantResponse(title="Imprimante à sélectionner",answer=name,steps=["Choisissez une imprimante dans les paramètres du travail."],next_view="print",next_label="Choisir l’imprimante",tool_calls=[],requires_confirmation=False)
    details=[f"Document : {name}",f"Exemplaires : {job.copies}"]
    if printer:details.append(f"Imprimante : {printer.name}")
    details.extend([f"Pages : {job.pages or 'toutes'}",f"Recto-verso : {'oui' if job.duplex else 'non'}"])
    label={"request_print":"Confirmer cette impression","cancel_print_job":"Confirmer l’annulation","ignore_print_job":"Ignorer ce travail"}[action]
    return AssistantResponse(title=label,answer="Vérifiez les informations ci-dessous avant de confirmer.",steps=details,tool_calls=[ToolCall(name=action,arguments={"job_reference":job.id},safety=TOOL_SAFETY[action])],requires_confirmation=True)
