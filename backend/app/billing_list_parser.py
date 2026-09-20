"""Conservative, ordered product-list detection for billing chat."""
import re
import unicodedata


def normalize(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", value.lower()) if not unicodedata.combining(c)).split())


def parse_product_list(message, catalog):
    """Keep unknown names for explicit price confirmation, never create here.

    Newlines, semicolons, bullets and non-decimal commas delimit products.
    An undelimited unknown phrase remains one editable name, not guessed words.
    """
    text = message.strip()
    text = re.sub(r"^(?:bonjour|bonsoir|salut|hello|coucou)[!,.\s]*", "", text, flags=re.I)
    text = re.sub(r"^(?:(?:fais|faire|crée|créer|cree|creer|prépare|préparer|prepare|preparer|ajoute|ajouter)\s+)?(?:moi\s+)?(?:une?\s+)?(?:facture(?:\s+proforma)?|devis|proforma|reçu|recu|bon de livraison)\s*(?::|avec|pour les produits|pour|de)?\s*", "", text, flags=re.I)
    text = re.sub(r"^(?:liste (?:de |des )?produits|produits|articles)\s*:\s*", "", text, flags=re.I)
    entries = []
    for part in re.split(r"[\r\n;•]+|,(?!\d)", text):
        part = re.sub(r"^\s*(?:[-*•]\s*|\d+[.)]\s+)", "", part).strip()
        if not part or normalize(part).strip("!?. ") in {"bonjour", "bonsoir", "salut", "merci", "comment ca va", "ca va"}:
            continue
        quantity = 1.0
        # Never mistake model numbers (A4, P3, 106A) for a quantity or price.
        match = re.match(r"^(\d+(?:[.,]\d+)?)\s*(?:[x×*]\s*|(?:pièces?|pieces?|unités?|unites?|pcs?)\s+(?:de\s+)?|\s+)(.+)$", part, re.I)
        if match:
            quantity = float(match[1].replace(",", ".")); part = match[2].strip()
        else:
            match = re.search(r"\s+[x×*]\s*(\d+(?:[.,]\d+)?)\s*$", part, re.I)
            if match:
                quantity = float(match[1].replace(",", ".")); part = part[:match.start()].strip()
        price = None
        match = re.search(r"\s+(?:à|a|@|prix\s*[:=]?)\s*(\d[\d\s\u00a0]*(?:[.,]\d{1,2})?)\s*(?:FCFA|F\s*CFA|XOF)?\s*$", part, re.I)
        if match:
            price = float(re.sub(r"\s", "", match[1]).replace(",", ".")); part = part[:match.start()].strip()
        if not part: continue
        # A lot of copied lists arrive as one line: "Piment vert Pastèque
        # Arrosoir". Extract full catalogue names in the displayed order. Any
        # remaining fragment becomes one explicit product-to-price row.
        normalized_part = normalize(part)
        available = sorted(
            [(normalize(product["name"]), product) for product in catalog if normalize(product["name"])],
            key=lambda item: len(item[0]), reverse=True,
        )
        spans = []
        reserved = []
        for product_name, product in available:
            start = normalized_part.find(product_name)
            while start >= 0:
                end = start + len(product_name)
                if not any(start < other_end and end > other_start for other_start, other_end in reserved):
                    reserved.append((start, end)); spans.append((start, end, product))
                start = normalized_part.find(product_name, start + 1)
        if len(spans) >= 2:
            spans.sort(key=lambda item: item[0])
            cursor = 0
            for start, end, product in spans:
                fragment = part[cursor:start].strip(" -,:/")
                if fragment:
                    entries.append({"product_id": None, "description": fragment, "quantity": quantity,
                                    "unit_amount": price, "unit": "piece", "source": "FACTURATION", "candidates": []})
                entries.append({"product_id": product["id"], "description": product["name"], "quantity": quantity,
                                "unit_amount": price if price is not None else product["price_xof"], "unit": product["unit"],
                                "source": product["source"], "candidates": []})
                cursor = end
            fragment = part[cursor:].strip(" -,:/")
            if fragment:
                entries.append({"product_id": None, "description": fragment, "quantity": quantity,
                                "unit_amount": price, "unit": "piece", "source": "FACTURATION", "candidates": []})
            continue
        if len(part) > 160 or not 0 < quantity <= 9999:
            raise ValueError("Vérifiez les désignations (160 caractères maximum) et les quantités (1 à 9 999). Séparez les produits par un retour à la ligne.")
        key = normalize(part)
        candidates = [p for p in catalog if normalize(p["name"]) == key]
        # Only resolve unambiguous full names. Similar models must not be mixed.
        product = candidates[0] if len(candidates) == 1 else None
        entries.append({"product_id": product["id"] if product else None,
                        "description": product["name"] if product else part,
                        "quantity": quantity,
                        "unit_amount": price if price is not None else (product["price_xof"] if product else None),
                        "unit": product["unit"] if product else "piece",
                        "source": product["source"] if product else "FACTURATION",
                        "candidates": candidates})
    if len(entries) > 100:
        raise ValueError("Une facture accepte au maximum 100 lignes. Répartissez cette liste en plusieurs factures.")
    return entries
