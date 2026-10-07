"""Local PDF layout checks only: no database, network or AI calls."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as Record

import fitz
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.billing_pdf import MODERN_STYLES, REFERENCE_STYLES, _cell_baseline, _row_layout, render_credit_statement_pdf, render_invoice_pdf

STYLES = ["standard", *REFERENCE_STYLES, *MODERN_STYLES, "ultra_compact"]


def header(style):
    return Record(company_name="ENTREPRISE LAYOUT UNIQUE", address="ZINDER-NIGER", phone="99094000", email=None,
                  nif="130585/P", rccm=None, logo_url=None, document_style=style, table_font_family=None,
                  table_font_size=None, tax_enabled=False, isb_enabled=False, isb_rate=0)


def invoice(lines, kind="INVOICE"):
    total = sum((Decimal(str(line.quantity)) * Decimal(str(line.unit_amount)) for line in lines), Decimal("0"))
    return Record(number="LAYOUT-2026", document_type=kind, document_style=None, issued_on=date(2026, 10, 7),
                  subject="", notes="", subtotal_amount=total, discount_amount=0, tax_amount=0, isb_amount=0, total_amount=total)


def rows(count):
    return [Record(description=f"Article {i:03d} pour installation", quantity=2, unit_amount=1000, total_amount=2000, unit="pièce") for i in range(1, count + 1)]


def assert_pages(pdf, company):
    texts = [page.get_text() for page in pdf]
    assert company in texts[0]
    assert all(company not in text and "Doit :" not in text for text in texts[1:])
    for index, text in enumerate(texts, 1):
        assert f"{index}/{len(texts)}" in text
    return texts


@pytest.mark.parametrize("style", STYLES)
def test_all_templates_have_tight_cells_single_header_and_total_page_count(style, tmp_path):
    company, customer = header(style), Record(name="CLIENT LAYOUT", address="Adresse à ne pas imprimer")
    short = rows(2)
    path = tmp_path / "short.pdf"
    render_invoice_pdf(path, invoice(short), company, customer, short)
    with fitz.open(path) as pdf:
        assert len(pdf) == 1
        text = "\n".join(assert_pages(pdf, company.company_name))
        assert "Adresse à ne pas imprimer" not in text
        assert "Arrêt" in text and "Article 001" in text and "Article 002" in text
        # The amount-in-words paragraph must sit below the final total.
        spans = [span for block in pdf[0].get_text("dict")["blocks"] if "lines" in block for line in block["lines"] for span in line["spans"]]
        sentence = next(span for span in spans if "Arrêt" in span["text"])
        totals = [span for span in spans if span["text"].strip().lower() in {"total", "total ttc"}]
        assert totals and sentence["bbox"][1] > max(span["bbox"][3] for span in totals) + 2
    long = rows(100)
    path = tmp_path / "long.pdf"
    render_invoice_pdf(path, invoice(long), company, customer, long)
    with fitz.open(path) as pdf:
        assert len(pdf) > 1
        text = "\n".join(assert_pages(pdf, company.company_name))
        positions = [text.index(f"Article {i:03d}") for i in range(1, 101)]
        assert positions == sorted(positions)
    operations = [{"kind": "PURCHASE", "date": date(2026, 10, 7), "amount": 1000, "number": f"CR-{i}",
                   "lines": [{"description": f"Produit crédit {i:03d}", "quantity": 1, "total_amount": 1000}]} for i in range(100)]
    with fitz.open(stream=render_credit_statement_pdf(invoice(long, "CREDIT_STATEMENT"), company, customer, operations, 100000), filetype="pdf") as pdf:
        assert len(pdf) > 1
        text = "\n".join(assert_pages(pdf, company.company_name))
        assert "Produit crédit 000" in text and "Produit crédit 099" in text


def test_cell_padding_is_balanced_without_an_empty_line():
    from reportlab.pdfbase import pdfmetrics
    for font in ("Times-Roman", "Helvetica", "Courier"):
        for size in (8, 11.5, 14):
            for count in (1, 2, 4):
                height, leading = _row_layout([""] * count, font, size)
                baseline = _cell_baseline(100, height, count, font, size, leading)
                ascent, descent = pdfmetrics.getAscentDescent(font, size)
                top_gap = 100 - baseline - ascent
                bottom_gap = baseline - (count - 1) * leading + descent - (100 - height)
                assert top_gap == pytest.approx(bottom_gap)
                assert leading == pytest.approx(size * 1.1)


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("kind", ["INVOICE", "DELIVERY_NOTE"])
def test_quantity_contents_are_centered_under_the_column_heading(style, kind, tmp_path):
    lines = [Record(description="Produit centré", quantity=37, unit_amount=1234,
                    total_amount=45658, unit="pièce")]
    path = tmp_path / "quantity.pdf"
    render_invoice_pdf(path, invoice(lines, kind), header(style), Record(name="CLIENT"), lines)
    with fitz.open(path) as pdf:
        spans = [span for block in pdf[0].get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        heading = next(span for span in spans if span["text"].casefold() in {"quantité", "qté"})
        quantity = next(span for span in spans if span["text"] == "37" or span["text"].startswith("37 "))
        center = lambda span: (span["bbox"][0] + span["bbox"][2]) / 2
        assert center(quantity) == pytest.approx(center(heading), abs=.2)


@pytest.mark.parametrize("style", STYLES)
def test_smaller_font_really_fits_more_products(style, tmp_path):
    company, customer, lines = header(style), Record(name="CLIENT"), rows(60)
    counts, pages = [], []
    for size in (8, 14):
        company.table_font_size = size
        path = tmp_path / f"font-{size}.pdf"
        render_invoice_pdf(path, invoice(lines), company, customer, lines)
        with fitz.open(path) as pdf:
            text = pdf[0].get_text()
            counts.append(sum(f"Article {i:03d}" in text for i in range(1, 61)))
            pages.append(len(pdf))
            spans = [span for block in pdf[0].get_text("dict")["blocks"] if "lines" in block for line in block["lines"] for span in line["spans"]]
            assert next(span for span in spans if "Article 001" in span["text"])["size"] == pytest.approx(size)
    assert counts[0] > counts[1]
    assert pages[0] <= pages[1]


def write_visual_samples(folder):
    """Reproduce the supplied invoice without modifying its saved data."""
    source = [
        ("Installation et repli de chantier", 2, 100000), ("Tuyau PVC diamètre 20 de 4 m", 30, 2000),
        ("Raccord union de 26", 4, 2000), ("Coude PVC de 26", 6, 250), ("Vanne PVC 26", 2, 2000),
        ("Té 26", 3, 500), ("Coude 20", 6, 500), ("Robinet de 15 Galva", 10, 4000), ("Té de 15", 5, 300),
        ("Raccord union de 15", 2, 500), ("Vanne d'arrêt de 15", 2, 3000), ("Coude de 15", 6, 300),
        ("Galva de 20", 1, 3100), ("Colle pour PVC", 4, 2200), ("Teplam", 2, 1150),
        ("Tuyau de PPR de 15 de 4 m", 8, 4000), ("Tuyau PVC diamètre 26 de 4 m", 25, 4000),
        ("Main-d'œuvre du plombier", 1, 80000),
        ("Réalisation de la superstructure en béton armé du réservoir en tank avec la main-d'œuvre", 1, 445000),
    ]
    lines = [Record(description=text, quantity=qty, unit_amount=amount, total_amount=qty * amount, unit="pièce") for text, qty, amount in source]
    for style in STYLES:
        company = header(style)
        company.company_name = "ALASSANE ALI MAHAMANE BACHIR"
        company.address = "COMMERCE-GENERAL\nZINDER-NIGER\nCOMPTE N° : 03783824401 CORIS BANQUE"
        document = invoice(lines)
        document.subject = "POUR LE RACCORDEMENT D'EAU DANS LE CSI DE GUIDIGUIR"
        path = folder / f"sample-{style}.pdf"
        render_invoice_pdf(path, document, company, Record(name="GOAL/ZINDER"), lines)
        with fitz.open(path) as pdf:
            for index, page in enumerate(pdf):
                page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25)).save(str(folder / f"sample-{style}-{index + 1}.png"))
            print(style, len(pdf), "pages", document.total_amount)


if __name__ == "__main__":
    write_visual_samples(ROOT / "tmp/pdfs")
