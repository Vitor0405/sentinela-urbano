"""Document the reporter forwards to the municipal ombudsman (ouvidoria) once the
prefecture has missed the response deadline (improvement 4).

Contains protocol, photos, exact coordinate, dates and history: everything needed to
file a complaint without depending on any integration with the municipality.
"""

import io
from datetime import UTC, datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import Settings
from app.models import Occurrence, PhotoKind
from app.services.deadlines import ResponseClock
from app.services.photos import resolve_photo_path

TEAL = colors.HexColor("#0f5f4f")
ORANGE = colors.HexColor("#d9622b")
INK = colors.HexColor("#1b2622")
SOFT = colors.HexColor("#4d5b56")
PAPER = colors.HexColor("#f6f4ee")

STATUS_LABEL = {
    "aberta": "Aberta",
    "em_atendimento": "Em atendimento",
    "resolvida_pelo_agente": "Resolvida pelo agente",
    "confirmada": "Resolução confirmada",
    "contestada": "Resolução contestada",
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            textColor=TEAL,
            fontSize=20,
            leading=24,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            textColor=ORANGE,
            fontSize=11,
            leading=14,
            fontName="Helvetica-Bold",
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            textColor=TEAL,
            fontSize=13,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], textColor=INK, fontSize=10, leading=14
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], textColor=SOFT, fontSize=8, leading=10
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"], textColor=INK, fontSize=9.5, leading=12
        ),
        "label": ParagraphStyle(
            "label",
            parent=base["Normal"],
            textColor=SOFT,
            fontSize=9,
            leading=12,
            fontName="Helvetica-Bold",
        ),
    }


def _fmt(dt: datetime | None, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%d/%m/%Y %H:%M") if dt else "—"


def build_ouvidoria_pdf(
    occurrence: Occurrence,
    clock: ResponseClock,
    settings: Settings,
    prefecture_recipient: str | None,
) -> bytes:
    tz = ZoneInfo(settings.timezone)
    st = _styles()
    lat, lon = occurrence.latitude, occurrence.longitude
    osm = f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=19/{lat:.6f}/{lon:.6f}"
    tracking = f"{settings.public_web_url.rstrip('/')}/acompanhar/{occurrence.protocol}"
    generated = datetime.now(UTC)
    start = occurrence.notified_at or occurrence.created_at

    story = [
        Paragraph("Solicitação à Ouvidoria Municipal", st["title"]),
        Paragraph(
            f"Ocorrência sem resposta da prefeitura há {clock.days_without_response} dias "
            f"(prazo: {clock.deadline_days} dias) · Sentinela Urbano",
            st["subtitle"],
        ),
    ]

    facts = [
        ("Protocolo", occurrence.protocol),
        ("Tipo de risco", occurrence.type_label),
        ("Setor responsável", occurrence.type.department),
        ("Município", settings.service_area_name),
        ("Registrada em", _fmt(occurrence.created_at, tz)),
        (
            "Prefeitura avisada em",
            _fmt(occurrence.notified_at, tz)
            + (f" (e-mail para {prefecture_recipient})" if prefecture_recipient else "")
            if occurrence.notified_at
            else "aviso automático não confirmado; contagem a partir do registro",
        ),
        ("Dias sem resposta", f"{clock.days_without_response} (desde {_fmt(start, tz)})"),
        ("Situação atual", STATUS_LABEL.get(occurrence.status.value, occurrence.status.value)),
        ("Coordenadas", f"{lat:.6f}, {lon:.6f}"),
        ("Ver no mapa", osm),
    ]
    table = Table(
        [[Paragraph(k, st["label"]), Paragraph(escape(v), st["cell"])] for k, v in facts],
        colWidths=[4.2 * cm, 12.8 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, PAPER]),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcd8cc")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [table]

    if occurrence.description:
        story += [
            Paragraph("Descrição informada no registro", st["h2"]),
            Paragraph(escape(occurrence.description), st["body"]),
        ]

    images = []
    for photo in [p for p in occurrence.photos if p.kind == PhotoKind.REPORT][:3]:
        try:
            path = resolve_photo_path(settings.upload_dir, photo.storage_key)
            width = 5.4 * cm
            images.append(Image(str(path), width=width, height=width * photo.height / photo.width))
        except (OSError, ValueError):
            continue
    if images:
        story += [
            Paragraph("Fotos do registro", st["h2"]),
            Table([images], hAlign="LEFT", style=[("VALIGN", (0, 0), (-1, -1), "TOP")]),
            Paragraph(
                "Fotos tiradas pelo morador a partir da via pública; metadados (EXIF) removidos.",
                st["small"],
            ),
        ]

    history = [[Paragraph("Data", st["label"]), Paragraph("Situação", st["label"])]] + [
        [
            Paragraph(_fmt(h.created_at, tz), st["cell"]),
            Paragraph(STATUS_LABEL.get(h.to_status.value, h.to_status.value), st["cell"]),
        ]
        for h in occurrence.history
    ]
    history_table = Table(history, colWidths=[4.2 * cm, 12.8 * cm])
    history_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, TEAL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story += [Paragraph("Histórico", st["h2"]), history_table]

    reporter = ""
    if not occurrence.is_anonymous:
        if occurrence.author is not None:
            reporter = occurrence.author.name
        elif occurrence.reporter_name:
            reporter = occurrence.reporter_name
    request = (
        f"Venho solicitar providências quanto à ocorrência de protocolo "
        f"<b>{occurrence.protocol}</b>, registrada em {_fmt(occurrence.created_at, tz)} na "
        f"plataforma Sentinela Urbano e comunicada automaticamente à prefeitura em "
        f"{_fmt(start, tz)}. Até a emissão deste documento, a ocorrência permanece sem "
        f"resposta há <b>{clock.days_without_response} dias</b>, acima do prazo de "
        f"{clock.deadline_days} dias. Trata-se de risco ambiental associado à proliferação do "
        f"mosquito <i>Aedes aegypti</i>, transmissor de dengue, zika e chikungunya."
    )
    signature = Table(
        [
            [
                Paragraph("Nome do solicitante:", st["label"]),
                Paragraph(escape(reporter) or " ", st["cell"]),
            ],
            [Paragraph("Contato:", st["label"]), Paragraph(" ", st["cell"])],
            [Paragraph("Data e assinatura:", st["label"]), Paragraph(" ", st["cell"])],
        ],
        colWidths=[4.2 * cm, 12.8 * cm],
        rowHeights=[0.9 * cm] * 3,
    )
    signature.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (1, 0), (1, -1), 0.5, SOFT),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ]
        )
    )
    story += [
        KeepTogether(
            [
                Paragraph("Solicitação", st["h2"]),
                Paragraph(request, st["body"]),
                Spacer(1, 10),
                signature,
            ]
        )
    ]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SOFT)
        canvas.drawString(
            2 * cm,
            1.2 * cm,
            f"Gerado em {_fmt(generated, tz)} pelo Sentinela Urbano · acompanhe em {tracking}",
        )
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=2 * cm,
        title=f"Ouvidoria - {occurrence.protocol}",
        author="Sentinela Urbano",
        subject="Ocorrência sem resposta da prefeitura",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
