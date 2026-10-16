from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build_profile_pdf(profile, collaborations, issued_at=None):
    """Build a formal, printable profile and contribution-history PDF."""
    issued_at = issued_at or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Informe profesional - KelDev",
        author="KelDev",
        subject="Perfil y colaboraciones",
    )
    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PlatformTitle",
        parent=base_styles["Title"],
        textColor=colors.HexColor("#163a63"),
        alignment=TA_CENTER,
        fontSize=20,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "PlatformSubtitle",
        parent=base_styles["Normal"],
        textColor=colors.HexColor("#526579"),
        alignment=TA_CENTER,
        fontSize=10,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "PlatformSection",
        parent=base_styles["Heading2"],
        textColor=colors.HexColor("#163a63"),
        fontSize=13,
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "PlatformBody",
        parent=base_styles["BodyText"],
        fontSize=9,
        leading=12,
    )
    cell_style = ParagraphStyle(
        "PlatformCell",
        parent=body_style,
        fontSize=8,
        leading=10,
    )

    skills = profile.get("habilidades") or []
    if isinstance(skills, dict):
        skills = list(skills)
    score_map = profile.get("reputacion_habilidades") or {}
    if not isinstance(score_map, dict):
        score_map = {}
    active_skills = {
        str(skill).strip() for skill in skills if str(skill).strip()
    }
    skills = sorted(
        active_skills
        | {str(skill).strip() for skill in score_map if str(skill).strip()},
        key=str.casefold,
    )

    story = [
        Paragraph("KelDev", title_style),
        Paragraph(
            "INFORME PROFESIONAL DE COLABORACIÓN Y HABILIDADES",
            subtitle_style,
        ),
    ]

    identity_rows = [
        [
            Paragraph("<b>Nombre</b>", body_style),
            Paragraph(escape(str(profile.get("nombre") or "—")), body_style),
            Paragraph("<b>Correo</b>", body_style),
            Paragraph(escape(str(profile.get("email") or "—")), body_style),
        ],
        [
            Paragraph("<b>Fecha de emisión</b>", body_style),
            Paragraph(issued_at.astimezone().strftime("%d/%m/%Y %H:%M %Z"), body_style),
            Paragraph("<b>Cuenta</b>", body_style),
            Paragraph(escape(str(profile.get("id") or "—")), body_style),
        ],
        [
            Paragraph("<b>Reputación total</b>", body_style),
            Paragraph(str(int(profile.get("reputacion") or 0)), body_style),
            Paragraph("<b>Tareas completadas</b>", body_style),
            Paragraph(str(int(profile.get("tareas_completadas") or 0)), body_style),
        ],
    ]
    identity_table = Table(identity_rows, colWidths=[28 * mm, 88 * mm, 30 * mm, 104 * mm])
    identity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f6fa")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7d2df")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8e0e9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        identity_table,
    ])
    description = str(profile.get("descripcion") or "").strip()
    if description:
        description_table = Table(
            [[
                Paragraph("<b>Presentación</b>", body_style),
                Paragraph(escape(description), body_style),
            ]],
            colWidths=[30 * mm, 220 * mm],
        )
        description_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f6fa")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7d2df")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([description_table, Spacer(1, 4)])
    story.append(Paragraph("Perfil de habilidades", section_style))

    if skills:
        skill_rows = [[
            Paragraph("<b>Habilidad</b>", cell_style),
            Paragraph("<b>Reputación</b>", cell_style),
            Paragraph("<b>Estado</b>", cell_style),
        ]]
        skill_rows.extend(
            [
                Paragraph(escape(skill), cell_style),
                Paragraph(str(int(score_map.get(skill) or 0)), cell_style),
                Paragraph(
                    "En perfil" if skill in active_skills else "Histórica",
                    cell_style,
                ),
            ]
            for skill in skills
        )
        skill_table = Table(
            skill_rows,
            colWidths=[100 * mm, 40 * mm, 35 * mm],
            repeatRows=1,
        )
        skill_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6edf5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163a63")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7d2df")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8e0e9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(skill_table)
    else:
        story.append(Paragraph("No hay habilidades registradas.", body_style))

    story.append(Paragraph("Historial de colaboraciones", section_style))
    if collaborations:
        rows = [[
            Paragraph("<b>Tarea / proyecto</b>", cell_style),
            Paragraph("<b>Estado</b>", cell_style),
            Paragraph("<b>Dificultad</b>", cell_style),
            Paragraph("<b>Reputación por habilidad</b>", cell_style),
            Paragraph("<b>Fecha</b>", cell_style),
        ]]
        for item in collaborations:
            task = item.get("task") or {}
            project = item.get("project") or {}
            detail = item.get("reputacion_detalle") or {}
            if isinstance(detail, dict) and detail:
                detail_text = "<br/>".join(
                    f"{escape(str(skill))}: +{int(points or 0)}"
                    for skill, points in sorted(
                        detail.items(), key=lambda entry: str(entry[0]).casefold()
                    )
                )
            elif (
                item.get("workflow_state") == "completed"
                and item.get("reputacion_detalle_completo")
            ):
                detail_text = "0 puntos (sin habilidades coincidentes)"
            elif item.get("workflow_state") == "completed":
                detail_text = "Desglose histórico no disponible"
            else:
                detail_text = "Sin reputación otorgada"
            created = item.get("created_at") or ""
            if isinstance(created, str):
                created = created[:10]
            delivery_url = item.get("code_url") or item.get("github_pr_url")
            delivery_reference = ""
            if delivery_url:
                parsed_url = urlsplit(str(delivery_url))
                if (
                    parsed_url.scheme == "https"
                    and parsed_url.hostname == "github.com"
                ):
                    delivery_reference = (
                        '<br/><link href="'
                        + escape(str(delivery_url))
                        + '" color="#2563eb">Ver entrega en GitHub</link>'
                    )
                else:
                    delivery_reference = (
                        "<br/>Entrega: " + escape(str(delivery_url))
                    )
            rows.append([
                Paragraph(
                    f"<b>{escape(str(task.get('titulo') or 'Tarea'))}"
                    f" (#{escape(str(item.get('task_id') or '—'))})</b>"
                    f"<br/>{escape(str(project.get('titulo') or ''))}"
                    f"{delivery_reference}",
                    cell_style,
                ),
                Paragraph(
                    escape(str(item.get("estado_label") or item.get("estado") or "—")),
                    cell_style,
                ),
                Paragraph(escape(str(task.get("dificultad") or "—")), cell_style),
                Paragraph(detail_text, cell_style),
                Paragraph(escape(str(created or "—")), cell_style),
            ])
        contribution_table = Table(
            rows,
            colWidths=[70 * mm, 42 * mm, 30 * mm, 92 * mm, 28 * mm],
            repeatRows=1,
        )
        contribution_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6edf5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163a63")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7d2df")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8e0e9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(contribution_table)
    else:
        story.append(Paragraph("No hay colaboraciones registradas.", body_style))

    story.extend([
        Spacer(1, 10),
        KeepTogether(Paragraph(
            "Documento generado automáticamente por KelDev a partir "
            "de los datos registrados en la plataforma en la fecha indicada.",
            subtitle_style,
        )),
    ])
    document.build(story)
    return buffer.getvalue()
