"""
Branded proposal PDF — the document that closes the deal.

ReportLab (pure pip, no system deps) renders a single-page financial case:
current vs. proposed equipment, annual savings, every incentive line with its
confirmation status, net investment, and payback. All figures arrive from
calc.py; nothing is computed (or invented) at render time.
"""

from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .schemas import ContractorProfile, ProposalCalc, SiteVisit

INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")
PAPER = colors.HexColor("#F3F4F6")

STATUS_BADGES = {
    "confirmed": ("CONFIRMED", colors.HexColor("#15803D")),
    "estimated_pending_approval": ("ESTIMATED — PENDING APPROVAL", colors.HexColor("#B45309")),
    "pending_rep_quote": ("AWAITING PROGRAM REP", colors.HexColor("#6B7280")),
    "financing": ("FINANCING", colors.HexColor("#1D4ED8")),
    "see_program_table": ("SEE PROGRAM TABLE", colors.HexColor("#6B7280")),
}


def _money(x: float | None) -> str:
    return f"${x:,.0f}" if x is not None else "—"


def _styles(brand: colors.Color) -> dict[str, ParagraphStyle]:
    base = dict(fontName="Helvetica", textColor=INK)
    return {
        "brand_big": ParagraphStyle("bb", fontName="Helvetica-Bold", fontSize=20,
                                    textColor=colors.white, leading=24),
        "brand_sub": ParagraphStyle("bs", fontName="Helvetica", fontSize=9,
                                    textColor=colors.white, leading=12),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12,
                             textColor=brand, spaceBefore=10, spaceAfter=4, leading=15),
        "body": ParagraphStyle("body", fontSize=9.5, leading=13, **base),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.5,
                                leading=10, textColor=MUTED),
        "big_number": ParagraphStyle("bn", fontName="Helvetica-Bold", fontSize=16,
                                     textColor=brand, leading=20),
    }


def render_proposal_pdf(
    visit: SiteVisit,
    calc: ProposalCalc,
    contractor: ContractorProfile,
    out_path: str,
) -> str:
    brand = colors.HexColor(contractor.brand_hex)
    s = _styles(brand)
    doc = SimpleDocTemplate(
        out_path, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title=f"Heating Upgrade Proposal — {visit.customer_name}",
        author=contractor.company_name,
    )
    content_w = doc.width
    story = []

    # Brand header band
    header = Table(
        [[Paragraph(contractor.company_name, s["brand_big"]),
          Paragraph(
              f"{contractor.contact_name}<br/>{contractor.phone}<br/>{contractor.email}",
              s["brand_sub"])]],
        colWidths=[content_w * 0.62, content_w * 0.38],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), brand),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
    ]))
    story += [header, Spacer(1, 10)]

    story.append(Paragraph(
        f"<b>Heating System Upgrade Proposal</b> &nbsp;·&nbsp; "
        f"{visit.customer_name} &nbsp;·&nbsp; {visit.site_address}, {visit.city} "
        f"&nbsp;·&nbsp; {date.today():%B %d, %Y}", s["body"]))
    story.append(Spacer(1, 6))

    # Equipment comparison
    story.append(Paragraph("Your Equipment", s["h2"]))
    ex, new = visit.existing, visit.proposed
    eq = Table(
        [["", "Today", "Proposed"],
         ["Equipment", f"{ex.make} {ex.model}", f"{new.make} {new.model} (x{new.quantity})"],
         ["Efficiency", f"{ex.afue_pct:.0f}% AFUE", f"{new.afue_pct:.0f}% AFUE"],
         ["Age", f"{ex.age_years} years", "New, full warranty"]],
        colWidths=[content_w * 0.18, content_w * 0.41, content_w * 0.41],
    )
    eq.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("BACKGROUND", (0, 0), (-1, 0), PAPER),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [eq, Spacer(1, 4)]

    # Savings story
    story.append(Paragraph("What It Saves Every Year", s["h2"]))
    story.append(Paragraph(
        f"Annual heating cost today: <b>{_money(calc.annual_fuel_cost_cad)}</b> "
        f"({calc.annual_gas_use_m3:,.0f} m³) &nbsp;→&nbsp; after upgrade: "
        f"<b>{_money(calc.new_annual_fuel_cost_cad)}</b>", s["body"]))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        f"{_money(calc.annual_savings_cad)} saved per year "
        f"({calc.annual_gas_saved_m3:,.0f} m³ less natural gas)", s["big_number"]))
    story.append(Spacer(1, 2))

    # Incentives
    story.append(Paragraph("Incentive Programs Applied", s["h2"]))
    badge_style = ParagraphStyle("badge", fontName="Helvetica-Bold", fontSize=7, leading=9)
    rows = [["Program", "Status", "Amount"]]
    row_styles = []
    for i, line in enumerate(calc.incentives, start=1):
        label, colour = STATUS_BADGES[line.status]
        amount = _money(line.amount_cad)
        if line.status == "financing":
            amount = f"{_money(line.loan_principal_cad)} @ {line.loan_rate_pct:.1f}%"
        rows.append([
            Paragraph(f"<b>{line.program_name}</b><br/>"
                      f"<font size=7 color='#6B7280'>{line.basis_note}</font>", s["body"]),
            Paragraph(label, ParagraphStyle("b2", parent=badge_style, textColor=colour)),
            amount,
        ])
        row_styles.append(("VALIGN", (0, i), (-1, i), "MIDDLE"))
    inc = Table(rows, colWidths=[content_w * 0.58, content_w * 0.24, content_w * 0.18])
    inc.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("BACKGROUND", (0, 0), (-1, 0), PAPER),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        *row_styles,
    ]))
    story += [inc, Spacer(1, 8)]

    # The bottom line
    story.append(Paragraph("The Bottom Line", s["h2"]))
    payback = f"{calc.payback_years:.1f} years" if calc.payback_years else "—"
    bottom = Table(
        [["Installed price (quoted)", _money(visit.quoted_price_cad)],
         ["Incentives — confirmed", f"− {_money(calc.rebate_total_confirmed_cad)}"],
         ["Incentives — estimated, pending approval", f"− {_money(calc.rebate_total_estimated_cad)}"],
         ["Net investment", _money(calc.net_cost_cad)],
         ["Annual energy savings", _money(calc.annual_savings_cad)],
         ["Payback period", payback]],
        colWidths=[content_w * 0.70, content_w * 0.30],
    )
    bottom.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ("LINEABOVE", (0, 3), (-1, 3), 1, brand),
        ("BACKGROUND", (0, 3), (-1, 3), PAPER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [bottom, Spacer(1, 10)]

    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "All savings figures are computed deterministically from your billed consumption and the "
        "rated efficiencies shown, using published incentive program structures. Amounts marked "
        "ESTIMATED are subject to program approval and are not guaranteed. Financing lines show loan "
        "terms, not rebates. Prepared with RebateIQ.", s["small"]))

    doc.build(story)
    return out_path
