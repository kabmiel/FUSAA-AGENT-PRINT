"""PDF invoices using the Boulangerie document templates.

Each available style has an independent layout.  This replaces the former
"one invoice, different colour" renderer so imported Boulangerie headers keep
their composition: scanned templates have their original table variants and
the modern templates retain their card, QR and totals layouts.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .config import settings


# Values are the Boulangerie source layout values, converted to ReportLab units.
REFERENCE_STYLES = {
    "scan_gauche": dict(font="Times-Roman", margins=(10.5, 10, 9, 10.5), body=14, head=16, align="left", indent=17, date_prefix="", date_top=2, title="FACTURE PRO-FORMA", title_size=20, underline=True, client=15, table=14, table_top=5, table_bg="#d7d7d7", bold=True, widths=(7, 45, 14, 15, 19), unit_label="Prix-\nunitaire", total_label="TOTAL", total_center=True, separator=".", suffix=" F", sentence_align="left", sentence=14, signature="plain", signature_top=14, signature_right=15, proforma_label="facture pro-forma"),
    "scan_alasko": dict(font="Helvetica", margins=(12, 10.5, 9, 10.5), body=13.5, head=18, align="left", indent=16, date_prefix="le ", date_top=18, title="FACTURE PRO FORMA", title_size=20, underline=False, client=13, table=13, table_top=3, table_bg="#d7d7d7", bold=True, widths=(7, 41, 18, 16, 18), unit_label="Prix unitaire", total_label="Total", total_center=False, separator=".", suffix=" F", sentence_align="center", sentence=12.5, signature="italic", signature_top=14, signature_right=12, proforma_label="facture pro forma", client_label="Doit", client_label_underline=False),
    "scan_centre": dict(font="Times-Roman", margins=(13.5, 11.5, 9, 11.5), body=14, head=18, align="center", indent=0, date_prefix="le ", date_top=8, title="FACTURE PRO FORMA", title_size=21, underline=False, client=14, table=14, table_top=10, table_bg=None, bold=False, widths=(7, 40, 18, 15, 20), unit_label="Prix unitaire", total_label="Total", total_center=False, separator="", suffix=" F", sentence_align="center", sentence=14, signature="italic", signature_top=18, signature_right=18, proforma_label="facture pro forma", rule=True),
    "scan_compact": dict(font="Times-Roman", margins=(10, 8.5, 8.5, 8.5), body=11.5, head=12.5, align="left", indent=10, date_prefix="", date_top=0, title="FACTURE PRO-FORMA", title_size=17, underline=True, client=12.5, table=11.5, table_top=3, table_bg="#eeeeee", bold=True, widths=(7, 45, 14, 15, 19), unit_label="Prix-\nunitaire", total_label="TOTAL", total_center=True, separator="", suffix="", sentence_align="left", sentence=11.5, signature="plain", signature_top=14, signature_right=12, proforma_label="facture pro-forma"),
    "scan_facture_simple": dict(font="Helvetica", margins=(16.5, 13.5, 10.5, 13.5), body=12.5, head=12.5, align="left", indent=0, date_prefix="le ", date_top=3, title="FACTURE PROFORMA", title_size=22, underline=True, client=12.5, table=11.5, table_top=6, table_bg="#d8d8d8", bold=True, widths=(7, 31, 11, 13, 18, 20), unit_label="Prix unitaire", total_label="Total", total_center=True, separator=" ", suffix=" FCFA", sentence_align="left", sentence=12.5, signature="italic", signature_top=20, signature_right=0, proforma_label="facture pro forma", rule=True, simple=True, client_label="Doit", client_label_underline=True),
}

MODERN_STYLES = {
    "moderne_clair": dict(accent="#0f766e", soft="#dff7f1", alt="#f59e0b", ink="#17202a", muted="#64748b", panel="#f8fafc", table_head="#0f766e", table_text="#ffffff", border="#d9e2ec", watermark="DOCUMENT"),
    "moderne_bandeau": dict(accent="#1f2937", soft="#fff1e6", alt="#c2410c", ink="#111827", muted="#6b7280", panel="#fffaf5", table_head="#1f2937", table_text="#ffffff", border="#e7d6c4", watermark="OFFICIEL"),
    "moderne_minimal": dict(accent="#334155", soft="#eef7f4", alt="#0f766e", ink="#0f172a", muted="#64748b", panel="#ffffff", table_head="#edf2f7", table_text="#0f172a", border="#d7dee8", watermark="PDF"),
}

DOCUMENT_NAMES = {"INVOICE": "FACTURE", "QUOTE": "DEVIS", "PROFORMA": "FACTURE PROFORMA", "DELIVERY_NOTE": "BON DE LIVRAISON", "RECEIPT": "REÇU"}
FONT_NAMES = {"times": "Times-Roman", "arial": "Helvetica", "calibri": "Helvetica", "segoe": "Helvetica", "courier": "Courier", "trebuchet": "Helvetica"}
ULTRA_COMPACT_STYLE = "ultra_compact"


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _quantity(value) -> str:
    number = _decimal(value)
    return str(int(number)) if number == number.to_integral_value() else f"{number.normalize():f}".replace(".", ",")


def _reference_money(value, separator="", suffix="") -> str:
    number = _decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if number < 0 else ""
    digits = str(abs(int(number)))
    if separator:
        digits = f"{abs(int(number)):,}".replace(",", separator)
    return f"{sign}{digits}{suffix}"


def _money(value) -> str:
    return f"{_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}".replace(",", " ").replace(".", ",") + " FCFA"


def _amount_words(value) -> str:
    """French amount spelling equivalent to Boulangerie's dependency fallback."""
    units = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
    tens = ["", "dix", "vingt", "trente", "quarante", "cinquante", "soixante", "soixante-dix", "quatre-vingt", "quatre-vingt-dix"]

    def under_hundred(number):
        if number < 20:
            return units[number]
        if number < 70:
            ten, unit = divmod(number, 10)
            return tens[ten] if not unit else f"{tens[ten]}{' et ' if unit == 1 and ten != 8 else '-'}{units[unit]}"
        if number < 80:
            rest = number - 60
            return "soixante" if not rest else f"soixante-{'et ' if rest == 11 else ''}{units[rest]}"
        return "quatre-vingts" if number == 80 else f"quatre-vingt-{units[number - 80]}"

    def spell(number):
        if number < 100:
            return under_hundred(number)
        if number < 1000:
            hundreds, rest = divmod(number, 100)
            prefix = "cent" if hundreds == 1 else f"{units[hundreds]} cent"
            return prefix + ("s" if not rest and hundreds > 1 else "") if not rest else f"{prefix} {spell(rest)}"
        if number < 1_000_000:
            thousands, rest = divmod(number, 1000)
            prefix = "mille" if thousands == 1 else f"{spell(thousands)} mille"
            return prefix if not rest else f"{prefix} {spell(rest)}"
        if number < 1_000_000_000:
            millions, rest = divmod(number, 1_000_000)
            prefix = "un million" if millions == 1 else f"{spell(millions)} millions"
            return prefix if not rest else f"{prefix} {spell(rest)}"
        billions, rest = divmod(number, 1_000_000_000)
        prefix = "un milliard" if billions == 1 else f"{spell(billions)} milliards"
        return prefix if not rest else f"{prefix} {spell(rest)}"

    number = _decimal(value)
    integer = max(0, int(number))
    cents = int(((number - integer) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    result = spell(integer).capitalize()
    return f"{result}{f' virgule {spell(cents)}' if cents else ''} francs CFA"


def _reference_amount_words(value) -> str:
    """Boulangerie's scanned templates append ``FCFA`` after the digits.

    Their amount-in-words block therefore removes the currency suffix before
    composing ``… (12 000) FCFA``.  Keep that tiny but visible convention.
    """
    text = _amount_words(value).strip()
    lowered = text.lower()
    for suffix in (" francs cfa", " franc cfa"):
        if lowered.endswith(suffix):
            return text[: -len(suffix)].strip()
    return text


def _document_title(invoice, config=None):
    kind = str(getattr(invoice, "document_type", "INVOICE") or "INVOICE")
    return config["title"] if kind == "PROFORMA" and config else DOCUMENT_NAMES.get(kind, "FACTURE")


def _document_label(invoice, config=None):
    kind = str(getattr(invoice, "document_type", "INVOICE") or "INVOICE")
    if kind == "QUOTE":
        return "devis"
    if kind == "PROFORMA":
        return (config or {}).get("proforma_label", "facture proforma")
    return "reçu" if kind == "RECEIPT" else "facture"


def _document_article(invoice):
    return "le présent" if str(getattr(invoice, "document_type", "")) in {"QUOTE", "RECEIPT"} else "la présente"


def _colour(value, fallback="#111111"):
    return colors.HexColor(value or fallback)


def _font_variant(font, bold=False, italic=False):
    if font == "Times-Roman":
        return "Times-BoldItalic" if bold and italic else "Times-Bold" if bold else "Times-Italic" if italic else font
    if font == "Courier":
        return "Courier-BoldOblique" if bold and italic else "Courier-Bold" if bold else "Courier-Oblique" if italic else font
    return "Helvetica-BoldOblique" if bold and italic else "Helvetica-Bold" if bold else "Helvetica-Oblique" if italic else font


def _wrap(value, font, size, max_width):
    words = str(value or "").replace("\r", " ").replace("\n", " ").split()
    lines, current = [], ""
    for word in words:
        proposal = word if not current else f"{current} {word}"
        if not current or pdfmetrics.stringWidth(proposal, font, size) <= max_width:
            current = proposal
        else:
            lines.append(current)
            current = word
    return lines + ([current] if current else [])


def _draw_text(pdf, lines, x, y, width, font, size, leading, align="left", limit=None):
    pdf.setFont(font, size)
    for line in lines[:limit]:
        if align == "center":
            pdf.drawCentredString(x + width / 2, y, line)
        elif align == "right":
            pdf.drawRightString(x + width, y, line)
        else:
            pdf.drawString(x, y, line)
        y -= leading
    return y


def _fit_text(value, font, size, max_width):
    """Keep a compact PDF label on one line without drawing outside its cell."""
    text = " ".join(str(value or "").split())
    if pdfmetrics.stringWidth(text, font, size) <= max_width:
        return text
    suffix = "..."
    while text and pdfmetrics.stringWidth(text + suffix, font, size) > max_width:
        text = text[:-1]
    return text.rstrip() + suffix if text else suffix


def _rule(pdf, x1, y, x2, colour="#111111", thickness=.55):
    pdf.setStrokeColor(_colour(colour))
    pdf.setLineWidth(thickness)
    pdf.line(x1, y, x2, y)


def _logo_reader(url):
    """Read a logo saved by FUSAA or a public HTTPS logo.

    Billing used to accept only a Cloudinary URL here.  That meant a logo
    selected from the header form could be stored but silently disappear from
    every generated PDF whenever Cloudinary was not configured.  Local
    ``storage://billing-logos`` references are now the primary path, while
    existing public HTTPS links remain compatible with imported headers.
    """
    value = str(url or "").strip()
    if not value:
        return None
    local_prefix = "storage://billing-logos/"
    if value.startswith(local_prefix):
        filename = Path(value[len(local_prefix):]).name
        root = (settings.storage_dir / "billing-logos").resolve()
        path = (root / filename).resolve()
        if path.parent != root or not path.is_file():
            return None
        try:
            return ImageReader(str(path))
        except Exception:
            return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    try:
        request = Request(value, headers={"User-Agent": "FUSAA-PDF/1.0", "Accept": "image/*"})
        with urlopen(request, timeout=4) as response:
            content = response.read(2_000_001)
            content_type = str(response.headers.get("Content-Type", "")).lower()
        if len(content) > 2_000_000 or (content_type and not content_type.startswith("image/")):
            return None
        return ImageReader(BytesIO(content))
    except Exception:
        return None


def _draw_logo(pdf, logo, x, top, width, height):
    if not logo:
        return False
    try:
        pdf.drawImage(logo, x, top - height, width=width, height=height, preserveAspectRatio=True, anchor="nw", mask="auto")
        return True
    except Exception:
        return False


def _draw_qr(pdf, value, x, y, size):
    try:
        widget = qr.QrCodeWidget(value)
        low_x, low_y, high_x, high_y = widget.getBounds()
        drawing = Drawing(size, size, transform=[size / (high_x - low_x), 0, 0, size / (high_y - low_y), 0, 0])
        drawing.add(widget)
        renderPDF.draw(drawing, pdf, x, y)
    except Exception:
        pdf.setStrokeColor(_colour("#999999"))
        pdf.rect(x, y, size, size, fill=0, stroke=1)


def _company_lines(header, commercial=False):
    lines = [str(getattr(header, "company_name", "") or "")]
    address = [part.strip() for part in str(getattr(header, "address", "") or "").splitlines() if part.strip()]
    if commercial:
        lines += address
        lines += [f"RCCM: {header.rccm}" for _ in [0] if getattr(header, "rccm", None)]
        lines += [f"NIF: {header.nif}" for _ in [0] if getattr(header, "nif", None)]
        lines += [f"Tel: {header.phone}" for _ in [0] if getattr(header, "phone", None)]
    else:
        lines += [f"NIF : {header.nif}" for _ in [0] if getattr(header, "nif", None)]
        lines += [f"CEL : {header.phone}" for _ in [0] if getattr(header, "phone", None)]
        lines += address
    return [line.upper() for line in lines if line]


def _client_lines(customer):
    if not customer:
        return ["Client comptant"]
    first = str(getattr(customer, "name", "") or "Client comptant")
    if getattr(customer, "phone", None):
        first += f" / Tel : {customer.phone}"
    return [first] + [part.strip() for part in str(getattr(customer, "address", "") or "").splitlines() if part.strip()]


def _customer_contact_lines(customer, include_email=False):
    """Client details in the same order as the Boulangerie standard/modern PDFs."""
    lines = _client_lines(customer)
    if include_email and customer and getattr(customer, "email", None):
        lines.append(f"Email: {customer.email}")
    return lines


def _total(line):
    total = getattr(line, "total_amount", None)
    return _decimal(total) if total is not None else _decimal(getattr(line, "quantity", 0)) * _decimal(getattr(line, "unit_amount", 0))


def _totals(invoice, header, *, no_tax_label="Total", always_ht=False):
    subtotal, discount = _decimal(getattr(invoice, "subtotal_amount", 0)), _decimal(getattr(invoice, "discount_amount", 0))
    taxable = max(Decimal("0"), subtotal - discount)
    rows = [("Remise", -discount)] if discount else []
    rows.append(("Total HT", taxable))
    isb, tax = _decimal(getattr(invoice, "isb_amount", 0)), _decimal(getattr(invoice, "tax_amount", 0))
    if isb:
        rows += [(f"ISB ({_quantity(getattr(header, 'isb_rate', 0))}%)", -isb), ("Total net", _decimal(getattr(invoice, "total_amount", taxable - isb)))]
    elif tax:
        rows += [(f"TVA ({_quantity(getattr(invoice, 'tax_rate', 0))}%)", tax), ("Total TTC", _decimal(getattr(invoice, "total_amount", taxable + tax)))]
    else:
        total = _decimal(getattr(invoice, "total_amount", taxable))
        if always_ht:
            rows.append(("Total TTC", total))
        else:
            rows[-1] = (no_tax_label, total)
    return rows


def _reference_header(pdf, invoice, header, customer, logo, cfg, width, height, continued=False):
    top, right, _bottom, left = [part * mm for part in cfg["margins"]]
    available, y, font = width - left - right, height - top, cfg["font"]
    company_x = left + cfg["indent"] * mm
    if cfg.get("simple"):
        _draw_logo(pdf, logo, left, y, 29 * mm, 23 * mm)
        company_x = left + 37 * mm
    company_width = available - (company_x - left)
    y = _draw_text(pdf, _company_lines(header, cfg.get("simple", False)), company_x, y, company_width, _font_variant(font, True), cfg["head"], cfg["head"] * 1.14, cfg["align"])
    if cfg.get("rule"):
        y -= 3 * mm
        _rule(pdf, left if cfg.get("simple") else left + available * .09, y, left + available if cfg.get("simple") else left + available * .91, "#111111" if cfg.get("simple") else "#aaaaaa")
        y -= 3 * mm
    if continued:
        pdf.setFillColor(colors.black)
        pdf.setFont(_font_variant(font, True), 10)
        pdf.drawRightString(left + available, y, f"{_document_title(invoice, cfg)} — {getattr(invoice, 'number', '')}")
        return y - 8 * mm, left, available
    date = getattr(invoice, "issued_on", None) or datetime.now()
    date_text = date.strftime("%d/%m/%Y") if hasattr(date, "strftime") else str(date)
    y -= cfg["date_top"] * mm
    pdf.setFont(_font_variant(font, True), cfg["body"])
    pdf.drawRightString(left + available - 17 * mm, y, f"Zinder, {cfg['date_prefix']}{date_text}")
    y -= 9 * mm
    title = _document_title(invoice, cfg)
    pdf.setFont(_font_variant(font, True), cfg["title_size"])
    pdf.drawCentredString(left + available / 2, y, title)
    if cfg["underline"]:
        title_width = pdfmetrics.stringWidth(title, _font_variant(font, True), cfg["title_size"])
        _rule(pdf, left + (available - title_width) / 2, y - 1.2 * mm, left + (available + title_width) / 2)
    y -= 11 * mm
    client = _client_lines(customer)
    label = cfg.get("client_label", "DOIT")
    pdf.setFont(_font_variant(font, True), cfg["client"])
    pdf.drawString(left, y, f"{label} : {client[0]}")
    if cfg.get("client_label_underline", label == "DOIT"):
        _rule(pdf, left, y - 1 * mm, left + pdfmetrics.stringWidth(label, _font_variant(font, True), cfg["client"]))
    y -= cfg["client"] * 1.25
    y = _draw_text(pdf, client[1:], left + mm, y, available, font, cfg["client"], cfg["client"] * 1.25)
    subject = str(getattr(invoice, "subject", "") or "").strip()
    if subject:
        y -= 2 * mm
        y = _draw_text(pdf, _wrap(subject, _font_variant(font, True), cfg["client"], available), left, y, available, _font_variant(font, True), cfg["client"], cfg["client"] * 1.22, "center")
    return y - cfg["table_top"] * mm, left, available


def _render_reference(pdf, invoice, header, customer, lines, logo, style, width, height):
    cfg = REFERENCE_STYLES[style]
    y, left, available = _reference_header(pdf, invoice, header, customer, logo, cfg, width, height)
    delivery = str(getattr(invoice, "document_type", "")) == "DELIVERY_NOTE"
    if delivery:
        labels, parts = ["N°", "Désignation", "Quantité"], [9, 63, 28]
    elif cfg.get("simple"):
        labels, parts = ["N°", "Désignation", "Unité", "Quantité", cfg["unit_label"], "Montant"], cfg["widths"]
    else:
        labels, parts = ["N°", "Désignation", "Quantité", cfg["unit_label"], "Montant"], cfg["widths"]
    columns = [available * part / sum(parts) for part in parts]
    table_font = FONT_NAMES.get(getattr(header, "table_font_family", None) or "", cfg["font"])
    size = min(14, max(8, float(getattr(header, "table_font_size", None) or cfg["table"])))
    bottom = cfg["margins"][2] * mm

    def table_head(current_y):
        h = max(8 * mm, 9 * mm if any("\n" in item for item in labels) else 8 * mm)
        x = left
        for index, (label, col) in enumerate(zip(labels, columns)):
            if cfg["table_bg"]:
                pdf.setFillColor(_colour(cfg["table_bg"]))
                pdf.rect(x, current_y - h, col, h, fill=1, stroke=0)
            pdf.setStrokeColor(colors.black)
            pdf.rect(x, current_y - h, col, h, fill=0, stroke=1)
            pdf.setFillColor(colors.black)
            pdf.setFont(_font_variant(table_font, cfg["bold"]), size)
            for offset, part in enumerate(label.split("\n")):
                if index == 0:
                    pdf.drawCentredString(x + col / 2, current_y - 4.5 * mm - offset * size, part)
                else:
                    pdf.drawString(x + 2 * mm, current_y - 4.5 * mm - offset * size, part)
            x += col
        return current_y - h

    y = table_head(y)
    for row, line in enumerate(lines, 1):
        if delivery:
            values = [str(row), str(getattr(line, "description", "")), f"{_quantity(getattr(line, 'quantity', 0))} {getattr(line, 'unit', '')}".strip()]
        elif cfg.get("simple"):
            values = [str(row), str(getattr(line, "description", "")), str(getattr(line, "unit", "") or ""), _quantity(getattr(line, "quantity", 0)), _reference_money(getattr(line, "unit_amount", 0), cfg["separator"]), _reference_money(_total(line), cfg["separator"])]
        else:
            values = [str(row), str(getattr(line, "description", "")), _quantity(getattr(line, "quantity", 0)), _reference_money(getattr(line, "unit_amount", 0)), _reference_money(_total(line))]
        wrapped = _wrap(values[1], table_font, size, columns[1] - 4 * mm)
        row_h = max(8 * mm, len(wrapped) * size * 1.2 + 4 * mm)
        if y - row_h < bottom + 45 * mm:
            pdf.showPage()
            y, left, available = _reference_header(pdf, invoice, header, customer, logo, cfg, width, height, True)
            y = table_head(y)
        x = left
        for index, (value, col) in enumerate(zip(values, columns)):
            pdf.setStrokeColor(colors.black)
            pdf.rect(x, y - row_h, col, row_h, fill=0, stroke=1)
            pdf.setFillColor(colors.black)
            if index == 1:
                _draw_text(pdf, wrapped, x + 2 * mm, y - 4.5 * mm, col - 4 * mm, table_font, size, size * 1.2)
            else:
                pdf.setFont(table_font, size)
                if index == 0 or (index >= len(values) - 2 and not delivery):
                    pdf.drawCentredString(x + col / 2, y - 5 * mm, value)
                else:
                    pdf.drawString(x + 2 * mm, y - 5 * mm, value)
            x += col
        y -= row_h
    if delivery:
        y -= cfg["signature_top"] * mm
        pdf.setFont(_font_variant(cfg["font"], True), cfg["client"])
        pdf.drawString(left, y, "CERTIFIE SERVICE FAIT")
        pdf.drawRightString(left + available, y, "LE FOURNISSEUR")
        return
    y -= 1 * mm
    total_x = left + available * (.42 if cfg["total_center"] else .35)
    totals = _totals(invoice, header, no_tax_label=cfg["total_label"])
    for index, (label, amount) in enumerate(totals):
        h = 7 * mm
        if y - h < bottom + 28 * mm:
            pdf.showPage()
            y = height - cfg["margins"][0] * mm
        if cfg.get("simple") and index == len(totals) - 1:
            pdf.setFillColor(_colour("#d8d8d8"))
            pdf.rect(total_x, y - h, left + available - total_x, h, fill=1, stroke=0)
        pdf.setStrokeColor(colors.black)
        pdf.rect(total_x, y - h, left + available - total_x, h, fill=0, stroke=1)
        pdf.setFillColor(colors.black)
        pdf.setFont(_font_variant(cfg["font"], True), size)
        if cfg["total_center"]:
            pdf.drawCentredString(total_x + (left + available - total_x) * .3, y - 4.7 * mm, label)
        else:
            pdf.drawString(total_x + 2 * mm, y - 4.7 * mm, label)
        pdf.drawRightString(left + available - 2 * mm, y - 4.7 * mm, _reference_money(amount, cfg["separator"], cfg["suffix"]))
        y -= h
    amount = _decimal(getattr(invoice, "total_amount", 0))
    sentence = f"Arrête la présente {_document_label(invoice, cfg)} à la somme de : {_reference_amount_words(amount)} ({_reference_money(amount, cfg['separator'] or ' ')}) FCFA"
    y -= 3 * mm
    y = _draw_text(pdf, _wrap(sentence, cfg["font"], cfg["sentence"], available), left, y, available, cfg["font"], cfg["sentence"], cfg["sentence"] * 1.28, cfg["sentence_align"])
    y -= cfg["signature_top"] * mm
    pdf.setFont(_font_variant(cfg["font"], True, cfg["signature"] == "italic"), cfg["client"])
    kind = str(getattr(invoice, "document_type", ""))
    if kind == "INVOICE":
        pdf.drawString(left, y, "Pour acquit")
        pdf.drawRightString(left + available - cfg["signature_right"] * mm, y, "Signature" if cfg.get("simple") else "Le fournisseur")
    else:
        pdf.drawRightString(left + available - cfg["signature_right"] * mm, y, "Reçu" if kind == "RECEIPT" else "Signature")


def _render_ultra_compact(pdf, invoice, header, customer, lines, logo, width, height):
    """High-density A4 layout for up to thirty ordinary invoice lines.

    It intentionally keeps each line in its supplied order.  Short product
    names use a 5.7 mm row, so 30 products, totals and signatures fit on a
    single A4 page.  Long descriptions use a second line only when necessary.
    """
    # Same header as the Compact template; only the table below is denser.
    compact_cfg = REFERENCE_STYLES["scan_compact"]
    initial_y, left, available = _reference_header(pdf, invoice, header, customer, logo, compact_cfg, width, height)
    bottom = compact_cfg["margins"][2] * mm
    delivery = str(getattr(invoice, "document_type", "")) == "DELIVERY_NOTE"
    table_font = FONT_NAMES.get(getattr(header, "table_font_family", None) or "", "Helvetica")
    configured_size = float(getattr(header, "table_font_size", None) or 8)
    # This is the only visual difference from Compact: a dense table.
    font_size = min(6.0, max(5.0, configured_size - 3.0))
    title_font = _font_variant(table_font, True)

    def page_header(continued=False):
        y = height - top
        logo_drawn = _draw_logo(pdf, logo, left, y, 14 * mm, 12 * mm)
        company_x = left + (17 * mm if logo_drawn else 0)
        company_width = available * .56 - (company_x - left)
        pdf.setFillColor(_colour("#102b42"))
        pdf.setFont(title_font, 10.2)
        pdf.drawString(company_x, y - 3.8 * mm, _fit_text(getattr(header, "company_name", "FUSAA"), title_font, 10.2, company_width))
        details = " · ".join(item for item in (str(getattr(header, "address", "") or "").replace("\n", ", "), getattr(header, "phone", None), getattr(header, "email", None), getattr(header, "nif", None)) if item)
        pdf.setFillColor(_colour("#536879")); pdf.setFont(table_font, 6.2)
        pdf.drawString(company_x, y - 7.6 * mm, _fit_text(details, table_font, 6.2, company_width))
        pdf.setFillColor(_colour("#0d6470")); pdf.setFont(title_font, 9.5)
        pdf.drawRightString(left + available, y - 3.7 * mm, _document_title(invoice))
        pdf.setFillColor(_colour("#536879")); pdf.setFont(table_font, 6.5)
        issued = getattr(invoice, "issued_on", None) or datetime.now()
        date_text = issued.strftime("%d/%m/%Y") if hasattr(issued, "strftime") else str(issued)
        pdf.drawRightString(left + available, y - 7.5 * mm, _fit_text(f"N° {getattr(invoice, 'number', '')} · {date_text}", table_font, 6.5, available * .39))
        y -= 15 * mm
        if continued:
            pdf.setFillColor(_colour("#536879")); pdf.setFont(title_font, 6.4)
            pdf.drawString(left, y, "SUITE DES LIGNES")
            y -= 3.4 * mm
        else:
            client_text = "Client comptant" if not customer else " / ".join(part for part in (getattr(customer, "name", None), getattr(customer, "phone", None), getattr(customer, "address", None)) if part)
            pdf.setFillColor(_colour("#162c3b")); pdf.setFont(title_font, 7.1)
            pdf.drawString(left, y, "CLIENT : " + _fit_text(client_text, table_font, 7.1, available - 20 * mm))
            subject = str(getattr(invoice, "subject", "") or "").strip()
            if subject:
                pdf.setFillColor(_colour("#536879")); pdf.setFont(table_font, 6.3)
                pdf.drawRightString(left + available, y, _fit_text(subject, table_font, 6.3, available * .46))
            y -= 4.4 * mm
        _rule(pdf, left, y, left + available, "#0d6470", .7)
        return y - 2.4 * mm

    labels, parts = (["N°", "DÉSIGNATION", "QTÉ"], [7, 75, 18]) if delivery else (["N°", "DÉSIGNATION", "QTÉ", "P.U.", "TOTAL"], [7, 55, 10, 14, 14])
    columns = [available * part / sum(parts) for part in parts]

    def table_head(y):
        h, x = 4.2 * mm, left
        pdf.setFillColor(_colour("#11354e")); pdf.rect(left, y - h, available, h, fill=1, stroke=0)
        pdf.setFillColor(colors.white); pdf.setFont(title_font, 5.2)
        for index, (label, column) in enumerate(zip(labels, columns)):
            if index == 1: pdf.drawString(x + 1.0 * mm, y - 2.7 * mm, label)
            elif index in (0, 2): pdf.drawCentredString(x + column / 2, y - 2.7 * mm, label)
            else: pdf.drawRightString(x + column - 1.0 * mm, y - 2.7 * mm, label)
            x += column
        return y - h

    # ``initial_y`` comes from the exact Compact header above.
    y = table_head(initial_y)
    footer_space = 31 * mm if not delivery else 15 * mm
    for row, line in enumerate(lines, 1):
        values = [str(row), str(getattr(line, "description", "")), _quantity(getattr(line, "quantity", 0))]
        if not delivery:
            values += [_reference_money(getattr(line, "unit_amount", 0), " "), _reference_money(_total(line), " ")]
        wrapped = _wrap(values[1], table_font, font_size, columns[1] - 2.4 * mm)[:2] or [""]
        if len(wrapped) == 2 and pdfmetrics.stringWidth(wrapped[-1], table_font, font_size) > columns[1] - 4 * mm:
            wrapped[-1] = _fit_text(wrapped[-1], table_font, font_size, columns[1] - 4 * mm)
        row_h = max(4.1 * mm, len(wrapped) * 2.35 * mm + .8 * mm)
        if y - row_h < bottom + footer_space:
            pdf.showPage(); y = table_head(_reference_header(pdf, invoice, header, customer, logo, compact_cfg, width, height, True)[0])
        if row % 2 == 0:
            pdf.setFillColor(_colour("#edf4f5")); pdf.rect(left, y - row_h, available, row_h, fill=1, stroke=0)
        x = left
        for index, (value, column) in enumerate(zip(values, columns)):
            pdf.setStrokeColor(_colour("#8da7b4")); pdf.rect(x, y - row_h, column, row_h, fill=0, stroke=1)
            pdf.setFillColor(_colour("#152b3a"))
            if index == 1:
                _draw_text(pdf, wrapped, x + 1.0 * mm, y - 2.6 * mm, column - 2.0 * mm, table_font, font_size, 2.35 * mm)
            else:
                pdf.setFont(table_font, font_size)
                if index in (0, 2): pdf.drawCentredString(x + column / 2, y - 2.6 * mm, _fit_text(value, table_font, font_size, column - 1.6 * mm))
                else: pdf.drawRightString(x + column - 1.0 * mm, y - 2.6 * mm, _fit_text(value, table_font, font_size, column - 1.6 * mm))
            x += column
        y -= row_h

    if delivery:
        y -= 8 * mm; pdf.setFillColor(_colour("#152b3a")); pdf.setFont(title_font, 7)
        pdf.drawString(left, y, "CERTIFIE SERVICE FAIT"); pdf.drawRightString(left + available, y, "LE FOURNISSEUR")
        return

    totals = _totals(invoice, header, no_tax_label="TOTAL")
    total_x = left + available - 57 * mm
    if y - (len(totals) * 5.7 * mm + 22 * mm) < bottom:
        pdf.showPage(); y = table_head(_reference_header(pdf, invoice, header, customer, logo, compact_cfg, width, height, True)[0])
    y -= 2 * mm
    for index, (label, amount) in enumerate(totals):
        h = 4.8 * mm; final = index == len(totals) - 1
        pdf.setFillColor(_colour("#0d6470") if final else colors.white); pdf.setStrokeColor(_colour("#0d6470"))
        pdf.rect(total_x, y - h, 57 * mm, h, fill=1, stroke=1)
        pdf.setFillColor(colors.white if final else _colour("#152b3a")); pdf.setFont(title_font, 6.5)
        pdf.drawString(total_x + 1.8 * mm, y - 3.7 * mm, label); pdf.drawRightString(left + available - 1.8 * mm, y - 3.7 * mm, _reference_money(amount, " ") + " FCFA")
        y -= h
    y -= 3.2 * mm
    amount = _decimal(getattr(invoice, "total_amount", 0))
    sentence = f"Arrêté {_document_article(invoice)} {_document_label(invoice)} à la somme de : {_reference_amount_words(amount)} ({_reference_money(amount, ' ')}) FCFA."
    pdf.setFillColor(_colour("#536879")); pdf.setFont(table_font, 5.9)
    y = _draw_text(pdf, _wrap(sentence, table_font, 5.9, available), left, y, available, table_font, 5.9, 7.0)
    y -= 5 * mm; pdf.setFillColor(_colour("#152b3a")); pdf.setFont(title_font, 6.6)
    left_label, right_label = ("Pour acquit", "Le fournisseur") if str(getattr(invoice, "document_type", "")) == "INVOICE" else ("Signature", "Validation")
    pdf.drawString(left, y, left_label); pdf.drawRightString(left + available, y, right_label)


def _modern_header(pdf, invoice, header, customer, logo, cfg, width, height, continued=False):
    left, top, bottom = 11.5 * mm, 11.5 * mm, 11.5 * mm
    available, y = width - 2 * left, height - top
    accent, border, ink, muted = [_colour(cfg[key]) for key in ("accent", "border", "ink", "muted")]
    if continued:
        pdf.setFillColor(accent)
        pdf.rect(left, y - 12 * mm, available, 12 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(left + 4 * mm, y - 7.3 * mm, f"{_document_title(invoice)} — {getattr(invoice, 'number', '')}")
        return y - 17 * mm, left, available, bottom
    # Boulangerie's modern documents use a pale word mark behind the document.
    pdf.setFillColor(_colour(cfg["soft"]))
    pdf.setFont("Helvetica-Bold", 47)
    pdf.drawCentredString(left + available / 2, height - 105 * mm, cfg["watermark"])
    box_h = 36 * mm
    pdf.setFillColor(_colour(cfg["panel"])); pdf.setStrokeColor(border)
    pdf.rect(left, y - box_h, available, box_h, fill=1, stroke=1)
    pdf.setFillColor(accent); pdf.rect(left, y - box_h, 3 * mm, box_h, fill=1, stroke=0)
    logo_drawn = _draw_logo(pdf, logo, left + 6 * mm, y - 4 * mm, 22 * mm, 20 * mm)
    if not logo_drawn:
        pdf.setFillColor(muted); pdf.setFont("Helvetica-Bold", 8); pdf.drawCentredString(left + 17 * mm, y - 17 * mm, "LOGO")
    company_x, company_w = left + 33 * mm, available - 86 * mm
    pdf.setFillColor(accent)
    company_y = _draw_text(pdf, _wrap(getattr(header, "company_name", ""), "Helvetica-Bold", 16, company_w), company_x, y - 8 * mm, company_w, "Helvetica-Bold", 16, 18, limit=2)
    details = [part.strip() for part in str(getattr(header, "address", "") or "").splitlines() if part.strip()]
    details += [f"{label}: {getattr(header, name)}" for label, name in (("Tel", "phone"), ("Email", "email"), ("NIF", "nif"), ("RCCM", "rccm")) if getattr(header, name, None)]
    pdf.setFillColor(muted)
    _draw_text(pdf, details, company_x, min(company_y - mm, y - 20 * mm), company_w, "Helvetica", 7.8, 9.5, limit=4)
    card_w, card_x = 44 * mm, left + available - 48 * mm
    pdf.setFillColor(accent); pdf.rect(card_x, y - 13 * mm, card_w, 9 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white); pdf.setFont("Helvetica-Bold", 10); pdf.drawCentredString(card_x + card_w / 2, y - 10 * mm, _document_title(invoice))
    date = getattr(invoice, "issued_on", None) or datetime.now()
    date_text = date.strftime("%d/%m/%Y") if hasattr(date, "strftime") else str(date)
    pdf.setFillColor(ink); pdf.setFont("Helvetica", 7.5)
    pdf.drawRightString(card_x + card_w, y - 18 * mm, f"N° {getattr(invoice, 'number', '')}")
    pdf.drawRightString(card_x + card_w, y - 22 * mm, f"Date {date_text}")
    y -= box_h + 6 * mm
    customer_lines = _customer_contact_lines(customer, include_email=True)
    customer_detail_lines = customer_lines[1:]
    # The web template grows this card with its contact details.  Keep the
    # same behaviour for addresses spanning several lines instead of clipping
    # telephone or e-mail on the PDF.
    client_w = available - 33 * mm
    client_h = max(29 * mm, (18 + min(len(customer_detail_lines), 4) * 3.4) * mm)
    pdf.setFillColor(colors.white); pdf.setStrokeColor(border); pdf.rect(left, y - client_h, client_w, client_h, fill=1, stroke=1)
    pdf.setFillColor(_colour(cfg["alt"])); pdf.setFont("Helvetica-Bold", 7.5); pdf.drawString(left + 4 * mm, y - 6 * mm, "CLIENT")
    pdf.setFillColor(ink); pdf.setFont("Helvetica-Bold", 11); pdf.drawString(left + 4 * mm, y - 12 * mm, customer_lines[0])
    pdf.setFillColor(muted); _draw_text(pdf, customer_detail_lines, left + 4 * mm, y - 17 * mm, client_w - 8 * mm, "Helvetica", 7.6, 9.2, limit=4)
    qr_x = left + client_w + 4 * mm
    _draw_qr(pdf, f"{_document_title(invoice)} - N° {getattr(invoice, 'number', '')} - Montant: {_money(getattr(invoice, 'total_amount', 0))}", qr_x + 2 * mm, y - 25 * mm, 19 * mm)
    pdf.setFillColor(muted); pdf.setFont("Helvetica", 6.8); pdf.drawCentredString(qr_x + 11.5 * mm, y - 28.5 * mm, "Scannez-moi")
    y -= client_h + 5 * mm
    subject = str(getattr(invoice, "subject", "") or "").strip()
    if subject:
        subject_lines = _wrap(subject, "Helvetica-Bold", 9, available - 8 * mm)
        subject_h = max(8 * mm, len(subject_lines) * 4.5 * mm + 3 * mm)
        pdf.setFillColor(colors.white); pdf.setStrokeColor(border); pdf.rect(left, y - subject_h, available, subject_h, fill=1, stroke=1)
        pdf.setFillColor(ink)
        y = _draw_text(pdf, subject_lines, left + 4 * mm, y - 5 * mm, available - 8 * mm, "Helvetica-Bold", 9, 10.5, "center") - 3 * mm
    return y, left, available, bottom


def _render_modern(pdf, invoice, header, customer, lines, logo, style, width, height):
    cfg = MODERN_STYLES[style]
    y, left, available, bottom = _modern_header(pdf, invoice, header, customer, logo, cfg, width, height)
    delivery = str(getattr(invoice, "document_type", "")) == "DELIVERY_NOTE"
    labels, parts = (["N°", "DÉSIGNATION", "QUANTITÉ"], [8, 68, 24]) if delivery else (["N°", "DÉSIGNATION", "QTÉ", "P.U.", "TOTAL"], [8, 43, 13, 18, 18])
    columns = [available * item / 100 for item in parts]
    font, size = FONT_NAMES.get(getattr(header, "table_font_family", None) or "", "Helvetica"), min(14, max(8, float(getattr(header, "table_font_size", None) or 9)))
    accent, ink, border = [_colour(cfg[key]) for key in ("accent", "ink", "border")]

    def table_head(current_y):
        x = left
        for index, (label, col) in enumerate(zip(labels, columns)):
            pdf.setFillColor(_colour(cfg["table_head"])); pdf.rect(x, current_y - 8 * mm, col, 8 * mm, fill=1, stroke=0)
            pdf.setFillColor(_colour(cfg["table_text"])); pdf.setFont(_font_variant(font, True), size)
            if index in (0, 2): pdf.drawCentredString(x + col / 2, current_y - 5 * mm, label)
            elif index >= 3: pdf.drawRightString(x + col - 2 * mm, current_y - 5 * mm, label)
            else: pdf.drawString(x + 2 * mm, current_y - 5 * mm, label)
            x += col
        return current_y - 8 * mm

    y = table_head(y)
    for row, line in enumerate(lines, 1):
        values = [str(row), str(getattr(line, "description", "")), _quantity(getattr(line, "quantity", 0))]
        if not delivery: values += [_money(getattr(line, "unit_amount", 0)), _money(_total(line))]
        wrapped, row_h = _wrap(values[1], font, size, columns[1] - 4 * mm), None
        row_h = max(8 * mm, len(wrapped) * size * 1.25 + 4 * mm)
        if y - row_h < bottom + 55 * mm:
            pdf.showPage(); y, left, available, bottom = _modern_header(pdf, invoice, header, customer, logo, cfg, width, height, True); y = table_head(y)
        if row % 2 == 0:
            pdf.setFillColor(_colour(cfg["soft"])); pdf.rect(left, y - row_h, available, row_h, fill=1, stroke=0)
        x = left
        for index, (value, col) in enumerate(zip(values, columns)):
            pdf.setStrokeColor(border); pdf.rect(x, y - row_h, col, row_h, fill=0, stroke=1); pdf.setFillColor(ink)
            if index == 1: _draw_text(pdf, wrapped, x + 2 * mm, y - 4.6 * mm, col - 4 * mm, font, size, size * 1.25)
            else:
                pdf.setFont(font, size)
                if index in (0, 2): pdf.drawCentredString(x + col / 2, y - 5 * mm, value)
                else: pdf.drawRightString(x + col - 2 * mm, y - 5 * mm, value)
            x += col
        y -= row_h
    if delivery:
        y -= 19 * mm; pdf.setFillColor(ink); pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(left, y, "CERTIFIE SERVICE FAIT"); pdf.drawRightString(left + available, y, "LE FOURNISSEUR")
        return
    y -= 7 * mm
    amount, amount_w, totals_x = _decimal(getattr(invoice, "total_amount", 0)), available - 65 * mm, left + available - 57 * mm
    sentence = f"Arrête {_document_article(invoice)} {_document_label(invoice)} à la somme de :\n{_amount_words(amount)} ({_money(amount)})"
    sentence_lines = [line for part in sentence.splitlines() for line in _wrap(part, "Helvetica", 8.2, amount_w - 7 * mm)]
    totals = _totals(invoice, header, always_ht=True); sentence_h, totals_h = max(23 * mm, len(sentence_lines) * 4.6 * mm + 8 * mm), len(totals) * 8 * mm
    if y - max(sentence_h, totals_h) < bottom + 32 * mm:
        pdf.showPage(); y, left, available, bottom = _modern_header(pdf, invoice, header, customer, logo, cfg, width, height, True); amount_w, totals_x = available - 65 * mm, left + available - 57 * mm
    pdf.setFillColor(_colour(cfg["soft"])); pdf.rect(left, y - sentence_h, amount_w, sentence_h, fill=1, stroke=0); pdf.setFillColor(ink)
    _draw_text(pdf, sentence_lines, left + 4 * mm, y - 5 * mm, amount_w - 7 * mm, "Helvetica", 8.2, 10.2)
    current_y = y
    for index, (label, value) in enumerate(totals):
        final = index == len(totals) - 1
        pdf.setFillColor(accent if final else colors.white); pdf.setStrokeColor(border); pdf.rect(totals_x, current_y - 8 * mm, 57 * mm, 8 * mm, fill=1, stroke=1)
        pdf.setFillColor(colors.white if final else ink); pdf.setFont("Helvetica-Bold", 8.3)
        pdf.drawString(totals_x + 3 * mm, current_y - 5 * mm, label); pdf.drawRightString(totals_x + 54 * mm, current_y - 5 * mm, _money(value)); current_y -= 8 * mm
    y -= max(sentence_h, totals_h) + 8 * mm
    notes = str(getattr(invoice, "notes", "") or "").strip()
    if notes:
        note_lines = _wrap(notes, "Helvetica", 8, available - 8 * mm); note_h = len(note_lines) * 4.5 * mm + 8 * mm
        pdf.setFillColor(colors.white); pdf.setStrokeColor(border); pdf.rect(left, y - note_h, available, note_h, fill=1, stroke=1)
        pdf.setFillColor(_colour(cfg["alt"])); pdf.setFont("Helvetica-Bold", 7.5); pdf.drawString(left + 4 * mm, y - 4.5 * mm, "NOTES")
        pdf.setFillColor(ink); y = _draw_text(pdf, note_lines, left + 4 * mm, y - 9 * mm, available - 8 * mm, "Helvetica", 8, 10) - 4 * mm
    y -= 15 * mm
    pdf.setFillColor(ink); pdf.setFont("Helvetica-Bold", 8.5); kind = str(getattr(invoice, "document_type", ""))
    if kind == "DELIVERY_NOTE":
        left_label, right_label = "CERTIFIE SERVICE FAIT", "LE FOURNISSEUR"
    elif kind == "INVOICE":
        left_label, right_label = "Pour acquit", "Le fournisseur"
    elif kind == "QUOTE":
        left_label, right_label = "Signature", "Bon pour accord"
    elif kind == "RECEIPT":
        left_label, right_label = "Caisse", "Client"
    else:
        left_label, right_label = "Signature", "Validation client"
    pdf.drawString(left, y, left_label); pdf.drawRightString(left + available, y, right_label)
    _rule(pdf, left, y - mm, left + 34 * mm, cfg["accent"]); _rule(pdf, left + available - 34 * mm, y - mm, left + available, cfg["accent"])
    pdf.setFillColor(_colour(cfg["muted"])); pdf.setFont("Helvetica", 6.8)
    pdf.drawCentredString(left + available / 2, max(bottom + 2 * mm, y - 12 * mm), f"Généré le {(getattr(invoice, 'issued_on', None) or datetime.now()):%d/%m/%Y} - Merci pour votre confiance")


def _render_standard(pdf, invoice, header, customer, lines, logo, width, height):
    """Boulangerie's original classic layout, preserved for 'standard' headers."""
    left, right, top, bottom = 20 * mm, 20 * mm, 12.7 * mm, 12.7 * mm
    available, y = width - left - right, height - top
    _draw_logo(pdf, logo, left, y, 32 * mm, 25 * mm)
    company_x, company_width = left + 39 * mm, available - 39 * mm
    table_font = FONT_NAMES.get(getattr(header, "table_font_family", None) or "", "Times-Roman")
    table_size = min(14, max(8, float(getattr(header, "table_font_size", None) or 9)))
    pdf.setFillColor(_colour("#333333"))
    company_y = _draw_text(pdf, _wrap(getattr(header, "company_name", ""), "Times-Bold", 14, company_width), company_x, y, company_width, "Times-Bold", 14, 16, limit=2)
    details = [part.strip() for part in str(getattr(header, "address", "") or "").splitlines() if part.strip()]
    details += [f"{label}: {getattr(header, field)}" for label, field in (("Tél", "phone"), ("Email", "email"), ("NIF", "nif"), ("RCCM", "rccm")) if getattr(header, field, None)]
    y = _draw_text(pdf, details, company_x, company_y - mm, company_width, "Times-Roman", 8.5, 10, limit=5)
    _rule(pdf, left, y - 4 * mm, left + available, "#333333", 1.4)
    y -= 15 * mm
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(left + available / 2, y, _document_title(invoice))
    y -= 12 * mm
    date = getattr(invoice, "issued_on", None) or datetime.now()
    date_text = date.strftime("%d/%m/%Y") if hasattr(date, "strftime") else str(date)
    pdf.setFont("Times-Roman", 10)
    pdf.drawString(left, y, f"Numéro: {getattr(invoice, 'number', '')}")
    y -= 5 * mm
    pdf.drawString(left, y, f"Date: {date_text}")
    y -= 12 * mm
    client = _customer_contact_lines(customer, include_email=True)
    pdf.setFont("Times-Bold", 10)
    pdf.drawString(left, y, "Facturé à:")
    y -= 5 * mm
    pdf.drawString(left, y, client[0])
    y -= 5 * mm
    y = _draw_text(pdf, client[1:], left, y, available, "Times-Roman", 9, 11)
    subject = str(getattr(invoice, "subject", "") or "").strip()
    if subject:
        y -= 3 * mm
        y = _draw_text(pdf, _wrap(subject, "Times-Bold", 10, available), left, y, available, "Times-Bold", 10, 12, "center")
    delivery = str(getattr(invoice, "document_type", "")) == "DELIVERY_NOTE"
    labels, parts = (["N°", "Désignation", "Quantité"], [8, 63, 29]) if delivery else (["N°", "Désignation", "Quantité", "Prix unitaire", "Total"], [8, 42, 14, 18, 18])
    columns = [available * part / 100 for part in parts]
    y -= 3 * mm

    def table_head(current_y):
        x = left
        for index, (label, col) in enumerate(zip(labels, columns)):
            pdf.setFillColor(_colour("#f0f0f0")); pdf.setStrokeColor(_colour("#999999"))
            pdf.rect(x, current_y - 7 * mm, col, 7 * mm, fill=1, stroke=1)
            pdf.setFillColor(_colour("#333333")); pdf.setFont(_font_variant(table_font, True), table_size)
            if index in (0, 2): pdf.drawCentredString(x + col / 2, current_y - 4.5 * mm, label)
            elif index >= 3: pdf.drawRightString(x + col - 2 * mm, current_y - 4.5 * mm, label)
            else: pdf.drawString(x + 2 * mm, current_y - 4.5 * mm, label)
            x += col
        return current_y - 7 * mm

    y = table_head(y)
    for row, line in enumerate(lines, 1):
        values = [str(row), str(getattr(line, "description", "")), _quantity(getattr(line, "quantity", 0))]
        if not delivery: values += [_money(getattr(line, "unit_amount", 0)), _money(_total(line))]
        wrapped = _wrap(values[1], table_font, table_size, columns[1] - 4 * mm)
        row_h = max(7 * mm, len(wrapped) * table_size * 1.22 + 3 * mm)
        if y - row_h < bottom + 45 * mm:
            pdf.showPage()
            y = height - top
            y = table_head(y)
        if row % 2 == 0:
            pdf.setFillColor(_colour("#f9f9f9")); pdf.rect(left, y - row_h, available, row_h, fill=1, stroke=0)
        x = left
        for index, (value, col) in enumerate(zip(values, columns)):
            pdf.setStrokeColor(_colour("#dddddd")); pdf.rect(x, y - row_h, col, row_h, fill=0, stroke=1)
            pdf.setFillColor(_colour("#333333"))
            if index == 1: _draw_text(pdf, wrapped, x + 2 * mm, y - 4 * mm, col - 4 * mm, table_font, table_size, table_size * 1.22)
            else:
                pdf.setFont(table_font, table_size)
                if index in (0, 2): pdf.drawCentredString(x + col / 2, y - 4.5 * mm, value)
                else: pdf.drawRightString(x + col - 2 * mm, y - 4.5 * mm, value)
            x += col
        y -= row_h
    if not delivery:
        y -= 6 * mm
        total_x = left + available * .5
        totals = _totals(invoice, header, always_ht=True)
        for index, (label, value) in enumerate(totals):
            final = index == len(totals) - 1
            _rule(pdf, total_x, y, left + available, "#333333" if final else "#dddddd", 1.2 if final else .5)
            pdf.setFillColor(_colour("#333333")); pdf.setFont("Helvetica-Bold" if final else "Helvetica", 9)
            pdf.drawString(total_x + 2 * mm, y - 4 * mm, label)
            pdf.drawRightString(left + available, y - 4 * mm, _money(value))
            y -= 7 * mm
        amount = _decimal(getattr(invoice, "total_amount", 0))
        y -= 4 * mm
        intro = "Arrêté(e) le présent" if str(getattr(invoice, "document_type", "")) in {"QUOTE", "RECEIPT"} else "Arrêté(e) la présente"
        sentence = f"{intro} {_document_label(invoice)} à la somme de : {_amount_words(amount)} ({_money(amount)})"
        y = _draw_text(pdf, _wrap(sentence, "Times-Bold", 9, available), left, y, available, "Times-Bold", 9, 11, "center")
    else:
        amount = _decimal(getattr(invoice, "total_amount", 0))

    # Boulangerie's original standard template always ends with a QR marker,
    # generation footer and a signature block, including delivery notes.
    if y - 58 * mm < bottom:
        pdf.showPage()
        y = height - top
    qr_y = y - 24 * mm
    _draw_qr(pdf, f"{_document_title(invoice)} - N° {getattr(invoice, 'number', '')} - Montant: {_money(amount)}", left, qr_y, 20 * mm)
    pdf.setFillColor(_colour("#333333")); pdf.setFont("Helvetica-Bold", 6.8)
    pdf.drawCentredString(left + 10 * mm, qr_y - 3 * mm, "Scannez-moi")
    date = getattr(invoice, "issued_on", None) or datetime.now()
    date_text = date.strftime("%d/%m/%Y") if hasattr(date, "strftime") else str(date)
    footer_y = qr_y - 11 * mm
    _rule(pdf, left, footer_y + 3 * mm, left + available, "#dddddd", .5)
    pdf.setFillColor(_colour("#666666")); pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(left + available / 2, footer_y, f"Généré le {date_text}")
    pdf.drawCentredString(left + available / 2, footer_y - 4 * mm, "Merci pour votre confiance")
    signature_y = footer_y - 13 * mm
    kind = str(getattr(invoice, "document_type", ""))
    pdf.setFillColor(_colour("#333333")); pdf.setFont("Times-Bold", 11)
    if kind == "INVOICE":
        left_label, right_label = "Pour acquit", "Le fournisseur"
        pdf.drawString(left, signature_y, left_label); pdf.drawRightString(left + available, signature_y, right_label)
        _rule(pdf, left, signature_y - 1.4 * mm, left + pdfmetrics.stringWidth(left_label, "Times-Bold", 11), "#333333", .5)
        _rule(pdf, left + available - pdfmetrics.stringWidth(right_label, "Times-Bold", 11), signature_y - 1.4 * mm, left + available, "#333333", .5)
    elif kind == "DELIVERY_NOTE":
        left_label, right_label = "CERTIFIE SERVICE FAIT", "LE FOURNISSEUR"
        pdf.drawString(left, signature_y, left_label); pdf.drawRightString(left + available, signature_y, right_label)
        _rule(pdf, left, signature_y - 1.4 * mm, left + pdfmetrics.stringWidth(left_label, "Times-Bold", 11), "#333333", .5)
        _rule(pdf, left + available - pdfmetrics.stringWidth(right_label, "Times-Bold", 11), signature_y - 1.4 * mm, left + available, "#333333", .5)
    elif kind in {"QUOTE", "PROFORMA"}:
        pdf.drawRightString(left + available, signature_y, "Signature")
        _rule(pdf, left + available - 42 * mm, signature_y - 8 * mm, left + available, "#333333", .5)
    elif kind == "RECEIPT":
        pdf.drawRightString(left + available, signature_y, f"Reçu le {date_text}")


def render_invoice_pdf(path: Path, invoice, header, customer, lines):
    """Write an invoice PDF using the selected Boulangerie header style."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    # The chosen style belongs to the document once it has been issued.  The
    # header remains the default only for older documents without a snapshot.
    style = str(getattr(invoice, "document_style", None) or getattr(header, "document_style", "standard") or "standard")
    logo = _logo_reader(getattr(header, "logo_url", None))
    if style == ULTRA_COMPACT_STYLE:
        _render_ultra_compact(pdf, invoice, header, customer, lines, logo, width, height)
    elif style in REFERENCE_STYLES:
        _render_reference(pdf, invoice, header, customer, lines, logo, style, width, height)
    elif style in MODERN_STYLES:
        _render_modern(pdf, invoice, header, customer, lines, logo, style, width, height)
    else:
        _render_standard(pdf, invoice, header, customer, lines, logo, width, height)
    pdf.save()
