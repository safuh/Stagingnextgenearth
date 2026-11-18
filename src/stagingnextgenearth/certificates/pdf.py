"""Render a one-page, verifiable course-completion certificate."""

from datetime import datetime
from io import BytesIO
from pathlib import Path

import reportlab
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("Vera", str(_FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("Vera-Bold", str(_FONT_DIR / "VeraBd.ttf")))


def _draw_fitted_centered(
    pdf: canvas.Canvas,
    text: str,
    *,
    center_x: float,
    y: float,
    font_name: str,
    font_size: float,
    minimum_size: float,
    max_width: float,
) -> None:
    """Fit long organisation, recipient, and course names inside the frame."""
    size = font_size
    while size > minimum_size and pdfmetrics.stringWidth(text, font_name, size) > max_width:
        size -= 0.5
    pdf.setFont(font_name, size)
    pdf.drawCentredString(center_x, y, text)


def render_certificate(
    *,
    recipient: str,
    course_title: str,
    organization_name: str,
    certificate_number: str,
    verification_code: str,
    issued_at: datetime,
    verification_url: str,
) -> bytes:
    """Return a landscape A4 PDF with a QR code to the public verification page."""
    output = BytesIO()
    page_width, page_height = landscape((297 * mm, 210 * mm))
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle(f"Certificate {certificate_number}")
    pdf.setAuthor(organization_name)
    pdf.setSubject(f"Completion of {course_title}")

    pdf.setFillColor(colors.HexColor("#F7F8F4"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#173D36"))
    pdf.setLineWidth(2.2)
    pdf.roundRect(13 * mm, 13 * mm, page_width - 26 * mm, page_height - 26 * mm, 4 * mm)
    pdf.setStrokeColor(colors.HexColor("#C39A54"))
    pdf.setLineWidth(0.8)
    pdf.roundRect(17 * mm, 17 * mm, page_width - 34 * mm, page_height - 34 * mm, 3 * mm)

    center = page_width / 2
    pdf.setFillColor(colors.HexColor("#173D36"))
    _draw_fitted_centered(
        pdf,
        organization_name.upper(),
        center_x=center,
        y=page_height - 36 * mm,
        font_name="Vera-Bold",
        font_size=12,
        minimum_size=8,
        max_width=page_width - 70 * mm,
    )
    pdf.setFillColor(colors.HexColor("#A77B35"))
    pdf.setFont("Vera-Bold", 25)
    pdf.drawCentredString(center, page_height - 57 * mm, "CERTIFICATE OF COMPLETION")
    pdf.setFillColor(colors.HexColor("#46534E"))
    pdf.setFont("Vera", 11)
    pdf.drawCentredString(center, page_height - 72 * mm, "This credential is proudly awarded to")

    pdf.setFillColor(colors.HexColor("#173D36"))
    display_recipient = recipient[:160]
    _draw_fitted_centered(
        pdf,
        display_recipient,
        center_x=center,
        y=page_height - 88 * mm,
        font_name="Vera-Bold",
        font_size=22,
        minimum_size=12,
        max_width=page_width - 80 * mm,
    )
    pdf.setFillColor(colors.HexColor("#46534E"))
    pdf.setFont("Vera", 11)
    pdf.drawCentredString(
        center, page_height - 103 * mm, "for successfully completing the learning programme"
    )
    pdf.setFillColor(colors.HexColor("#173D36"))
    _draw_fitted_centered(
        pdf,
        course_title[:180],
        center_x=center,
        y=page_height - 117 * mm,
        font_name="Vera-Bold",
        font_size=17,
        minimum_size=10,
        max_width=page_width - 80 * mm,
    )

    issued_label = issued_at.strftime("%d %B %Y")
    pdf.setFillColor(colors.HexColor("#46534E"))
    pdf.setFont("Vera", 9)
    pdf.drawCentredString(center, page_height - 137 * mm, f"Issued on {issued_label}")
    pdf.setFont("Vera-Bold", 9)
    pdf.drawCentredString(center, page_height - 145 * mm, f"Certificate No. {certificate_number}")

    qr = QrCodeWidget(verification_url)
    bounds = qr.getBounds()
    qr_width = bounds[2] - bounds[0]
    qr_height = bounds[3] - bounds[1]
    qr_size = 25 * mm
    drawing = Drawing(
        qr_size, qr_size, transform=[qr_size / qr_width, 0, 0, qr_size / qr_height, 0, 0]
    )
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, page_width - 52 * mm, 25 * mm)
    pdf.setFillColor(colors.HexColor("#46534E"))
    pdf.setFont("Vera", 7)
    pdf.drawRightString(page_width - 22 * mm, 20 * mm, "Scan to verify this credential")
    pdf.drawString(22 * mm, 22 * mm, f"Verification code: {verification_code}")
    pdf.drawString(
        22 * mm,
        17 * mm,
        "Public verification does not disclose the learner's private account details.",
    )

    pdf.showPage()
    pdf.save()
    return output.getvalue()
