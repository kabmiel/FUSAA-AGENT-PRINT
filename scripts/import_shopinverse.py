"""One-time import of the Shopinverse Django catalogue into Boutique FUSAA.

Usage (from the FUSAA project root):
  py -3.11 scripts/import_shopinverse.py --source "C:\\...\\shopinverse_django\\db.sqlite3" --organization-id YOUR_ORG_ID

It deliberately imports catalogue data only. Historical Django accounts/orders
are not copied because their passwords and customer-consent model are different.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from app.database import SessionLocal
from app.models import Organization, ShopCategory, ShopProduct

def unique_slug(db,model,organization_id,slug):
    base=slug or "article";candidate=base;index=2
    while db.query(model).filter_by(organization_id=organization_id,slug=candidate).first():
        candidate=f"{base}-{index}";index+=1
    return candidate

def main():
    parser=argparse.ArgumentParser(description="Import Shopinverse products into Boutique FUSAA")
    parser.add_argument("--source",required=True,type=Path,help="Path to the Django db.sqlite3")
    parser.add_argument("--organization-id",required=True,help="FUSAA organization UUID")
    args=parser.parse_args()
    if not args.source.is_file():raise SystemExit(f"Database not found: {args.source}")
    source=sqlite3.connect(args.source);source.row_factory=sqlite3.Row
    db=SessionLocal()
    try:
        if not db.get(Organization,args.organization_id):raise SystemExit("Unknown FUSAA organization id")
        category_map={}
        for row in source.execute("SELECT id,name,slug,description,icon FROM products_category ORDER BY id"):
            existing=db.query(ShopCategory).filter_by(organization_id=args.organization_id,slug=row["slug"]).one_or_none()
            category=existing or ShopCategory(organization_id=args.organization_id,name=row["name"],slug=unique_slug(db,ShopCategory,args.organization_id,row["slug"]),description=row["description"] or None,icon=row["icon"] or None)
            if not existing:db.add(category);db.flush()
            category_map[row["id"]]=category.id
        imported=0;skipped=0
        rows=source.execute("SELECT id,category_id,name,slug,description,brand,price,original_price,status,stock,specifications FROM products_product ORDER BY id")
        for row in rows:
            if db.query(ShopProduct).filter_by(organization_id=args.organization_id,slug=row["slug"]).first():skipped+=1;continue
            condition="USED" if row["status"]=="used" else "NEW"
            product=ShopProduct(organization_id=args.organization_id,category_id=category_map.get(row["category_id"]),name=row["name"],slug=unique_slug(db,ShopProduct,args.organization_id,row["slug"]),description=row["description"] or "",brand=row["brand"] or None,price_xof=float(row["price"] or 0),original_price_xof=float(row["original_price"]) if row["original_price"] is not None else None,condition=condition,stock_quantity=max(0,int(row["stock"] or 0)),specifications={})
            db.add(product);imported+=1
        db.commit();print(f"Import complete: {imported} product(s) added, {skipped} already present.")
    finally:
        source.close();db.close()

if __name__=="__main__":main()
