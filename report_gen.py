"""LOGITERRE 2026 — Professional PDF Campaign Report Generator"""
import io
from datetime import datetime
from collections import Counter

def generate_campaign_report(campaign_name, stats, contacts, timeline=None, gen_date=None):
    """Génère un rapport PDF professionnel de campagne.
    Retourne les bytes du PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm, mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                        TableStyle, HRFlowable)
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        return None  # reportlab not installed

    gen_date = gen_date or datetime.now().strftime("%d/%m/%Y %H:%M")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)

    NAVY  = colors.HexColor("#1a1a2e")
    PURPLE= colors.HexColor("#302b63")
    GREEN = colors.HexColor("#238636")
    RED   = colors.HexColor("#da3633")
    BLUE  = colors.HexColor("#1f6feb")
    GREY  = colors.HexColor("#888888")
    LIGHT = colors.HexColor("#f0f4ff")

    styles = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=styles["Title"], fontName="Helvetica-Bold",
                             fontSize=22, textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)
    sub_s   = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=11,
                             textColor=GREY, alignment=TA_CENTER, spaceAfter=20)
    h2_s    = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                             fontSize=14, textColor=PURPLE, spaceBefore=16, spaceAfter=8)
    body_s  = ParagraphStyle("B", parent=styles["Normal"], fontSize=10, textColor=NAVY)

    story = []

    # ── Header ────────────────────────────────────────────────
    story.append(Paragraph("🌍 LOGITERRE 2026", title_s))
    story.append(Paragraph("International Transport &amp; Logistics Forum — Casablanca, Morocco", sub_s))
    story.append(HRFlowable(width="100%", thickness=2, color=PURPLE, spaceAfter=12))

    story.append(Paragraph("Rapport de Campagne Email", h2_s))
    story.append(Paragraph(f"<b>Campagne :</b> {campaign_name}", body_s))
    story.append(Paragraph(f"<b>Date du rapport :</b> {gen_date}", body_s))
    story.append(Spacer(1, 14))

    # ── KPI cards (as table) ──────────────────────────────────
    total   = stats.get("total", 0)
    sent    = stats.get("sent", 0)
    opened  = stats.get("opened", 0)
    replied = stats.get("replied", 0)
    bounced = stats.get("bounced", 0)

    open_rate  = f"{opened*100//max(sent,1)}%"
    reply_rate = f"{replied*100//max(sent,1)}%"
    deliv_rate = f"{(sent-bounced)*100//max(sent,1)}%"

    kpi_data = [
        ["Total\ncontacts", "Emails\nenvoyés", "Taux de\nlivraison", "Taux\nd'ouverture", "Taux de\nréponse"],
        [str(total), str(sent), deliv_rate, open_rate, reply_rate],
    ]
    kpi_t = Table(kpi_data, colWidths=[3.3*cm]*5)
    kpi_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PURPLE),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 9),
        ("FONTNAME", (0,1), (-1,1), "Helvetica-Bold"),
        ("FONTSIZE", (0,1), (-1,1), 20),
        ("TEXTCOLOR", (0,1), (-1,1), NAVY),
        ("BACKGROUND", (0,1), (-1,1), LIGHT),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("GRID", (0,0), (-1,-1), 1, colors.white),
    ]))
    story.append(kpi_t)
    story.append(Spacer(1, 18))

    # ── Funnel ────────────────────────────────────────────────
    story.append(Paragraph("Entonnoir de conversion", h2_s))
    funnel_data = [["Étape", "Nombre", "Taux"]]
    funnel = [
        ("📋 Contacts ciblés", total, "100%"),
        ("📤 Emails envoyés", sent, f"{sent*100//max(total,1)}%"),
        ("✅ Livrés", sent-bounced, deliv_rate),
        ("👁️ Ouverts", opened, open_rate),
        ("💬 Réponses", replied, reply_rate),
    ]
    for label, num, rate in funnel:
        funnel_data.append([label, str(num), rate])
    ft = Table(funnel_data, colWidths=[7*cm, 4*cm, 4*cm])
    ft.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
        ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING", (0,0), (0,-1), 12),
    ]))
    story.append(ft)
    story.append(Spacer(1, 18))

    # ── Répartition par type ──────────────────────────────────
    type_counts = Counter(c.get("org_type","general") for c in contacts)
    if type_counts:
        story.append(Paragraph("Répartition par type d'organisation", h2_s))
        type_labels = {"academic":"🎓 Académique","government":"🏛️ Gouvernement",
                       "international":"🌐 International","federation":"🤝 Fédération",
                       "port":"⚓ Port","logistics":"📦 Logistique","industry":"🏭 Industrie",
                       "general":"📋 Général"}
        type_data = [["Type", "Contacts", "%"]]
        for t, cnt in type_counts.most_common():
            type_data.append([type_labels.get(t,t), str(cnt), f"{cnt*100//max(total,1)}%"])
        tt = Table(type_data, colWidths=[7*cm, 4*cm, 4*cm])
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), BLUE),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
            ("ALIGN", (1,0), (-1,-1), "CENTER"),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING", (0,0), (0,-1), 12),
        ]))
        story.append(tt)
        story.append(Spacer(1, 18))

    # ── Réponses reçues (top) ─────────────────────────────────
    repliers = [c for c in contacts if c.get("replied_at")]
    if repliers:
        story.append(Paragraph(f"Réponses reçues ({len(repliers)})", h2_s))
        rep_data = [["Organisation", "Email", "Date réponse"]]
        for c in repliers[:15]:
            rep_data.append([c.get("name","")[:35], c.get("email","")[:30],
                            (c.get("replied_at","") or "")[:10]])
        rt = Table(rep_data, colWidths=[6*cm, 6*cm, 3*cm])
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), GREEN),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#e8f5e9")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(rt)
        story.append(Spacer(1, 18))

    # ── Footer ────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=GREY))
    footer_s = ParagraphStyle("F", parent=styles["Normal"], fontSize=8,
                              textColor=GREY, alignment=TA_CENTER)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "LOGITERRE 2026 Organizing Committee — sg@logiterre-expo.com — +212 673 642 4246<br/>"
        f"Rapport généré automatiquement le {gen_date} — Document confidentiel",
        footer_s))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
