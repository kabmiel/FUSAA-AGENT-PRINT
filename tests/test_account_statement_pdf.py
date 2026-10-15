"""Account statement presentation only: synthetic data, no DB/network/AI."""
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace as Record

import fitz
import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app import billing_pdf as pdfmod


def sample(count=1, paid=Decimal("3500.25"), name="Amina Test", style="standard", long=False):
    company=Record(company_name="ATELIER & PARTENAIRES",address="Maradi - Niger",phone="90001122",
                   email="contact@example.test",nif="TEST-123",rccm="TEST-456",logo_url="test-logo",
                   document_style=style,table_font_family=None,table_font_size=None)
    customer=Record(name=name,address="Adresse privée à ne pas imprimer")
    doc=Record(number="SIT-TEST-021",issued_on=datetime(2026,10,15),document_type="CREDIT_STATEMENT")
    operations=[]
    for i in range(count):
        label=("Désignation très longue & détaillée <vérifiée> " * 350) if long and i==0 else f"Article de contrôle {i:03d}"
        operations.append({"kind":"PURCHASE","date":datetime(2026,10,1),"amount":Decimal("23500.75"),
            "number":f"INV-TEST-{i:03d}","lines":[{"description":label,"quantity":1,"total_amount":Decimal("23500.75")} ]})
    if paid:
        operations.append({"kind":"REPAYMENT","date":datetime(2026,10,12),"amount":paid,"method":"VIREMENT",
                           "note":"Référence banque ABC-009", "allocations":[{"number":"INV-TEST-000"}]})
    return doc,company,customer,operations,Decimal("23500.75")*count-paid


@pytest.fixture
def logo_and_qr(monkeypatch):
    image=BytesIO();Image.new("RGB",(120,70),(14,118,110)).save(image,format="PNG")
    monkeypatch.setattr(pdfmod,"_logo_reader",lambda _:ImageReader(BytesIO(image.getvalue())))
    original=pdfmod._draw_qr;values=[]
    def capture(pdf,value,*args):
        values.append(value);return original(pdf,value,*args)
    monkeypatch.setattr(pdfmod,"_draw_qr",capture)
    return values


@pytest.mark.parametrize("style,name,paid",[
    ("standard","Amina Test",Decimal("3500.25")),
    ("scan_compact","Madame Safia Exemple",Decimal("23500.75")),
    ("moderne_clair","ASSOCIATION TEST & SOLIDARITÉ",Decimal("0")),
])
def test_statement_dynamic_courteous_totals_logo_qr_and_settled_account(style,name,paid,logo_and_qr,tmp_path):
    args=sample(paid=paid,name=name,style=style)
    content=pdfmod.render_credit_statement_pdf(*args)
    path=tmp_path/f"situation-{style}.pdf";path.write_bytes(content)
    with fitz.open(stream=content,filetype="pdf") as pdf:
        assert len(pdf)==1
        page=pdf[0];text=page.get_text();flat=" ".join(text.split())
        assert pdf.metadata["title"]=="SITUATION DE COMPTE CLIENT - "+name
        assert "SITUATION DE COMPTE CLIENT" in text and "Client : "+name in flat
        assert "Bonjour "+name+"," in flat and "15/10/2026" in text
        assert "ATELIER & PARTENAIRES" in text and "Maradi - Niger" in text
        assert "contact@example.test" in text and "TEST-123" in text and "TEST-456" in text
        assert "Total des règlements" in text and "23 500,75 FCFA" in flat
        assert "Solde : 0 FCFA" in flat if paid==Decimal("23500.75") else "Solde restant" in flat
        if paid==Decimal("23500.75"):
            assert "entièrement réglé" in flat and "Aucun règlement complémentaire" in flat
        elif paid:
            assert "20 000,50 FCFA" in flat and "3 500,25 FCFA" in flat
        for unwanted in ("ÉTAT DE CRÉDIT", "Doit :", "Total remboursé", "Solde à payer", "Roufai", "24 050", "98 800", "74 750", "Adresse privée"):
            assert unwanted not in text
        spans=[s for b in page.get_text("dict")["blocks"] if "lines" in b for line in b["lines"] for s in line["spans"]]
        title=next(s for s in spans if s["text"]=="SITUATION DE COMPTE CLIENT")
        assert (title["bbox"][0]+title["bbox"][2])/2==pytest.approx(page.rect.width/2,abs=1)
        assert "Bold" in title["font"] and title["size"]>=16
        assert page.get_images() and page.get_drawings() and "1/1" in text
        page.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(str(tmp_path/f"situation-{style}.png"))
    assert len(logo_and_qr)==1
    qr=logo_and_qr[0]
    assert "SIT-TEST-021" in qr and "15/10/2026" in qr
    assert f"Solde: {args[-1]} XOF" in qr
    assert f"Reglements: {paid}" in qr


def test_statement_splits_very_long_operations_and_long_client_names(logo_and_qr,tmp_path):
    name="Organisation de démonstration "*5
    args=sample(count=45,name=name,long=True)
    content=pdfmod.render_credit_statement_pdf(*args)
    (tmp_path/"situation-longue.pdf").write_bytes(content)
    with fitz.open(stream=content,filetype="pdf") as pdf:
        assert len(pdf)>2
        assert "Désignation très longue" in pdf[0].get_text()
        text="\n".join(page.get_text() for page in pdf)
        assert text.count("SITUATION DE COMPTE CLIENT")==1
        assert "INV-TEST-000" in text and "INV-TEST-044" in text and "ABC-009" in text
        assert text.index("INV-TEST-001")<text.index("INV-TEST-044")
        assert "01/10/2026" in text and "12/10/2026" in text
        for number,page in enumerate(pdf,1):
            assert f"{number}/{len(pdf)}" in page.get_text()
            assert page.get_text().count("Désignation / référence")<=1
            for block in page.get_text("dict")["blocks"]:
                if "lines" not in block:continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        x0,y0,x1,y1=span["bbox"]
                        assert 20<=x0<x1<=page.rect.width-20
                        assert 20<=y0<y1<=page.rect.height-8
        for number in (0,len(pdf)-1):
            pdf[number].get_pixmap(matrix=fitz.Matrix(1.15,1.15)).save(str(tmp_path/f"situation-longue-{number+1}.png"))
    assert len(logo_and_qr)==1


def test_empty_account_and_explicit_civility(logo_and_qr):
    args=list(sample(count=0,paid=Decimal("0"),name="Test Client"))
    args[2].civilite="Monsieur"
    with fitz.open(stream=pdfmod.render_credit_statement_pdf(*args),filetype="pdf") as pdf:
        text=" ".join(pdf[0].get_text().split())
        assert "Bonjour Monsieur Test Client," in text
        assert "Aucune opération enregistrée" in text and "Solde : 0 FCFA" in text
    with pytest.raises(ValueError,match="solde"):
        pdfmod.render_credit_statement_pdf(*args[:-1],Decimal("100"))
