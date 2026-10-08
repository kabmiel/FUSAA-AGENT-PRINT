"""Bulk shop imports: one validation pass, atomic publication, safe retries."""
import math
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from .models import ShopCategory, ShopProduct


def bulk_product_ids(organization_id, data):
    return [str(uuid5(NAMESPACE_URL, f"fusaa-shop-bulk:{organization_id}:{data.request_id}:{item.client_key}"))
            for item in data.items]


def bulk_products_out(products, data):
    return [{"client_key":item.client_key, "id":product.id, "name":product.name, "image_url":product.image_url}
            for item, product in zip(data.items, products)]


def validate_shop_bulk(db, organization_id, data, slugger, cloud_name=""):
    ids = bulk_product_ids(organization_id, data)
    existing = {p.id:p for p in db.query(ShopProduct).filter(ShopProduct.id.in_(ids)).all()}
    errors = []
    keys, slugs = set(), []
    for index, item in enumerate(data.items, 1):
        slug = slugger(item.slug or item.name, "article")
        slugs.append(slug)
        if item.client_key in keys:
            errors.append({"line":index, "client_key":item.client_key, "message":"Cette ligne est présente deux fois dans le lot."})
        keys.add(item.client_key)
    if errors:
        return {"errors":errors, "already_saved":False, "products":[], "ids":ids, "slugs":slugs}
    if len(existing) == len(ids):
        return {"errors":[], "already_saved":True, "products":bulk_products_out([existing[i] for i in ids], data), "ids":ids, "slugs":slugs}
    if existing:
        errors.append({"line":0, "client_key":"", "message":"Ce lot a déjà été modifié. Rechargez le catalogue avant de recommencer."})
    category_ids = {item.category_id for item in data.items if item.category_id}
    allowed_categories = {c.id for c in db.query(ShopCategory).filter(ShopCategory.organization_id == organization_id,
                           ShopCategory.id.in_(category_ids)).all()} if category_ids else set()
    occupied = {p.slug for p in db.query(ShopProduct).filter(ShopProduct.organization_id == organization_id,
                ShopProduct.slug.in_(slugs)).all()}
    seen = set()
    for index, (item, slug) in enumerate(zip(data.items, slugs), 1):
        messages = []
        if not item.name.strip(): messages.append("Le nom du produit est obligatoire.")
        if slug in seen: messages.append("Ce produit apparaît plusieurs fois dans la liste.")
        if slug in occupied: messages.append("Un produit de la Boutique porte déjà ce nom. Aucun remplacement automatique.")
        seen.add(slug)
        if not math.isfinite(item.price_xof) or (item.original_price_xof is not None and
                (not math.isfinite(item.original_price_xof) or item.original_price_xof < item.price_xof)):
            messages.append("Vérifiez le prix de vente et le prix normal.")
        if item.category_id and item.category_id not in allowed_categories:
            messages.append("La catégorie ne fait pas partie de cette Boutique.")
        if item.image_url:
            try:
                image_url = urlsplit(item.image_url)
                valid_image_url = image_url.scheme in {"http", "https"} and bool(image_url.hostname)
            except ValueError:
                valid_image_url = False
            if not valid_image_url:
                messages.append("L’image doit utiliser une URL HTTP ou HTTPS valide.")
        if item.cloudinary_public_id and (not cloud_name or not item.image_url or
                not item.image_url.startswith(f"https://res.cloudinary.com/{cloud_name}/")):
            messages.append("L’image ne provient pas du compte Cloudinary configuré.")
        for message in messages:
            errors.append({"line":index, "client_key":item.client_key, "message":message})
    return {"errors":errors, "already_saved":False, "products":[], "ids":ids, "slugs":slugs}
