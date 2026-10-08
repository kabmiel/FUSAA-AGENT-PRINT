"""Only local in-memory checks; no Cloudinary, database server or AI calls."""
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.database import Base
from app.models import Organization,OrganizationMember,User,ShopCategory,ShopProduct
from app.main import create_shop_product_bulk,validate_shop_product_bulk
from app.shop_schemas import ShopProductBulkIn
from app.config import settings


@pytest.fixture
def bulk_db():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner=User(id='owner',email='owner@example.test',display_name='Owner',password_hash='unused')
        viewer=User(id='viewer',email='viewer@example.test',display_name='Viewer',password_hash='unused')
        db.add_all([Organization(id='o',name='Boutique'),Organization(id='other',name='Other'),owner,viewer]);db.flush()
        db.add_all([OrganizationMember(organization_id='o',user_id='owner',role='OWNER'),OrganizationMember(organization_id='o',user_id='viewer',role='OPERATOR'),ShopCategory(id='cat',organization_id='o',name='Papier',slug='papier'),ShopCategory(id='foreign',organization_id='other',name='Other',slug='other')]);db.commit()
        yield db,owner,viewer


def batch(items,request_id=None):
    return ShopProductBulkIn(request_id=request_id or uuid4(),items=items)


def test_bulk_is_atomic_scope_checked_and_does_not_overwrite_existing_products(bulk_db):
    db,owner,viewer=bulk_db
    invalid=batch([{'client_key':'a','name':'Ramette','price_xof':3500,'category_id':'cat'},
                   {'client_key':'b','name':'Cahier','price_xof':250,'category_id':'foreign'}])
    with pytest.raises(HTTPException) as error:create_shop_product_bulk('o',invalid,owner,db)
    assert error.value.status_code==422 and db.query(ShopProduct).count()==0
    with pytest.raises(HTTPException) as error:validate_shop_product_bulk('o',invalid,viewer,db)
    assert error.value.status_code==403
    duplicate=batch([{'client_key':'a','name':'Ramette','price_xof':1}, {'client_key':'b','name':'Ramette','price_xof':2}])
    assert validate_shop_product_bulk('o',duplicate,owner,db)['errors']
    valid=batch([{'client_key':'a','name':'Ramette','price_xof':3500,'category_id':'cat'}])
    create_shop_product_bulk('o',valid,owner,db)
    with pytest.raises(HTTPException):create_shop_product_bulk('o',batch([{'client_key':'c','name':'Ramette','price_xof':1}]),owner,db)
    assert db.query(ShopProduct).one().price_xof==3500


def test_bulk_retry_returns_same_products_with_images_and_no_duplicate(bulk_db,monkeypatch):
    db,owner,_=bulk_db
    monkeypatch.setattr(settings,'cloudinary_cloud_name','test-cloud')
    data=batch([{'client_key':'first','name':'Produit photo','price_xof':500,'stock_quantity':3,
                 'image_url':'https://res.cloudinary.com/test-cloud/image/upload/photo.webp','cloudinary_public_id':'products/photo'},
                {'client_key':'second','name':'Second produit','price_xof':100,'description':'Deuxième ligne'}])
    assert validate_shop_product_bulk('o',data,owner,db)['errors']==[]
    result=create_shop_product_bulk('o',data,owner,db)
    retry=create_shop_product_bulk('o',data,owner,db)
    assert result['products']==retry['products'] and retry['already_saved'] is True
    assert validate_shop_product_bulk('o',data,owner,db)['already_saved'] is True
    assert db.query(ShopProduct).count()==2
    photo=db.query(ShopProduct).filter_by(name='Produit photo').one()
    assert photo.enabled and photo.cloudinary_public_id=='products/photo'
    assert [item['client_key'] for item in result['products']]==['first','second']


def test_bulk_review_local_photo_mobile_and_lost_response_retry(tmp_path):
    from io import BytesIO
    from PIL import Image
    playwright=pytest.importorskip('playwright.sync_api')
    web=ROOT/'backend/app/web'
    html="""<!doctype html><html data-theme="dark"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:#081727;color:#e9f3ff;font:15px Arial}main{padding:12px;max-width:1100px;margin:auto;min-width:0}.view{display:none}.view.active{display:block}.view-head{display:flex;justify-content:space-between}.inline-actions{display:flex;gap:8px}.panel{padding:18px;background:#102033;border:1px solid #345;border-radius:16px;margin-bottom:15px}button{border:0;border-radius:8px;padding:9px 12px;color:#fff;background:#147ddd;cursor:pointer}.secondary{background:#ffffff15}input,select,textarea{font:inherit}h1{font-size:26px}.eyebrow{font-size:11px;color:#5dddd2}
</style><link rel="stylesheet" href="/shop-bulk-import.css"></head><body><main><section id="shopProductsManage" class="view active"><div class="view-head"><h1>Catalogue</h1><div class="inline-actions"></div></div></section></main><script>
let org='o',shopProductPage={categories:[]},idCounter=0;
function newId(){return '00000000-0000-4000-8000-'+String(++idCounter).padStart(12,'0')}
function esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function tell(value){window.notice=value}
function selectView(id){document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id===id))}
window.publishCount=0;window.imageUploads=0;window.signatureCalls=0;window.committed=false;
async function api(path,options={}){
 if(path.includes('/categories?'))return [{id:'cat',name:'Bureautique'}];
 if(path.includes('/bulk/validate'))return {errors:[],already_saved:window.committed,products:window.committed?window.lastBulk.items.map(item=>({client_key:item.client_key,id:item.client_key,name:item.name})):[]};
 if(path.includes('/cloudinary/signature')){window.signatureCalls++;return {cloud_name:'test-cloud',api_key:'test',timestamp:1,signature:'test',folder:'test',public_id:'photo'}};
 if(path.includes('/products/bulk?')){window.lastBulk=JSON.parse(options.body);window.publishCount++;window.committed=true;throw Error('Réponse perdue après publication simulée')};
 throw Error('Appel inattendu : '+path);
}
window.XMLHttpRequest=class{
 constructor(){this.upload={}}
 open(method,url){window.uploadAddress=url}
 send(body){window.imageUploads++;setTimeout(()=>{this.upload.onprogress?.({lengthComputable:true,loaded:1,total:1});this.status=200;this.responseText=JSON.stringify({secure_url:'https://res.cloudinary.com/test-cloud/image/upload/photo.webp',public_id:'photo'});this.onload()},10)}
 abort(){this.onabort?.()}
};
</script><script src="/shop-bulk-import.js"></script></body></html>"""
    with playwright.sync_playwright() as driver:
        try:browser=driver.chromium.launch(headless=True)
        except Exception as error:pytest.skip(f'Chromium indisponible : {error}')
        page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        def serve(route):
            path=route.request.url.split('?',1)[0]
            if path.endswith('/admin'):route.fulfill(content_type='text/html; charset=utf-8',body=html)
            elif path.endswith('.js'):route.fulfill(content_type='application/javascript',body=(web/'shop-bulk-import.js').read_text(encoding='utf-8'))
            elif path.endswith('.css'):route.fulfill(content_type='text/css',body=(web/'shop-bulk-import.css').read_text(encoding='utf-8'))
            else:route.fulfill(status=404)
        page.route('**/*',serve);page.goto('http://bulk-ui.test/admin')
        page.get_by_role('button',name='Importer par lot').click()
        page.wait_for_function("document.getElementById('shopBulkImport').classList.contains('active')")
        csv='Produit;Prix;Stock;Catégorie;Image\n"Ramette; premium";"3 500";10;Bureautique;ramette.png\nCahier;250;5;Bureautique;\nCahier;300;2;Bureautique;\n'
        page.locator('#bulkListFile').set_input_files({'name':'produits.csv','mimeType':'text/csv','buffer':csv.encode()})
        page.locator('.shop-bulk-row').nth(2).wait_for()
        assert page.locator('#bulkSave').is_disabled()
        page.locator('.shop-bulk-row').nth(2).get_by_role('button',name='Retirer ce produit du lot').click()
        photo=BytesIO();Image.new('RGB',(8,8),(20,180,140)).save(photo,format='PNG')
        page.locator('[data-file]').first.set_input_files({'name':'ramette.png','mimeType':'image/png','buffer':photo.getvalue()})
        page.wait_for_function("document.querySelector('.shop-bulk-thumb img')?.src.startsWith('blob:')")
        assert page.locator('[data-field="price_xof"]').first.input_value()=='3500'
        assert page.evaluate('window.publishCount')==0 and page.evaluate('window.imageUploads')==0
        page.locator('.shop-bulk-thumb').first.click()
        assert page.locator('#bulkPhotoDialog').is_visible()
        page.get_by_role('button',name='Fermer l’aperçu').click()
        for width in (1440,390,320):
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('#shopBulkImport').screenshot(path=str(tmp_path/f'bulk-review-{width}.png'))
        page.locator('#bulkSave').click();page.locator('#bulkConfirm [data-confirm]').click()
        page.wait_for_function("document.getElementById('bulkProgressLabel').textContent==='Enregistrement non confirmé'")
        assert page.evaluate('window.publishCount')==1 and page.evaluate('window.imageUploads')==1
        page.locator('#bulkSave').click();page.locator('#bulkConfirm [data-confirm]').click()
        page.locator('#bulkSuccess').wait_for(state='visible')
        assert page.evaluate('window.publishCount')==1 and page.evaluate('window.imageUploads')==1
        assert page.evaluate('window.lastBulk.items.length')==2
        assert page.evaluate('window.lastBulk.items[0].cloudinary_public_id')=='photo'
        assert page.evaluate('window.lastBulk.items[0].name')=='Ramette; premium'
        assert page.locator('#bulkPercent').inner_text()=='100 %'
        assert not errors
        browser.close()
