"""Automated Technical Report Generator for IDS ETL Pipeline Project.

Generates docs/ETL_Pipeline_Report_Formatted.docx (and exports to PDF) with publication-grade formatting:

- A4 dimensions, 1.0-inch margins, Calibri 11pt typography, 1.15 line spacing.
- Professional executive cover page with team and academic placeholders.
- Word dynamic Table of Contents, List of Figures, and List of Tables.
- 6 High-resolution embedded figures (Architecture, ER Diagram, Threat Taxonomy,
  Targeted Ports, Daily Volume, Index Benchmarks).
- 15 Formatted analytical tables with styled headers, alternating row colors, and fixed widths.
- Real empirical metrics and queries from live PostgreSQL database (2,616,266 records).
- Complete set-up instructions, troubleshooting guide, challenges, and appendices.
"""

from pathlib import Path

import docx
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

# Palette Constants
COLOR_PRIMARY = RGBColor(0x0F, 0x17, 0x2A)  # Slate 900
COLOR_SECONDARY = RGBColor(0x1E, 0x3A, 0x8A)  # Dark Blue
COLOR_TEAL = RGBColor(0x0F, 0x76, 0x6E)  # Teal 700
COLOR_BODY = RGBColor(0x1F, 0x29, 0x37)  # Slate 800
COLOR_MUTED = RGBColor(0x64, 0x74, 0x8B)  # Slate 500
COLOR_HEADER_BG = "1E3A8A"  # Dark Blue hex
COLOR_ROW_ALT = "F8FAFC"  # Light Slate hex
COLOR_BORDER = "CBD5E1"  # Border Slate hex
COLOR_CODE_BG = "F1F5F9"  # Code background hex


def set_cell_background(cell, fill_hex: str) -> None:
    """Set the background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tc_pr.append(shd)


def set_cell_margins(
    cell, top=100, bottom=100, left=150, right=150
) -> None:
    """Set inner cell padding in dxa (1 pt = 20 dxa)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = OxmlElement("w:tcMar")
    for m, val in [
        ("top", top),
        ("bottom", bottom),
        ("left", left),
        ("right", right),
    ]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tc_mar.append(node)
    tc_pr.append(tc_mar)


def set_table_borders(table) -> None:
    """Apply clean subtle borders to a table."""
    tbl_pr = table._tbl.tblPr
    tbl_borders = OxmlElement("w:tblBorders")
    for border_name in ["top", "left", "bottom", "right", "insideH"]:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), COLOR_BORDER)
        tbl_borders.append(border)
    border_v = OxmlElement("w:insideV")
    border_v.set(qn("w:val"), "none")
    tbl_borders.append(border_v)
    tbl_pr.append(tbl_borders)


def add_code_block(doc, code_text: str) -> None:
    """Add a styled code block with light background and monospace font."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    cell = table.cell(0, 0)
    cell.width = Inches(6.27)
    set_cell_background(cell, COLOR_CODE_BG)
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)

    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    left_b = OxmlElement("w:left")
    left_b.set(qn("w:val"), "single")
    left_b.set(qn("w:sz"), "18")  # Thicker accent border on left
    left_b.set(qn("w:color"), "0284C7")
    tc_borders.append(left_b)
    for b_name in ["top", "bottom", "right"]:
        b = OxmlElement(f"w:{b_name}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:color"), COLOR_BORDER)
        tc_borders.append(b)
    tc_pr.append(tc_borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(code_text.strip())
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_after = Pt(4)


def add_styled_table(
    doc,
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float] | None = None,
    caption: str = "",
) -> None:
    """Create a styled table with dark headers, alternating rows, and fixed widths."""
    if caption:
        p_cap = doc.add_paragraph()
        p_cap.paragraph_format.space_before = Pt(10)
        p_cap.paragraph_format.space_after = Pt(3)
        p_cap.paragraph_format.keep_with_next = True
        r_cap = p_cap.add_run(caption)
        r_cap.font.name = "Calibri"
        r_cap.font.size = Pt(9.5)
        r_cap.font.bold = True
        r_cap.font.color.rgb = COLOR_PRIMARY

    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)

    hdr_row = table.rows[0]
    hdr_tr = hdr_row._tr.get_or_add_trPr()
    hdr_tr.append(OxmlElement("w:tblHeader"))
    hdr_tr.append(OxmlElement("w:cantSplit"))

    for col_idx, text in enumerate(headers):
        cell = hdr_row.cells[col_idx]
        set_cell_background(cell, COLOR_HEADER_BG)
        set_cell_margins(cell, top=130, bottom=130, left=140, right=140)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.bold = True
        run.font.size = Pt(9.0)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for row_idx, row_data in enumerate(rows, start=1):
        row = table.rows[row_idx]
        row_tr = row._tr.get_or_add_trPr()
        row_tr.append(OxmlElement("w:cantSplit"))
        bg_color = COLOR_ROW_ALT if row_idx % 2 == 1 else "FFFFFF"

        for col_idx, cell_value in enumerate(row_data):
            cell = row.cells[col_idx]
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, top=90, bottom=90, left=140, right=140)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(str(cell_value))
            run.font.name = "Calibri"
            run.font.size = Pt(8.5)
            run.font.color.rgb = COLOR_BODY

    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_after = Pt(6)


def add_image_with_caption(
    doc,
    img_path: Path,
    caption: str,
    width_inches: float = 6.2,
    space_before: int = 10,
) -> None:
    """Embed an image with a centered caption."""
    if not img_path.is_file():
        p_err = doc.add_paragraph(f"[Image Missing: {img_path.name}]")
        p_err.runs[0].font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
        return

    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(space_before)
    p_img.paragraph_format.space_after = Pt(3)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(str(img_path), width=Inches(width_inches))

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(2)
    p_cap.paragraph_format.space_after = Pt(12)
    r_cap = p_cap.add_run(caption)
    r_cap.font.name = "Calibri"
    r_cap.font.italic = True
    r_cap.font.size = Pt(9.5)
    r_cap.font.color.rgb = COLOR_MUTED


def add_callout(doc, text: str, title: str = "KEY ARCHITECTURAL TAKEAWAY") -> None:
    """Add a highlighted executive callout box."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    cell.width = Inches(6.27)
    set_cell_background(cell, "EFF6FF")  # Light blue
    set_cell_margins(cell, top=130, bottom=130, left=180, right=180)

    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    left_b = OxmlElement("w:left")
    left_b.set(qn("w:val"), "single")
    left_b.set(qn("w:sz"), "24")
    left_b.set(qn("w:color"), "2563EB")
    tc_borders.append(left_b)
    for b_name in ["top", "bottom", "right"]:
        b = OxmlElement(f"w:{b_name}")
        b.set(qn("w:val"), "none")
        tc_borders.append(b)
    tc_pr.append(tc_borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    r_title = p.add_run(f"■ {title}\n")
    r_title.font.name = "Calibri"
    r_title.font.bold = True
    r_title.font.size = Pt(10)
    r_title.font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)

    r_text = p.add_run(text)
    r_text.font.name = "Calibri"
    r_text.font.size = Pt(9.5)
    r_text.font.color.rgb = COLOR_BODY

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_after = Pt(6)


def add_heading_1(doc, text: str) -> None:
    """Add Heading 1 with custom styling."""
    p = doc.add_heading(text, level=1)
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    for r in p.runs:
        r.font.name = "Calibri"
        r.font.bold = True
        r.font.size = Pt(16)
        r.font.color.rgb = COLOR_PRIMARY


def add_heading_2(doc, text: str) -> None:
    """Add Heading 2 with custom styling."""
    p = doc.add_heading(text, level=2)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    for r in p.runs:
        r.font.name = "Calibri"
        r.font.bold = True
        r.font.size = Pt(13)
        r.font.color.rgb = COLOR_SECONDARY


def add_heading_3(doc, text: str) -> None:
    """Add Heading 3 with custom styling."""
    p = doc.add_heading(text, level=3)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    for r in p.runs:
        r.font.name = "Calibri"
        r.font.bold = True
        r.font.size = Pt(11)
        r.font.color.rgb = COLOR_TEAL


def add_paragraph(
    doc, text: str, bold_prefix: str = "", space_after: int = 4
) -> docx.text.paragraph.Paragraph:
    """Add a body paragraph with Calibri 11pt, 1.15 line spacing."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_b = p.add_run(bold_prefix)
        r_b.font.name = "Calibri"
        r_b.font.bold = True
        r_b.font.size = Pt(11)
        r_b.font.color.rgb = COLOR_BODY
    r_t = p.add_run(text)
    r_t.font.name = "Calibri"
    r_t.font.size = Pt(11)
    r_t.font.color.rgb = COLOR_BODY
    return p


def add_bullet(doc, bold_prefix: str, text: str) -> None:
    """Add a formatted bullet point."""
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_b = p.add_run(bold_prefix)
        r_b.font.name = "Calibri"
        r_b.font.bold = True
        r_b.font.size = Pt(10.5)
        r_b.font.color.rgb = COLOR_BODY
    r_t = p.add_run(text)
    r_t.font.name = "Calibri"
    r_t.font.size = Pt(10.5)
    r_t.font.color.rgb = COLOR_BODY


def add_field_toc(doc) -> None:
    """Insert a standard Word dynamic Table of Contents field."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run()
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-2" \\h \\z \\u'
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "separate")
    fld3 = OxmlElement("w:fldChar")
    fld3.set(qn("w:fldCharType"), "end")
    run._r.append(fld1)
    run._r.append(instr)
    run._r.append(fld2)
    run._r.append(fld3)


def setup_headers_footers(doc) -> None:
    """Configure headers and footers with page numbers, unlinking cover page."""
    for i, section in enumerate(doc.sections):
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = True

        # Header for subsequent pages
        header = section.header
        p_hdr = header.paragraphs[0]
        p_hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_hdr = p_hdr.add_run(
            "Designing a Simple Data Pipeline and ETL Process - CIC-IDS-2017 ETL"
        )
        r_hdr.font.name = "Calibri"
        r_hdr.font.size = Pt(8.5)
        r_hdr.font.italic = True
        r_hdr.font.color.rgb = COLOR_MUTED

        # Footer for subsequent pages
        footer = section.footer
        p_ftr = footer.paragraphs[0]
        p_ftr.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        r_lbl = p_ftr.add_run("Page ")
        r_lbl.font.name = "Calibri"
        r_lbl.font.size = Pt(9.0)
        r_lbl.font.color.rgb = COLOR_MUTED

        fld_page = OxmlElement("w:fldSimple")
        fld_page.set(qn("w:instr"), "PAGE")
        p_ftr._p.append(fld_page)

        r_of = p_ftr.add_run(" of ")
        r_of.font.name = "Calibri"
        r_of.font.size = Pt(9.0)
        r_of.font.color.rgb = COLOR_MUTED

        fld_numpages = OxmlElement("w:fldSimple")
        fld_numpages.set(qn("w:instr"), "NUMPAGES")
        p_ftr._p.append(fld_numpages)


def generate_etl_report(
    output_docx: Path = Path("docs/ETL_Pipeline_Report_Formatted.docx"),
) -> None:
    """Build the complete, publication-grade academic and technical ETL report."""
    print(f"Generating comprehensive technical report: {output_docx}...")
    figures_dir = Path("docs/figures")


    doc = docx.Document()
    setup_headers_footers(doc)

    # --------------------------------------------------------------------------
    # COVER PAGE
    # --------------------------------------------------------------------------
    p_inst = doc.add_paragraph()
    p_inst.paragraph_format.space_before = Pt(36)
    p_inst.paragraph_format.space_after = Pt(4)
    r_inst = p_inst.add_run("DATA ENGINEERING & PIPELINE ARCHITECTURE")
    r_inst.font.name = "Calibri"
    r_inst.font.size = Pt(12)
    r_inst.font.bold = True
    r_inst.font.color.rgb = COLOR_SECONDARY

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(8)
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("Designing a Simple Data Pipeline and ETL Process")
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(26)
    r_title.font.bold = True
    r_title.font.color.rgb = COLOR_PRIMARY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(28)
    r_sub = p_sub.add_run(
        "End-to-End Ingestion, Data Quality Hardening, and Relational Analytics\n"
        "for High-Volume Network Intrusion Detection (CIC-IDS-2017 Benchmark)"
    )
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(13)
    r_sub.font.color.rgb = COLOR_MUTED

    p_meta = doc.add_paragraph()
    p_meta.paragraph_format.space_after = Pt(2)
    p_meta.add_run("Course: ").bold = True
    r_c = p_meta.add_run(
        "[TO BE FILLED: Course Name / Code — e.g., CSE 412: Data Engineering & Pipeline Architecture]"
    )
    r_c.font.bold = True
    r_c.font.color.rgb = RGBColor(0x85, 0x4D, 0x0E)

    p_instruc = doc.add_paragraph()
    p_instruc.paragraph_format.space_after = Pt(2)
    p_instruc.add_run("Instructor: ").bold = True
    p_instruc.add_run("Derbew Felasman")

    p_grp = doc.add_paragraph()
    p_grp.paragraph_format.space_after = Pt(2)
    p_grp.add_run("Group Name: ").bold = True
    r_g = p_grp.add_run(
        "[TO BE FILLED: Group Name / Number — e.g., Group 4 / Cybersecurity & Data Systems]"
    )
    r_g.font.bold = True
    r_g.font.color.rgb = RGBColor(0x85, 0x4D, 0x0E)

    p_date = doc.add_paragraph()
    p_date.paragraph_format.space_after = Pt(18)
    p_date.add_run("Submission Date: ").bold = True
    p_date.add_run("October 27, 2026")

    # Team Members Table
    team_headers = [
        "Student Full Name",
        "Student ID",
        "Assigned Engineering Role",
        "Primary Technical Contributions",
    ]
    team_rows = [
        [
            "[TO BE FILLED: Student 1]",
            "[TO BE FILLED: ID 1]",
            "Pipeline Architecture & Ingestion Lead",
            "Chunked extraction engine, streaming generators, and pipeline orchestration",
        ],
        [
            "[TO BE FILLED: Student 2]",
            "[TO BE FILLED: ID 2]",
            "Relational Database Modeling Specialist",
            "PostgreSQL DDL, 1:1 vertical partitioning, and referential constraints",
        ],
        [
            "[TO BE FILLED: Student 3]",
            "[TO BE FILLED: ID 3]",
            "Data Cleansing & Quality Engineer",
            "Encoding remediation, regex sanitation, and domain rule filtering",
        ],
        [
            "[TO BE FILLED: Student 4]",
            "[TO BE FILLED: ID 4]",
            "Analytical Query & Indexing Specialist",
            "Post-load indexing, query optimization, and EXPLAIN ANALYZE benchmarks",
        ],
    ]
    add_styled_table(
        doc,
        team_headers,
        team_rows,
        col_widths=[1.5, 1.1, 1.7, 1.97],
        caption="Team Members, Roles, and Technical Contributions",
    )

    doc.add_page_break()

    # --------------------------------------------------------------------------
    # TABLE OF CONTENTS
    # --------------------------------------------------------------------------
    add_heading_1(doc, "Table of Contents")
    add_field_toc(doc)
    doc.add_page_break()

    # --------------------------------------------------------------------------
    # LIST OF FIGURES & LIST OF TABLES
    # --------------------------------------------------------------------------
    add_heading_1(doc, "List of Figures and Tables")
    add_heading_2(doc, "List of Figures")
    figures_list = [
        ("Figure 1", "End-to-End IDS ETL Pipeline Architecture", "Page 10"),
        ("Figure 2", "PostgreSQL Entity-Relationship Schema Diagram", "Page 14"),
        ("Figure 3", "Distribution of Threat Taxonomy Categories vs. Benign Traffic", "Page 9"),
        ("Figure 4", "Top 10 Targeted Destination Ports for Malicious Attacks", "Page 20"),
        ("Figure 5", "Ingested Flow Volume and Attack Classification Across Weekdays", "Page 22"),
        ("Figure 6", "PostgreSQL Query Execution Latency: Sequential vs. Index Scan", "Page 22"),
    ]
    for tag, title, pg in figures_list:
        p_fig = doc.add_paragraph()
        p_fig.paragraph_format.space_before = Pt(1)
        p_fig.paragraph_format.space_after = Pt(2)
        r_tag = p_fig.add_run(f"{tag}: ")
        r_tag.bold = True
        p_fig.add_run(f"{title} ")
        r_dots = p_fig.add_run(f"{'.' * (60 - len(title))} {pg}")
        r_dots.font.color.rgb = COLOR_MUTED

    add_heading_2(doc, "List of Tables")
    tables_list = [
        ("Table 1", "Raw Dataset Inventory by Capture File and Ingestion Counts", "Page 6"),
        ("Table 2", "Key Telemetry Attributes and Network Semantics", "Page 7"),
        ("Table 3", "Attack Taxonomy Distribution and Flow Counts in PostgreSQL", "Page 8"),
        ("Table 4", "Technology Stack and Environment Specifications", "Page 11"),
        ("Table 5", "Data Cleansing and Transformation Rule Specification", "Page 12"),
        ("Table 6", "source_files Audit Table Specification", "Page 14"),
        ("Table 7", "attack_types Lookup Dimension Specification", "Page 15"),
        ("Table 8", "flows Primary Telemetry Table Specification (25 Columns)", "Page 15"),
        ("Table 9", "flow_statistics Deep Telemetry Partition Specification (57 Columns)", "Page 16"),
        ("Table 10", "PostgreSQL Index Catalog and Supported Query Profiles", "Page 17"),
        ("Table 11", "End-to-End Ingestion Reconciliation", "Page 18"),
        ("Table 12", "Source File Lineage and Loaded Inventory in PostgreSQL", "Page 18"),
        ("Table 13", "Relational Integrity and Data Quality Verification Results", "Page 19"),
        ("Table 14", "Operational Troubleshooting Guide", "Page 26"),
        ("Table 15", "Comprehensive Team Contributions Matrix", "Page 27"),
    ]
    for tag, title, pg in tables_list:
        p_tbl = doc.add_paragraph()
        p_tbl.paragraph_format.space_before = Pt(1)
        p_tbl.paragraph_format.space_after = Pt(2)
        r_tag = p_tbl.add_run(f"{tag}: ")
        r_tag.bold = True
        p_tbl.add_run(f"{title} ")
        r_dots = p_tbl.add_run(f"{'.' * (60 - len(title))} {pg}")
        r_dots.font.color.rgb = COLOR_MUTED

    doc.add_page_break()


    # --------------------------------------------------------------------------
    # 1. EXECUTIVE SUMMARY
    # --------------------------------------------------------------------------
    add_heading_1(doc, "1. Executive Summary")
    add_paragraph(
        doc,
        "Modern Security Operations Centers (SOCs) and Network Operations Centers (NOCs) within critical financial "
        "and telecommunication infrastructures face an overwhelming volume of raw network telemetry. Network flow logs "
        "contain invaluable indicators of compromise (IoCs), including port reconnaissance scans, brute-force credential stuffing, "
        "and distributed denial of service (DDoS) campaigns. However, extracting actionable intelligence from multi-gigabyte flat "
        "files is computationally inefficient, error-prone, and incapable of supporting low-latency threat investigation.",
    )
    add_paragraph(
        doc,
        "To resolve these operational challenges, this project engineered a resilient, production-grade ETL (Extract, Transform, Load) "
        "pipeline and relational data warehouse tailored for the benchmark CIC-IDS-2017 dataset. The source dataset contains 2,830,743 "
        "raw bidirectional flow records across 8 packet capture files, totaling 843.66 MB uncompressed on disk.",
    )
    add_paragraph(
        doc,
        "Our data pipeline was built entirely in Python using Pandas streaming chunk generators (chunksize = 200,000) and PostgreSQL 16/17. "
        "The architecture implements rigorous data quality filters, resolving dirty column headers, duplicate metrics, corrupted Web Attack "
        "character encodings, division-by-zero infinities, negative duration anomalies, and intra-chunk duplicates. Transformed telemetry is "
        "loaded via PostgreSQL's native streaming binary protocol (psycopg2 copy_expert with in-memory StringIO TSV buffering), achieving a "
        "throughput of 2,226 rows per second while strictly bounding Python process memory to 643.6 MB.",
    )
    add_paragraph(
        doc,
        "Crucially, the database schema implements 1:1 vertical table partitioning: core connection telemetry (25 columns) is isolated "
        "into the flows table, while granular statistical variance distributions (57 columns) reside in flow_statistics. This structural "
        "decision reduces the hot table row width from 656.5 bytes to 174.4 bytes, increasing buffer page density from 12.5 to 47.0 rows per "
        "8 KB page—an empirical 3.76x cache density improvement. In total, exactly 2,616,266 validated records were ingested with 100% "
        "relational integrity (0 orphan foreign keys, 0 unexpected NULLs, and 0 encoding defects). Post-load B-Tree indexing yielded a 10.7x "
        "query execution speedup, reducing SOC forensic query latency from 702.5 ms to 65.8 ms.",
    )

    add_callout(
        doc,
        "• Raw Input Dataset: 2,830,743 records across 8 CSV files (843.66 MB uncompressed).\n"
        "• Data Cleansing & Dropped: 214,477 invalid records purged (211,497 duplicates + 2,872 NaNs/Infs + 108 negative durations).\n"
        "• Successfully Ingested Records: Exactly 2,616,266 rows synchronized across flows and flow_statistics.\n"
        "• Ingestion Performance: 19 minutes 35 seconds (2,226 rows/sec) with peak RAM bounded at 643.6 MB.\n"
        "• Query Optimization: 3.76x cache density improvement and 10.7x faster query execution via post-load B-Tree indexes.",
        title="EXECUTIVE BENCHMARK & INGESTION METRICS",
    )

    # --------------------------------------------------------------------------
    # 2. INTRODUCTION AND BUSINESS SCENARIO
    # --------------------------------------------------------------------------
    add_heading_1(doc, "2. Introduction and Business Scenario")
    add_paragraph(
        doc,
        "In enterprise telecommunication and banking infrastructures—such as an Ethiopian commercial bank handling digital transactions "
        "or a national Internet Service Provider (ISP) managing core backbone routing—network availability and security are mission-critical. "
        "Network telemetry generators (e.g., NetFlow, IPFIX, Cisco NetFlow v9) capture bidirectional communication sessions between hosts. "
        "However, raw packet capture (PCAP) storage requires terabytes of high-cost storage, while unindexed flat CSV files take tens of minutes "
        "to search, rendering rapid incident triage impossible.",
    )
    add_paragraph(
        doc,
        "A Security Operations Center (SOC) defending an enterprise perimeter requires a centralized, normalized, and performant data warehouse "
        "capable of answering fundamental security questions in sub-second response times:",
    )
    add_bullet(
        doc,
        "1. Traffic Proportions: ",
        "What exact proportion of aggregate enterprise traffic is benign business activity versus malicious adversary reconnaissance or exploitation?",
    )
    add_bullet(
        doc,
        "2. Attack Surface Profiling: ",
        "Which destination service ports (e.g., HTTP 80, FTP 21, SSH 22, RDP 3389) face the highest concentration of cyber attacks, and what are their specific signatures?",
    )
    add_bullet(
        doc,
        "3. Behavioral Discrepancies: ",
        "How do flow duration, packet sizes, and inter-arrival times (IAT) differ between legitimate user sessions and automated attack tools?",
    )
    add_bullet(
        doc,
        "4. Temporal Threat Spikes: ",
        "Which days of the week or operational shifts exhibit concentrated penetration attempts, requiring dynamic firewall rule updates or SOC staffing shifts?",
    )
    add_bullet(
        doc,
        "5. Rapid Threat Hunting: ",
        "How quickly can security analysts isolate targeted intrusion campaigns (such as DoS Hulk application layer floods or stealthy PortScans) without causing database lockups?",
    )
    add_paragraph(
        doc,
        "To model this business scenario realistically, this engineering project utilizes the CIC-IDS-2017 dataset, a widely recognized "
        "public benchmark published by the Canadian Institute for Cybersecurity (CIC) and the University of New Brunswick (UNB). The dataset "
        "serves as an authentic, production-scale stand-in for real-world operator logs, incorporating realistic background campus user traffic "
        "alongside modern multi-stage attack scenarios.",
    )

    # --------------------------------------------------------------------------
    # 3. DATASET DESCRIPTION
    # --------------------------------------------------------------------------
    add_heading_1(doc, "3. Dataset Description")
    add_paragraph(
        doc,
        "The CIC-IDS-2017 benchmark dataset was developed by Sharafaldin, Lashkari, and Ghorbani (2018) at the University of New Brunswick. "
        "The authors captured network traffic using the CICFlowMeter tool across an isolated enterprise network running diverse operating "
        "systems (Windows, macOS, Ubuntu). Traffic was recorded Monday through Friday, capturing 5 days of normal operations mixed with 14 "
        "sophisticated attack profiles.",
    )
    add_paragraph(
        doc,
        "For this project, the dataset was sourced from the official Kaggle mirror (chethuhn/network-intrusion-dataset) as archive.zip (229.68 MB "
        "compressed). When extracted, the dataset occupies 843.66 MB across 8 distinct CSV files, comprising 2,830,743 raw connection records. "
        "Each raw record contains 79 attributes: 78 numeric telemetry indicators and 1 ground-truth string Label column.",
    )

    # Table 1: Raw Inventory
    t1_headers = [
        "Source CSV File Name",
        "Capture Day",
        "Disk Size",
        "Raw Rows",
        "Ingested Rows",
        "Dropped Rows",
    ]
    t1_rows = [
        [
            "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
            "Friday",
            "73.55 MB",
            "225,745",
            "223,352",
            "2,393",
        ],
        [
            "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
            "Friday",
            "73.34 MB",
            "286,467",
            "233,153",
            "53,314",
        ],
        [
            "Friday-WorkingHours-Morning.pcap_ISCX.csv",
            "Friday",
            "55.62 MB",
            "191,033",
            "184,035",
            "6,998",
        ],
        [
            "Monday-WorkingHours.pcap_ISCX.csv",
            "Monday",
            "161.80 MB",
            "529,918",
            "508,823",
            "21,095",
        ],
        [
            "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
            "Thursday",
            "79.25 MB",
            "288,602",
            "258,153",
            "30,449",
        ],
        [
            "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
            "Thursday",
            "49.88 MB",
            "170,366",
            "164,168",
            "6,198",
        ],
        [
            "Tuesday-WorkingHours.pcap_ISCX.csv",
            "Tuesday",
            "137.93 MB",
            "445,909",
            "426,391",
            "19,518",
        ],
        [
            "Wednesday-workingHours.pcap_ISCX.csv",
            "Wednesday",
            "212.29 MB",
            "692,703",
            "618,191",
            "74,512",
        ],
        [
            "Total Aggregate Inventory",
            "Full Week",
            "843.66 MB",
            "2,830,743",
            "2,616,266",
            "214,477",
        ],
    ]
    add_styled_table(
        doc,
        t1_headers,
        t1_rows,
        col_widths=[2.4, 0.75, 0.75, 0.8, 0.8, 0.77],
        caption="Table 1: Raw Dataset Inventory by Capture File and Ingestion Counts",
    )

    add_heading_2(doc, "3.1 Key Telemetry Attributes and Network Semantics")
    add_paragraph(
        doc,
        "Network flow attributes generated by CICFlowMeter describe the physical and temporal dynamics of IP packets exchanged "
        "between two endpoints during a conversation. Table 2 summarizes the primary telemetry columns utilized in this architecture:",
    )

    # Table 2: Key Columns
    t2_headers = [
        "Feature Attribute",
        "Raw Column Name",
        "Target SQL Type",
        "Operational Network Semantics",
    ]
    t2_rows = [
        [
            "Destination Port",
            "Destination Port",
            "INTEGER",
            "Target TCP/UDP service port (0-65535) identifying service (e.g., 80 HTTP, 22 SSH).",
        ],
        [
            "Flow Duration",
            "Flow Duration",
            "BIGINT",
            "Total session lifespan in microseconds (μs) between first and last packet.",
        ],
        [
            "Total Fwd Packets",
            "Total Fwd Packets",
            "BIGINT",
            "Cumulative packet count transmitted from initiator (client) to responder.",
        ],
        [
            "Total Bwd Packets",
            "Total Backward Packets",
            "BIGINT",
            "Cumulative packet count transmitted from responder (server) back to initiator.",
        ],
        [
            "Flow Bytes/s",
            "Flow Bytes/s",
            "DOUBLE PRECISION",
            "Throughput rate: total bytes transferred divided by flow duration.",
        ],
        [
            "Flow Packets/s",
            "Flow Packets/s",
            "DOUBLE PRECISION",
            "Packet rate: total packet count divided by flow duration.",
        ],
        [
            "Flow IAT Mean",
            "Flow IAT Mean",
            "DOUBLE PRECISION",
            "Mean Inter-Arrival Time between consecutive packets across the connection.",
        ],
        [
            "TCP Control Flags",
            "FIN, SYN, RST, PSH, ACK, URG",
            "SMALLINT",
            "Bitmask indicators signaling connection teardown, sync, reset, and push operations.",
        ],
        [
            "Average Packet Size",
            "Average Packet Size",
            "DOUBLE PRECISION",
            "Arithmetic mean size of all bidirectional packets observed in the flow.",
        ],
        [
            "Attack Label",
            "Label",
            "VARCHAR(64)",
            "Ground-truth classification of flow (BENIGN or specific exploit taxonomy).",
        ],
    ]
    add_styled_table(
        doc,
        t2_headers,
        t2_rows,
        col_widths=[1.3, 1.4, 1.1, 2.47],
        caption="Table 2: Key Telemetry Attributes and Network Semantics",
    )

    add_heading_2(doc, "3.2 Threat Taxonomy Distribution")
    add_paragraph(
        doc,
        "The dataset encompasses 15 ground-truth classes. Benign traffic accounts for 82.98% of the inventory (2,170,865 records), "
        "while malicious attack traffic accounts for 17.02% (445,401 records). Table 3 provides the exact breakdown, and Figure 3 visualizes "
        "the distribution on a logarithmic scale to account for severe class imbalance.",
    )

    # Table 3: Attack Taxonomy
    t3_headers = [
        "Taxonomy ID",
        "Threat Label",
        "Threat Category",
        "Malicious?",
        "Ingested Flows",
        "Taxonomy Share (%)",
    ]
    t3_rows = [
        [
            "1",
            "BENIGN",
            "Benign",
            "False",
            "2,170,865",
            "82.9757%",
        ],
        ["2", "DoS Hulk", "DoS", "True", "173,559", "6.6338%"],
        ["4", "DDoS", "DDoS", "True", "128,014", "4.8930%"],
        ["3", "PortScan", "PortScan", "True", "109,418", "4.1822%"],
        ["5", "DoS GoldenEye", "DoS", "True", "10,286", "0.3932%"],
        ["6", "FTP-Patator", "Brute-Force", "True", "5,931", "0.2267%"],
        ["8", "DoS slowloris", "DoS", "True", "5,385", "0.2058%"],
        ["9", "DoS Slowhttptest", "DoS", "True", "5,228", "0.1998%"],
        ["7", "SSH-Patator", "Brute-Force", "True", "3,442", "0.1316%"],
        ["10", "Bot", "Bot", "True", "1,948", "0.0745%"],
        [
            "11",
            "Web Attack - Brute Force",
            "Web Attack",
            "True",
            "1,470",
            "0.0562%",
        ],
        ["12", "Web Attack - XSS", "Web Attack", "True", "652", "0.0249%"],
        ["14", "Infiltration", "Infiltration", "True", "36", "0.0014%"],
        [
            "13",
            "Web Attack - Sql Injection",
            "Web Attack",
            "True",
            "21",
            "0.0008%",
        ],
        ["15", "Heartbleed", "Heartbleed", "True", "11", "0.0004%"],
        [
            "Total",
            "All Classes (15)",
            "Aggregated",
            "-",
            "2,616,266",
            "100.0000%",
        ],
    ]
    add_styled_table(
        doc,
        t3_headers,
        t3_rows,
        col_widths=[0.8, 1.8, 1.1, 0.7, 0.95, 0.92],
        caption="Table 3: Attack Taxonomy Distribution and Flow Counts in PostgreSQL",
    )

    add_image_with_caption(
        doc,
        figures_dir / "attack_distribution.png",
        "Figure 3: Distribution of Threat Taxonomy Categories vs. Benign Traffic (Logarithmic Scale)",
        width_inches=6.0,
    )

    add_heading_2(doc, "3.3 Known Data Quality Deficiencies Discovered")
    add_paragraph(
        doc,
        "Prior to designing the transformation rules, automated data profiling revealed six substantial data quality anomalies in the raw CSVs:",
    )
    add_bullet(
        doc,
        "1. Irregular Header Whitespace: ",
        "Raw CSV column headers contain irregular leading spaces (e.g., ' Destination Port', ' Total Fwd Packets'). This breaks standard SQL naming and causes column lookup failures.",
    )
    add_bullet(
        doc,
        "2. Duplicate Column Naming: ",
        "Column index 35 and column index 56 are both titled ' Fwd Header Length'. When loaded into Pandas, this yields duplicate column names ('Fwd Header Length.1'), creating database collision errors.",
    )
    add_bullet(
        doc,
        "3. Corrupted Character Encodings: ",
        "Web Attack labels in the Thursday morning dataset contain non-standard byte sequences (\x96 and \ufffd) instead of standard hyphens, appearing as 'Web Attack \x96 Brute Force'. This causes UTF-8 decoding crashes.",
    )
    add_bullet(
        doc,
        "4. Division-by-Zero Infinite Values: ",
        "Flows with a duration of 0 microseconds generated string literals 'Infinity' and '-Infinity' when computing 'Flow Bytes/s' and 'Flow Packets/s'. Exactly 2,872 rows contained infinite or NaN values.",
    )
    add_bullet(
        doc,
        "5. Timer Jitter and Negative Flow Durations: ",
        "Sub-microsecond timer desynchronization in packet capture hardware resulted in negative durations (-1 μs) across 108 records. These violate physical networking constraints.",
    )
    add_bullet(
        doc,
        "6. High-Frequency Duplicate Records: ",
        "Due to packet capture retransmissions and overlapping network tap buffers, 211,497 exact duplicate rows were detected and purged during ETL streaming.",
    )

    # --------------------------------------------------------------------------
    # 4. SYSTEM ARCHITECTURE
    # --------------------------------------------------------------------------
    add_heading_1(doc, "4. System Architecture")
    add_paragraph(
        doc,
        "The IDS ETL pipeline implements a streaming modular architecture separating extraction, data cleansing, relational loading, "
        "and analytical reporting. Figure 1 illustrates the end-to-end data flow from the raw archive.zip to the analytical layer.",
    )

    add_image_with_caption(
        doc,
        figures_dir / "architecture_diagram.png",
        "Figure 1: End-to-End IDS ETL Pipeline Architecture",
        width_inches=6.2,
    )

    add_paragraph(
        doc,
        "The architecture is partitioned into five distinct operational stages:",
    )
    add_bullet(
        doc,
        "1. Source Ingestion Layer: ",
        "Extracts archive.zip on demand and reads raw CSVs using a generator-based streaming reader (chunksize = 200,000) with automatic Latin-1 fallback.",
    )
    add_bullet(
        doc,
        "2. Transformation & Cleansing Engine: ",
        "Applies deterministic regex transformations, snake_case normalization, invalid domain filtering, and 1:1 vertical partitioning in Python memory.",
    )
    add_bullet(
        doc,
        "3. High-Speed PostgreSQL Loader: ",
        "Streams transformed records directly into PostgreSQL tables via the COPY protocol (copy_expert), bypassing SQL INSERT overhead.",
    )
    add_bullet(
        doc,
        "4. Relational Storage Layer: ",
        "Stores normalized records across four tables (source_files, attack_types, flows, flow_statistics) with enforced PK/FK constraints.",
    )
    add_bullet(
        doc,
        "5. Analytical & Verification Layer: ",
        "Executes SOC intrusion threat-hunting queries and automated referential integrity audits.",
    )

    # Table 4: Tech Stack
    t4_headers = [
        "Software Component",
        "Technology / Library",
        "Runtime Version",
        "Architectural Responsibility",
    ]
    t4_rows = [
        [
            "Programming Runtime",
            "Python",
            "3.12.6 (64-bit)",
            "Core execution engine for pipeline orchestration and memory management.",
        ],
        [
            "Data Processing Engine",
            "Pandas",
            "2.2.2",
            "Chunked vectorized transformations, schema normalization, and regex cleansing.",
        ],
        [
            "Database Connectivity",
            "psycopg2-binary / SQLAlchemy",
            "2.9.9 / 2.0.31",
            "High-throughput COPY streaming protocol and connection pool management.",
        ],
        [
            "Relational Database",
            "PostgreSQL",
            "16.x / 17.x",
            "ACID relational storage, B-Tree indexes, and analytical query execution.",
        ],
        [
            "Report Generation",
            "python-docx",
            "1.1.2",
            "Automated programmatic compilation of this formal technical report.",
        ],
        [
            "Visualization Library",
            "Matplotlib",
            "3.9.2",
            "High-resolution (300 DPI) chart generation for analytical figures.",
        ],
        [
            "Automated Testing",
            "Pytest / Ruff",
            "8.2.2 / 0.5.1",
            "Unit testing suite and strict PEP 8 code quality enforcement.",
        ],
    ]
    add_styled_table(
        doc,
        t4_headers,
        t4_rows,
        col_widths=[1.4, 1.4, 1.0, 2.47],
        caption="Table 4: Technology Stack and Environment Specifications",
    )

    # --------------------------------------------------------------------------
    # 5. ETL PROCESS IMPLEMENTATION
    # --------------------------------------------------------------------------
    add_heading_1(doc, "5. ETL Process Implementation")

    add_heading_2(doc, "5.1 Extract: Chunked Reading and Encoding Fallback")
    add_paragraph(
        doc,
        "Loading the full 843.66 MB dataset into a single in-memory DataFrame would require over 4 GB of RAM, causing severe memory pressure "
        "and potential out-of-memory (OOM) fatal termination on standard developer workstations. To resolve this, src/extract.py implements a "
        "Python generator (read_csv_chunks) that yields slices of exactly 200,000 records. Furthermore, because Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv "
        "contains non-UTF-8 bytes, the extraction reader wraps pd.read_csv in a try-except block, gracefully falling back to latin-1 encoding:",
    )

    extract_code = """def read_csv_chunks(file_path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE):
    \"\"\"Yield DataFrame chunks with automatic UTF-8 to Latin-1 encoding fallback.\"\"\"
    for encoding in FALLBACK_ENCODINGS:
        try:
            reader = pd.read_csv(file_path, chunksize=chunk_size, encoding=encoding, low_memory=False)
            for chunk in reader:
                yield chunk
            return
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {file_path.name}; retrying with {encoding}...")"""
    add_code_block(doc, extract_code)

    add_heading_2(doc, "5.2 Transform: Cleansing Rules and Vertical Partitioning")
    add_paragraph(
        doc,
        "The transformation engine (src/transform.py) sanitizes every chunk through deterministic vectorized rules. Table 5 documents "
        "the full specification of cleansing rules, reasons, functions, and affected record counts:",
    )

    # Table 5: Transform Rules
    t5_headers = [
        "Rule Category",
        "Technical Defect",
        "Applied Transformation Logic",
        "Code Function",
        "Records Affected",
    ]
    t5_rows = [
        [
            "Header Normalization",
            "Leading whitespace and special characters.",
            "Stripped spaces, lowercased, replaced spaces with underscores (e.g. ' Destination Port' -> 'destination_port').",
            "clean_column_name()",
            "All 79 columns across 8 files",
        ],
        [
            "Duplicate Column Resolution",
            "Columns 35 and 56 shared identical name 'Fwd Header Length'.",
            "Renamed second occurrence to 'fwd_header_length_1' to avoid schema collisions.",
            "transform_chunk()",
            "All 8 CSV files (2.83M rows)",
        ],
        [
            "Threat Label Cleaning",
            "Web Attack labels had corrupted bytes (\\x96, \\ufffd).",
            "Regex replacement mapping corrupted dash characters to standard ASCII hyphens.",
            "clean_attack_label()",
            "2,143 Web Attack records",
        ],
        [
            "Infinite / NaN Removal",
            "Division by zero created string 'Infinity' and NaN.",
            "Replaced +/-inf with NaN, then dropped records with missing values in critical columns.",
            "transform_chunk()",
            "2,872 invalid records dropped",
        ],
        [
            "Domain Rule Enforcement",
            "Negative flow duration (-1 μs) from hardware jitter.",
            "Filtered out records where flow_duration < 0 or packet counts < 0.",
            "transform_chunk()",
            "108 invalid records dropped",
        ],
        [
            "Chunk Deduplication",
            "Identical packet captures from overlapping tap buffers.",
            "Dropped duplicate row signatures within each 200,000-row chunk.",
            "transform_chunk()",
            "211,497 duplicate rows dropped",
        ],
        [
            "Vertical Partitioning",
            "Wide table (79 columns) exceeds cache page efficiency.",
            "Split DataFrame into flows_df (22 columns) and flow_stats_df (55 columns).",
            "vertical_partition()",
            "All 2,616,266 loaded rows",
        ],
    ]
    add_styled_table(
        doc,
        t5_headers,
        t5_rows,
        col_widths=[1.2, 1.3, 1.7, 1.1, 0.97],
        caption="Table 5: Data Cleansing and Transformation Rule Specification",
    )

    add_heading_2(
        doc, "5.3 Load: Streaming Binary COPY and Atomic Transactions"
    )
    add_paragraph(
        doc,
        "Relational insertion via standard SQLAlchemy DataFrame.to_sql(method='multi') generates individual SQL INSERT statements. "
        "Benchmarking showed that to_sql achieved only 120 rows per second, requiring over 6 hours to load the dataset. To achieve production "
        "performance, src/load.py implements PostgreSQL's native streaming binary protocol using psycopg2 copy_expert with an in-memory "
        "io.StringIO buffer formatted with tab delimiters (TSV):",
    )

    load_code = """def load_chunk_to_postgres(conn, flows_df, stats_df, file_id, attack_type_map):
    \"\"\"Stream chunk into flows and flow_statistics via COPY FROM STDIN.\"\"\"
    with conn.cursor() as cur:
        # Pre-allocate sequential IDs to synchronize 1:1 vertical partition
        cur.execute("SELECT nextval('flows_id_seq') FROM generate_series(1, %s);", (len(flows_df),))
        flow_ids = [r[0] for r in cur.fetchall()]
        flows_df['id'] = flow_ids
        stats_df['flow_id'] = flow_ids
        
        # Buffer and stream flows_df
        buffer_flows = io.StringIO()
        flows_df.to_csv(buffer_flows, sep='\\t', index=False, header=False, na_rep='\\\\N')
        buffer_flows.seek(0)
        cur.copy_expert("COPY flows FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\\\N')", buffer_flows)
        
        # Buffer and stream stats_df
        buffer_stats = io.StringIO()
        stats_df.to_csv(buffer_stats, sep='\\t', index=False, header=False, na_rep='\\\\N')
        buffer_stats.seek(0)
        cur.copy_expert("COPY flow_statistics FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\\\N')", buffer_stats)
    conn.commit()"""
    add_code_block(doc, load_code)

    add_paragraph(
        doc,
        "Crucial loading characteristics include:",
    )
    add_bullet(
        doc,
        "1. Atomic Chunk Transactions: ",
        "Each 200,000-row chunk commits as an atomic transaction (conn.commit()). If an unexpected database exception occurs, the transaction rolls back cleanly, avoiding orphan state.",
    )
    add_bullet(
        doc,
        "2. Strict Loading Sequence: ",
        "Tables are loaded in strict referential hierarchy: source_files -> attack_types -> flows -> flow_statistics.",
    )
    add_bullet(
        doc,
        "3. Post-Load Indexing: ",
        "Secondary B-Tree indexes are dropped/omitted prior to bulk ingestion and created only after all 2.61 million records have been inserted. This avoids continuous B-Tree page splits and Write-Ahead Log (WAL) amplification.",
    )
    add_bullet(
        doc,
        "4. Pipeline Idempotency: ",
        "The pipeline inspects source_files.file_name before extraction. Files already marked as successfully ingested are automatically skipped, allowing the pipeline to resume safely after interruptions.",
    )

    add_heading_2(
        doc, "5.4 Error Handling, Logging, and Memory Management"
    )
    add_paragraph(
        doc,
        "Robust pipeline resilience is enforced through dual logging and memory-bounded generators. The logging subsystem (src/logger.py) "
        "outputs structured timestamps, log levels, and module names concurrently to the standard console and logs/etl.log. Memory usage "
        "is bounded because only a single 200,000-record chunk resides in Python heap memory at any time. Live benchmarking with Python's "
        "tracemalloc measured peak process RAM at 643.6 MB, comfortably below standard system limits.",
    )

    add_heading_2(doc, "5.5 Ingestion Throughput and Performance")
    add_paragraph(
        doc,
        "The complete end-to-end ingestion of all 8 files (2,830,743 raw records) completed in exactly 19 minutes and 35 seconds (1,175.4 seconds). "
        "This corresponds to an effective ingestion throughput of 2,226 rows per second, including extraction, decompression, regex cleaning, "
        "vertical partitioning, and relational storage.",
    )

    # --------------------------------------------------------------------------
    # 6. DATABASE DESIGN AND SCHEMA ARCHITECTURE
    # --------------------------------------------------------------------------
    add_heading_1(doc, "6. Database Design and Schema Architecture")
    add_paragraph(
        doc,
        "The relational schema was designed to adhere strictly to Third Normal Form (3NF) while incorporating vertical partitioning "
        "to optimize PostgreSQL disk buffer utilization. Figure 2 depicts the Entity-Relationship (ER) model.",
    )

    add_image_with_caption(
        doc,
        figures_dir / "er_diagram.png",
        "Figure 2: PostgreSQL Entity-Relationship Schema Diagram",
        width_inches=6.2,
    )

    add_heading_2(doc, "6.1 Relational Table Specifications")
    add_paragraph(
        doc,
        "The database comprises four normalized tables across lookup, audit, core telemetry, and granular statistics:",
    )

    # Table 6: source_files
    t6_headers = ["Column Name", "Data Type", "Constraints", "Description"]
    t6_rows = [
        [
            "id",
            "SERIAL",
            "PRIMARY KEY",
            "Unique auto-incrementing file identifier.",
        ],
        [
            "file_name",
            "VARCHAR(255)",
            "NOT NULL UNIQUE",
            "Base filename of the extracted CSV file.",
        ],
        [
            "capture_day",
            "VARCHAR(32)",
            "NULL",
            "Day of the week of packet capture (e.g., Friday).",
        ],
        [
            "row_count",
            "BIGINT",
            "CHECK (row_count >= 0)",
            "Total valid flow records successfully ingested from this file.",
        ],
        [
            "imported_at",
            "TIMESTAMPTZ",
            "DEFAULT CURRENT_TIMESTAMP",
            "Timestamp when file ingestion was committed.",
        ],
    ]
    add_styled_table(
        doc,
        t6_headers,
        t6_rows,
        col_widths=[1.3, 1.2, 1.5, 2.27],
        caption="Table 6: source_files Audit Table Specification",
    )

    # Table 7: attack_types
    t7_headers = ["Column Name", "Data Type", "Constraints", "Description"]
    t7_rows = [
        [
            "id",
            "SMALLSERIAL",
            "PRIMARY KEY",
            "2-byte surrogate identifier for attack class.",
        ],
        [
            "label",
            "VARCHAR(64)",
            "NOT NULL UNIQUE",
            "Exact attack label string (e.g., 'DoS Hulk', 'BENIGN').",
        ],
        [
            "category",
            "VARCHAR(32)",
            "NOT NULL",
            "High-level category (e.g., 'DoS', 'Brute-Force', 'Web Attack').",
        ],
        [
            "is_malicious",
            "BOOLEAN",
            "NOT NULL DEFAULT FALSE",
            "Boolean flag: TRUE for adversary traffic, FALSE for normal traffic.",
        ],
        [
            "description",
            "TEXT",
            "NULL",
            "Detailed technical description of the attack vector.",
        ],
    ]
    add_styled_table(
        doc,
        t7_headers,
        t7_rows,
        col_widths=[1.3, 1.2, 1.5, 2.27],
        caption="Table 7: attack_types Lookup Dimension Specification",
    )

    # Table 8: flows
    t8_headers = ["Column Name", "Data Type", "Constraints", "Description"]
    t8_rows = [
        [
            "id",
            "BIGSERIAL",
            "PRIMARY KEY",
            "8-byte surrogate sequence key for network flow record.",
        ],
        [
            "source_file_id",
            "INT",
            "NOT NULL REFERENCES source_files(id)",
            "Audit foreign key tracing record to source CSV file.",
        ],
        [
            "attack_type_id",
            "SMALLINT",
            "NOT NULL REFERENCES attack_types(id)",
            "Normalized threat classification foreign key.",
        ],
        [
            "destination_port",
            "INTEGER",
            "NOT NULL CHECK (0-65535)",
            "Target TCP/UDP service port.",
        ],
        [
            "flow_duration",
            "BIGINT",
            "NOT NULL CHECK (>= 0)",
            "Bidirectional connection duration in microseconds.",
        ],
        [
            "total_fwd_packets",
            "BIGINT",
            "NOT NULL CHECK (>= 0)",
            "Forward packet count (initiator -> responder).",
        ],
        [
            "total_bwd_packets",
            "BIGINT",
            "NOT NULL CHECK (>= 0)",
            "Backward packet count (responder -> initiator).",
        ],
        [
            "total_length_of_fwd_packets",
            "BIGINT",
            "NOT NULL CHECK (>= 0)",
            "Total payload volume in forward direction (bytes).",
        ],
        [
            "total_length_of_bwd_packets",
            "BIGINT",
            "NOT NULL CHECK (>= 0)",
            "Total payload volume in backward direction (bytes).",
        ],
        [
            "flow_bytes_per_s",
            "DOUBLE PRECISION",
            "NULL",
            "Throughput rate in bytes per second.",
        ],
        [
            "flow_packets_per_s",
            "DOUBLE PRECISION",
            "NULL",
            "Packet transmission frequency per second.",
        ],
        [
            "flow_iat_mean/std/max/min",
            "DOUBLE PRECISION",
            "NULL",
            "Inter-Arrival Time (IAT) statistics between packets.",
        ],
        [
            "fin/syn/rst/psh/ack/urg_flag_count",
            "SMALLINT",
            "CHECK (>= 0)",
            "TCP protocol control flags.",
        ],
        [
            "down_up_ratio",
            "DOUBLE PRECISION",
            "CHECK (>= 0)",
            "Download/Upload traffic ratio.",
        ],
        [
            "average_packet_size",
            "DOUBLE PRECISION",
            "CHECK (>= 0)",
            "Mean size of packets across the entire connection.",
        ],
    ]
    add_styled_table(
        doc,
        t8_headers,
        t8_rows,
        col_widths=[1.5, 1.2, 1.5, 2.07],
        caption="Table 8: flows Primary Telemetry Table Specification (25 Columns)",
    )

    # Table 9: flow_statistics
    t9_headers = ["Column Name", "Data Type", "Constraints", "Description"]
    t9_rows = [
        [
            "flow_id",
            "BIGINT",
            "PRIMARY KEY REFERENCES flows(id) ON DELETE CASCADE",
            "1:1 foreign key joining back to core flows table.",
        ],
        [
            "fwd/bwd_packet_length_*",
            "DOUBLE PRECISION",
            "CHECK (>= 0)",
            "Directional packet length distributions (min, max, mean, std).",
        ],
        [
            "fwd/bwd_iat_*",
            "DOUBLE PRECISION",
            "CHECK (>= 0)",
            "Directional Inter-Arrival Times (total, mean, std, max, min).",
        ],
        [
            "fwd/bwd_header_length",
            "BIGINT",
            "NULL",
            "TCP/IP header byte length in forward/backward directions.",
        ],
        [
            "subflow_fwd/bwd_*",
            "BIGINT",
            "CHECK (>= 0)",
            "Subflow packet and byte distribution counters.",
        ],
        [
            "init_win_bytes_*",
            "BIGINT",
            "NULL",
            "Initial TCP receive window size in forward/backward directions.",
        ],
        [
            "active/idle_*",
            "DOUBLE PRECISION",
            "CHECK (>= 0)",
            "Activity and idle duration timing statistics (mean, std, max, min).",
        ],
    ]
    add_styled_table(
        doc,
        t9_headers,
        t9_rows,
        col_widths=[1.5, 1.2, 1.5, 2.07],
        caption="Table 9: flow_statistics Deep Telemetry Partition Specification (57 Columns)",
    )

    add_heading_2(
        doc, "6.2 Normalization Decisions and Vertical Partitioning Justification"
    )
    add_paragraph(
        doc,
        "The database design achieves Third Normal Form (3NF) through strict decoupling of dimensions. In the raw CSVs, the Label column "
        "implied transitive functional dependencies on category and malicious status. By extracting this into the attack_types lookup dimension, "
        "we replaced 64-byte repeated string literals with 2-byte SMALLINT foreign keys, saving approximately 162 MB of storage across 2.61M rows.",
    )
    add_paragraph(
        doc,
        "Even more critical is our decision to implement vertical table partitioning. In PostgreSQL, tables are stored in fixed 8 KB buffer pages. "
        "Storing all 79 columns in a single flat table yields an average row width of 656.5 bytes, allowing only 12.5 rows per buffer page. "
        "Scanning the entire 2.61 million row table would require reading 209,600 buffer pages (~1.64 GB from disk or cache).",
    )
    add_paragraph(
        doc,
        "However, routine SOC intrusion analysis queries almost exclusively inspect operational connection attributes: destination ports, "
        "duration, packet counts, rates, and TCP control flags. By vertically partitioning the table, the flows table contains only 25 columns "
        "with an empirically measured row width of 174.4 bytes. This increases buffer density to 47.0 rows per 8 KB page (occupying only 435 MB "
        "across 55,692 pages). This represents an empirical 3.76x cache density improvement ($47.0 / 12.5 = 3.76\\times$), keeping the working "
        "set of all connection telemetry residing in RAM.",
    )

    add_heading_2(doc, "6.3 Indexing Strategy")
    add_paragraph(
        doc,
        "To accelerate analytical queries without impacting ingestion performance, targeted B-Tree indexes were created in sql/02_indexes.sql "
        "after bulk loading completed. Table 10 documents the index catalog and the specific query profiles each index accelerates:",
    )

    # Table 10: Indexes
    t10_headers = [
        "Index Identifier",
        "Target Table",
        "Indexed Columns",
        "Supported Query Profile",
    ]
    t10_rows = [
        [
            "idx_flows_attack_type_id",
            "flows",
            "attack_type_id",
            "Threat classification filtering and JOINs with attack_types.",
        ],
        [
            "idx_flows_source_file_id",
            "flows",
            "source_file_id",
            "Ingestion lineage audits and daily traffic aggregation.",
        ],
        [
            "idx_flows_destination_port",
            "flows",
            "destination_port",
            "Service-specific forensic scans (e.g. port 80 HTTP, port 22 SSH).",
        ],
        [
            "idx_flows_duration",
            "flows",
            "flow_duration",
            "Long-duration persistent connection hunting (e.g. C2 beacons).",
        ],
        [
            "idx_flows_attack_port",
            "flows",
            "(attack_type_id, destination_port)",
            "Composite threat hunting (e.g., DoS Hulk targeting Web ports).",
        ],
        [
            "idx_attack_types_category",
            "attack_types",
            "category",
            "Aggregations grouped by high-level threat categories.",
        ],
        [
            "idx_source_files_capture_day",
            "source_files",
            "capture_day",
            "Day-of-week temporal filtering and trend analysis.",
        ],
    ]
    add_styled_table(
        doc,
        t10_headers,
        t10_rows,
        col_widths=[1.7, 0.9, 1.6, 2.07],
        caption="Table 10: PostgreSQL Index Catalog and Supported Query Profiles",
    )

    # --------------------------------------------------------------------------
    # 7. VERIFICATION AND RESULTS
    # --------------------------------------------------------------------------
    add_heading_1(doc, "7. Verification and Results")
    add_paragraph(
        doc,
        "Every metric, row count, and query plan in this report was verified directly against the live PostgreSQL database instance. "
        "Table 11 demonstrates the complete, mathematically exact reconciliation between the raw CSV inventory and loaded records:",
    )

    # Table 11: Reconciliation
    t11_headers = [
        "Audit Pipeline Stage",
        "Record Count",
        "Percentage of Raw",
        "Engineering Justification",
    ]
    t11_rows = [
        [
            "Total Raw Input Records",
            "2,830,743",
            "100.00%",
            "Cumulative raw records across all 8 extracted CSV files.",
        ],
        [
            "Intra-Chunk Duplicate Records Purged",
            "- 211,497",
            "7.47%",
            "Exact duplicates removed within 200,000-row streaming chunks.",
        ],
        [
            "Infinite / NaN Value Records Dropped",
            "- 2,872",
            "0.10%",
            "Division by zero duration yielding non-finite floating point numbers.",
        ],
        [
            "Negative Flow Duration Records Dropped",
            "- 108",
            "< 0.01%",
            "Timer jitter anomalies resulting in negative lifespan (-1 μs).",
        ],
        [
            "Total Records Successfully Ingested",
            "2,616,266",
            "92.42%",
            "Clean records loaded and synchronized in flows and flow_statistics.",
        ],
    ]
    add_styled_table(
        doc,
        t11_headers,
        t11_rows,
        col_widths=[1.8, 1.0, 1.1, 2.37],
        caption="Table 11: End-to-End Ingestion Reconciliation",
    )

    add_heading_2(doc, "7.1 Source File Lineage and Relational Integrity")
    add_paragraph(
        doc,
        "Table 12 lists the exact loaded counts per source capture file stored in source_files, while Table 13 summarizes the results of "
        "automated referential integrity checks executed by src/verify.py:",
    )

    # Table 12: Source files loaded
    t12_headers = [
        "Audit ID",
        "Capture Weekday",
        "Loaded Record Count",
        "Lineage Source File Name",
    ]
    t12_rows = [
        [
            "1",
            "Friday",
            "223,352",
            "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
        ],
        [
            "2",
            "Friday",
            "233,153",
            "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
        ],
        [
            "3",
            "Friday",
            "184,035",
            "Friday-WorkingHours-Morning.pcap_ISCX.csv",
        ],
        ["4", "Monday", "508,823", "Monday-WorkingHours.pcap_ISCX.csv"],
        [
            "5",
            "Thursday",
            "258,153",
            "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
        ],
        [
            "6",
            "Thursday",
            "164,168",
            "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
        ],
        ["7", "Tuesday", "426,391", "Tuesday-WorkingHours.pcap_ISCX.csv"],
        ["8", "Wednesday", "618,191", "Wednesday-workingHours.pcap_ISCX.csv"],
        [
            "Total",
            "All Files",
            "2,616,266",
            "100% Synchronized with flows and flow_statistics",
        ],
    ]
    add_styled_table(
        doc,
        t12_headers,
        t12_rows,
        col_widths=[0.8, 1.1, 1.4, 2.97],
        caption="Table 12: Source File Lineage and Loaded Inventory in PostgreSQL",
    )

    # Table 13: Integrity Checks
    t13_headers = [
        "Integrity Audit Test",
        "SQL Query / Verification Logic",
        "Defect Count",
        "Audit Status",
    ]
    t13_rows = [
        [
            "Vertical Split Sync",
            "COUNT(flows) - COUNT(flow_statistics)",
            "0",
            "PASS (100% 1:1 Synchronized)",
        ],
        [
            "Orphan Source Files",
            "flows WHERE source_file_id NOT IN (source_files)",
            "0",
            "PASS (Zero Orphan Records)",
        ],
        [
            "Orphan Attack Types",
            "flows WHERE attack_type_id NOT IN (attack_types)",
            "0",
            "PASS (Zero Orphan Records)",
        ],
        [
            "Telemetry NULLs",
            "flows WHERE destination_port IS NULL OR flow_duration IS NULL",
            "0",
            "PASS (Zero NULLs in Core Columns)",
        ],
        [
            "Negative Durations",
            "flows WHERE flow_duration < 0",
            "0",
            "PASS (Zero Domain Violations)",
        ],
        [
            "Label Whitespace",
            "attack_types WHERE label != TRIM(label)",
            "0",
            "PASS (Zero Whitespace Defects)",
        ],
        [
            "Unicode Replacement",
            "attack_types WHERE POSITION(chr(65533) IN label) > 0",
            "0",
            "PASS (Zero Corrupted Encodings)",
        ],
    ]
    add_styled_table(
        doc,
        t13_headers,
        t13_rows,
        col_widths=[1.5, 2.2, 0.9, 1.67],
        caption="Table 13: Relational Integrity and Data Quality Verification Results",
    )

    add_heading_2(doc, "7.2 Business Analytics Queries and Interpretations")
    add_paragraph(
        doc,
        "To demonstrate the analytical capabilities of the data warehouse, four key business queries were executed. Each query provides "
        "actionable intelligence for SOC security analysts:",
    )

    # Query 1
    add_heading_3(doc, "Query 1: Benign vs. Malicious Attack Traffic Share")
    q1_sql = """SELECT 
    CASE WHEN at.is_malicious THEN 'Malicious Attacks' ELSE 'Benign Business Traffic' END AS traffic_type,
    COUNT(f.id) AS total_flows,
    ROUND((COUNT(f.id) * 100.0 / (SELECT COUNT(*) FROM flows))::numeric, 2) AS share_pct
FROM flows f
JOIN attack_types at ON f.attack_type_id = at.id
GROUP BY at.is_malicious
ORDER BY total_flows DESC;"""
    add_code_block(doc, q1_sql)
    q1_headers = [
        "Traffic Classification",
        "Total Ingested Flows",
        "Traffic Share (%)",
    ]
    q1_rows = [
        ["Benign Business Traffic", "2,170,865", "82.98%"],
        ["Malicious Attacks", "445,401", "17.02%"],
    ]
    add_styled_table(doc, q1_headers, q1_rows, col_widths=[2.5, 2.0, 1.77])
    add_paragraph(
        doc,
        "While benign traffic dominates enterprise bandwidth at 82.98%, malicious intrusions constitute "
        "17.02% of all connection attempts (nearly 1 in every 6 connections), demonstrating the urgent necessity for automated filtering.",
        bold_prefix="Business Meaning: ",
    )

    # Query 2
    add_heading_3(doc, "Query 2: Top 10 Targeted Destination Ports")
    q2_sql = """SELECT 
    f.destination_port,
    COUNT(*) AS attack_count,
    ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM flows WHERE attack_type_id != 1))::numeric, 2) AS pct_of_attacks
FROM flows f
WHERE f.attack_type_id != 1
GROUP BY f.destination_port
ORDER BY attack_count DESC
LIMIT 10;"""
    add_code_block(doc, q2_sql)
    add_image_with_caption(
        doc,
        figures_dir / "top_attack_ports.png",
        "Figure 4: Top 10 Targeted Destination Ports for Malicious Attack Traffic",
        width_inches=6.0,
    )
    add_paragraph(
        doc,
        "Port 80 (standard HTTP) faces an overwhelming 72.96% of all malicious flows (324,985 attacks), "
        "primarily driven by DoS Hulk and web exploits, followed by legacy management ports (FTP 21 at 1.39% and SSH 22 at 0.83%).",
        bold_prefix="Business Meaning: ",
    )

    # Query 3
    add_heading_3(
        doc,
        "Query 3: Behavioral Profiling: Average Duration and Packet Dynamics",
    )
    q3_sql = """SELECT 
    at.category,
    COUNT(*) AS flow_count,
    ROUND((AVG(f.flow_duration) / 1000.0)::numeric, 2) AS avg_duration_ms,
    ROUND(AVG(f.total_fwd_packets)::numeric, 1) AS avg_fwd_pkts,
    ROUND(AVG(f.total_bwd_packets)::numeric, 1) AS avg_bwd_pkts,
    ROUND((AVG(f.flow_bytes_per_s) / 1024.0)::numeric, 2) AS avg_kb_per_s
FROM flows f
JOIN attack_types at ON f.attack_type_id = at.id
GROUP BY at.category
ORDER BY flow_count DESC;"""
    add_code_block(doc, q3_sql)
    q3_headers = [
        "Threat Category",
        "Flow Count",
        "Avg Duration",
        "Avg Fwd Pkts",
        "Avg Bwd Pkts",
        "Throughput (KB/s)",
    ]
    q3_rows = [
        ["Benign", "2,170,865", "11,735.91 ms", "11.1", "12.7", "1,663.42"],
        ["DoS", "194,458", "72,368.42 ms", "6.3", "5.3", "68.66"],
        ["DDoS", "128,014", "16,957.16 ms", "4.5", "3.3", "59.09"],
        ["PortScan", "109,418", "120.28 ms", "1.0", "1.0", "236.10"],
        ["Brute-Force", "9,373", "7,703.42 ms", "11.0", "16.7", "23.85"],
        ["Web Attack", "2,143", "6,646.53 ms", "11.1", "5.4", "0.16"],
        ["Bot", "1,948", "354.19 ms", "3.2", "3.4", "283.33"],
        ["Infiltration", "36", "78,407.72 ms", "830.2", "829.6", "19.72"],
        ["Heartbleed", "11", "110,679.71 ms", "2,583.7", "1,897.2", "64.36"],
    ]
    add_styled_table(
        doc,
        q3_headers,
        q3_rows,
        col_widths=[1.1, 1.0, 1.1, 1.0, 1.0, 1.07],
        caption="Behavioral Telemetry Dynamics by Threat Category",
    )
    add_paragraph(
        doc,
        "Distinct behavioral signatures emerge: PortScans exhibit ultra-short sessions (120.28 ms, exactly 1 packet each way), "
        "whereas DoS attacks maintain protracted sessions (72,368 ms) designed to exhaust web server thread pools.",
        bold_prefix="Business Meaning: ",
    )

    # Query 4
    add_heading_3(doc, "Query 4: Temporal Spikes: Attack Volume by Weekday")
    q4_sql = """SELECT 
    sf.capture_day,
    COUNT(f.id) AS total_flows,
    COUNT(f.id) FILTER (WHERE f.attack_type_id != 1) AS attack_flows,
    ROUND((COUNT(f.id) FILTER (WHERE f.attack_type_id != 1) * 100.0 / COUNT(f.id))::numeric, 2) AS attack_pct
FROM source_files sf
JOIN flows f ON f.source_file_id = sf.id
GROUP BY sf.capture_day
ORDER BY attack_flows DESC;"""
    add_code_block(doc, q4_sql)
    add_image_with_caption(
        doc,
        figures_dir / "daily_traffic_volume.png",
        "Figure 5: Ingested Flow Volume and Attack Classification Across Weekdays",
        width_inches=6.0,
    )
    add_paragraph(
        doc,
        "Friday (37.37% attack rate, 239,380 attacks) and Wednesday (31.46% attack rate, 194,469 attacks) "
        "experience extreme attack volumes, whereas Monday is entirely benign baseline traffic (0 attacks across 508,823 flows).",
        bold_prefix="Business Meaning: ",
    )


    add_heading_2(
        doc, "7.3 Query Optimization and EXPLAIN ANALYZE Benchmarks"
    )
    add_paragraph(
        doc,
        "To rigorously quantify the performance impact of our B-Tree indexing strategy, we benchmarked Query 6 (counting all DoS Hulk flows, "
        "attack_type_id = 2) using PostgreSQL's EXPLAIN (ANALYZE, BUFFERS) before and after disabling indexes. Figure 6 and the query plans "
        "below highlight the dramatic performance gain:",
    )

    add_image_with_caption(
        doc,
        figures_dir / "index_performance_comparison.png",
        "Figure 6: PostgreSQL Query Execution Latency: Sequential vs. Index Scan",
        width_inches=5.8,
    )

    plan_indexed = """-- 1. WITH B-TREE INDEX (Index Only Scan on idx_flows_attack_type_id)
Aggregate  (cost=4077.38..4077.39 rows=1 width=8) (actual time=65.421..65.422 rows=1.00 loops=1)
  Buffers: shared hit=152 read=1
  ->  Index Only Scan using idx_flows_attack_type_id on flows  (cost=0.43..3649.74 rows=171056 width=0) 
        (actual time=1.202..38.636 rows=173559.00 loops=1)
        Index Cond: (attack_type_id = 2)
Execution Time: 65.799 ms  |  Total Buffer Pages Traversed: 153 pages (1.2 MB)"""
    add_code_block(doc, plan_indexed)

    plan_seq = """-- 2. WITHOUT INDEX (Parallel Sequential Table Scan across 2 workers)
Finalize Aggregate  (cost=70492.94..70492.95 rows=1 width=8) (actual time=693.690..702.394 rows=1.00 loops=1)
  Buffers: shared hit=1034 read=54658
  ->  Gather  (cost=70492.72..70492.93 rows=2 width=8) (actual time=693.461..702.383 rows=3.00 loops=1)
        Workers Planned: 2  |  Workers Launched: 2
        ->  Parallel Seq Scan on flows  (cost=0.00..69314.54 rows=71273 width=0)
              Filter: (attack_type_id = 2)  |  Rows Removed by Filter: 814236
Execution Time: 702.537 ms  |  Total Buffer Pages Traversed: 55,692 pages (435.1 MB)"""
    add_code_block(doc, plan_seq)

    add_callout(
        doc,
        "• Query Latency Reduction: Dropped from 702.5 ms (Sequential Scan) to 65.8 ms (Index Scan) -> 10.7x Speedup.\n"
        "• I/O Buffer Traversal Reduction: Dropped from 55,692 disk pages (435 MB) to 153 index pages (1.2 MB) -> 364x I/O Reduction.\n"
        "• Production Impact: Guarantees interactive SOC dashboard performance without saturating database server I/O.",
        title="EMPIRICAL INDEX OPTIMIZATION RESULTS",
    )

    # --------------------------------------------------------------------------
    # 8. SET-UP AND EXECUTION INSTRUCTIONS
    # --------------------------------------------------------------------------
    add_heading_1(doc, "8. Set-up and Execution Instructions")
    add_paragraph(
        doc,
        "This section provides numbered, copy-paste-ready instructions to deploy and execute the pipeline from a clean development environment.",
    )

    add_heading_2(doc, "Step 1: System Prerequisites")
    add_paragraph(
        doc,
        "Verify that the host environment meets the minimum software requirements:",
    )
    add_bullet(
        doc,
        "• Operating System: ",
        "Windows 10/11, macOS 12+, or Ubuntu Linux 22.04 LTS.",
    )
    add_bullet(
        doc,
        "• Python: ",
        "Python 3.10, 3.11, or 3.12 (64-bit). Verify with: python --version.",
    )
    add_bullet(
        doc,
        "• PostgreSQL: ",
        "PostgreSQL 14, 15, 16, or 17 server running locally or accessible via network.",
    )
    add_bullet(
        doc,
        "• System Memory & Disk: ",
        "Minimum 8 GB RAM and 10 GB free disk space (for dataset extraction and PostgreSQL tables).",
    )

    add_heading_2(doc, "Step 2: Clone the Repository and Navigate to Root")
    add_code_block(
        doc,
        "git clone https://github.com/NardosShumete/ids-etl-pipeline-postgres-assignment.git\n"
        "cd ids-etl-pipeline-postgres-assignment",
    )

    add_heading_2(
        doc, "Step 3: Create and Activate Python Virtual Environment"
    )
    add_code_block(
        doc,
        "# Windows PowerShell:\n"
        "python -m venv .venv\n"
        ".\\.venv\\Scripts\\Activate.ps1\n\n"
        "# Linux / macOS Bash:\n"
        "python3 -m venv .venv\n"
        "source .venv/bin/activate",
    )

    add_heading_2(doc, "Step 4: Install Required Python Packages")
    add_code_block(
        doc,
        "pip install --upgrade pip\n"
        "pip install -r requirements.txt\n"
        "# Verify key packages:\n"
        "python -c 'import pandas, psycopg2, sqlalchemy, docx, matplotlib; print(\"Environment Ready!\")'",
    )

    add_heading_2(doc, "Step 5: Configure Environment Credentials (.env)")
    add_paragraph(
        doc,
        "Copy the template configuration file .env.example to .env and configure your local PostgreSQL database credentials:",
    )
    add_code_block(
        doc,
        "# Windows PowerShell:\n"
        "Copy-Item .env.example .env\n\n"
        "# Linux / macOS:\n"
        "cp .env.example .env\n\n"
        "# Edit .env with your PostgreSQL credentials:\n"
        "DB_HOST=localhost\n"
        "DB_PORT=5432\n"
        "DB_NAME=ids_flows_db\n"
        "DB_USER=postgres\n"
        "DB_PASSWORD=your_secure_password_here",
    )

    add_heading_2(doc, "Step 6: Place the Dataset Archive")
    add_paragraph(
        doc,
        "Download archive.zip from Kaggle (chethuhn/network-intrusion-dataset) and place it directly into the data/ directory:",
    )
    add_code_block(
        doc,
        "# Verify archive placement (size should be ~229 MB):\n"
        "ls -lh data/archive.zip",
    )

    add_heading_2(
        doc, "Step 7: Initialize PostgreSQL Database and Schema DDL"
    )
    add_code_block(
        doc,
        "python -m src.create_database\n\n"
        "# Expected Output:\n"
        "# [INFO] Database 'ids_flows_db' created or verified.\n"
        "# [INFO] Executing schema DDL from sql/01_schema.sql...\n"
        "# [INFO] Tables created: source_files, attack_types, flows, flow_statistics.\n"
        "# [INFO] Attack types seed taxonomy inserted (15 classes).",
    )

    add_heading_2(doc, "Step 8: Execute Full ETL Ingestion Pipeline")
    add_code_block(
        doc,
        "python -m src.pipeline\n\n"
        "# Expected Output:\n"
        "# [INFO] pipeline: Starting pipeline execution...\n"
        "# [INFO] extract: Extracting data/archive.zip to data/raw/...\n"
        "# [INFO] pipeline: Ingesting file 1/8: Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv...\n"
        "# ...\n"
        "# [INFO] pipeline: Ingestion completed: 2,616,266 records in 19m 35s.\n"
        "# [INFO] pipeline: Applying post-load indexes from sql/02_indexes.sql...\n"
        "# [INFO] pipeline: All B-Tree indexes created successfully.",
    )

    add_heading_2(
        doc, "Step 9: Run Automated Verification and Quality Audits"
    )
    add_code_block(
        doc,
        "python -m src.verify\n\n"
        "# Expected Output:\n"
        "# [PASS] Dataset verification confirmed: > 2 Million rows ingested.\n"
        "# [PASS] Vertical partitioning is 100% synchronized (flows == flow_statistics).\n"
        "# [PASS] Zero orphan records found. Referential integrity is strictly maintained.\n"
        "# [PASS] Zero NULL values in critical telemetry columns.\n"
        "# [PASS] All attack type labels are clean, valid, and properly encoded.",
    )

    add_heading_2(doc, "Step 10: Run Unit Tests and Code Linter")
    add_code_block(
        doc,
        "pytest tests/ -v\n"
        "ruff check src/ tests/\n\n"
        "# Expected Output:\n"
        "# ============================= 13 passed in 2.61s =============================\n"
        "# All checks passed!",
    )

    add_heading_2(doc, "8.1 Operational Troubleshooting Guide")
    add_paragraph(
        doc,
        "Table 14 documents common deployment errors, root causes, and verified technical remediations:",
    )

    # Table 14: Troubleshooting
    t14_headers = [
        "Observed Symptom / Error",
        "Probable Root Cause",
        "Verified Technical Remediation",
    ]
    t14_rows = [
        [
            "ValueError: Missing required environment variable: DB_PASSWORD",
            ".env file missing or DB_PASSWORD is unset.",
            "Copy .env.example to .env and set your active PostgreSQL password.",
        ],
        [
            "psycopg2.OperationalError: Connection refused (port 5432)",
            "PostgreSQL service is stopped or port is blocked.",
            "Start service via 'net start postgresql-x64-16' (Windows) or 'sudo systemctl start postgresql' (Linux).",
        ],
        [
            "FileNotFoundError: archive.zip not found in data/",
            "Dataset archive was not placed in data/ folder.",
            "Download archive.zip from Kaggle and place it in data/archive.zip.",
        ],
        [
            "PermissionError: [Errno 13] Permission denied: 'docs/report.docx'",
            "Report file is currently open in Microsoft Word.",
            "Close Microsoft Word to release the exclusive file lock and re-run build_report.py.",
        ],
        [
            "MemoryError during CSV extraction",
            "chunk_size set too high for available system RAM.",
            "Ensure DEFAULT_CHUNK_SIZE remains set to 200,000 in src/config.py.",
        ],
    ]
    add_styled_table(
        doc,
        t14_headers,
        t14_rows,
        col_widths=[2.1, 1.8, 2.37],
        caption="Table 14: Operational Troubleshooting Guide",
    )

    # --------------------------------------------------------------------------
    # 9. CHALLENGES AND LESSONS LEARNED
    # --------------------------------------------------------------------------
    add_heading_1(doc, "9. Challenges and Lessons Learned")
    add_paragraph(
        doc,
        "Developing an enterprise-grade ETL pipeline across millions of records yielded several critical engineering lessons:",
    )
    add_bullet(
        doc,
        "1. Real-World Datasets Contain Hidden Header Defects: ",
        "Raw network data invariably contains irregular whitespace and duplicate column names ('Fwd Header Length'). Standardizing column names into clean, predictable snake_case identifiers early in the pipeline prevents downstream relational errors.",
    )
    add_bullet(
        doc,
        "2. Character Encodings Require Fallback Resilience: ",
        "Assuming a uniform UTF-8 encoding across all files causes unexpected fatal crashes. Implementing automated dual-encoding fallback (UTF-8 with Latin-1 fallback) guarantees robust extraction across legacy and multi-platform data dumps.",
    )
    add_bullet(
        doc,
        "3. Chunked Streaming is Mandatory for Predictable Memory: ",
        "Attempting full-dataset in-memory processing exhausts RAM. Streaming chunk generators bound memory predictably (643.6 MB peak RAM), allowing the pipeline to execute reliably on constrained developer machines.",
    )
    add_bullet(
        doc,
        "4. Synchronizing 1:1 Vertical Partitions Requires Explicit Sequence Pre-allocation: ",
        "When splitting a single DataFrame into two relational tables with a 1:1 foreign key dependency, relying on auto-incrementing database defaults can cause sequence desynchronization during parallel or aborted transactions. Explicitly pre-allocating sequences via nextval('flows_id_seq') guarantees perfect 1:1 ID alignment.",
    )
    add_bullet(
        doc,
        "5. Bulk Ingestion Must Defer Index Creation: ",
        "Inserting rows into indexed tables triggers severe B-Tree page splits and Write-Ahead Log (WAL) overhead. Deferring secondary index construction until after bulk loading reduced total load time by an estimated 65%.",
    )

    # --------------------------------------------------------------------------
    # 10. LIMITATIONS AND FUTURE WORK
    # --------------------------------------------------------------------------
    add_heading_1(doc, "10. Limitations and Future Work")
    add_paragraph(
        doc,
        "While this architecture successfully meets all technical objectives, several architectural enhancements can expand its capabilities:",
    )
    add_bullet(
        doc,
        "• Declarative Table Partitioning by Range: ",
        "Currently, flows is a single large table. Implementing PostgreSQL declarative table partitioning by capture date (PARTITION BY RANGE (imported_at)) would allow partition pruning during historical range queries.",
    )
    add_bullet(
        doc,
        "• Distributed Workflow Orchestration (Apache Airflow): ",
        "Migrating from local Python script execution to an Apache Airflow DAG would provide automated scheduling, DAG visualization, alerting, and automated retries.",
    )
    add_bullet(
        doc,
        "• Real-Time Stream Ingestion (Apache Kafka): ",
        "Integrating Apache Kafka and Faust would transition the system from batch file ingestion to real-time packet stream processing, allowing sub-second intrusion alerts.",
    )
    add_bullet(
        doc,
        "• Interactive SOC Dashboards (Power BI / Grafana): ",
        "Connecting PostgreSQL to Grafana or Microsoft Power BI would provide operational security dashboards for real-time visualization of PortScan and DoS spikes.",
    )
    add_bullet(
        doc,
        "• Machine Learning Intrusion Classification: ",
        "Deploying an XGBoost or Random Forest classification model directly on the normalized flow_statistics telemetry would enable automated anomaly detection for zero-day exploits.",
    )

    # --------------------------------------------------------------------------
    # 11. TEAM CONTRIBUTIONS
    # --------------------------------------------------------------------------
    add_heading_1(doc, "11. Team Contributions")
    add_paragraph(
        doc,
        "This project was collaboratively designed and implemented by a multidisciplinary team of student data engineers. "
        "Table 15 specifies the technical responsibilities and contributions of each team member:",
    )

    # Table 15: Team Contributions
    t15_headers = [
        "Team Member Name",
        "Student ID",
        "Engineering Role",
        "Detailed Technical Deliverables",
    ]
    t15_rows = [
        [
            "[TO BE FILLED: Student 1]",
            "[TO BE FILLED: ID 1]",
            "Pipeline Architecture & Streaming Ingestion Lead",
            "Designed src/extract.py, streaming generator architecture, chunksize optimization, and end-to-end pipeline CLI orchestration.",
        ],
        [
            "[TO BE FILLED: Student 2]",
            "[TO BE FILLED: ID 2]",
            "Relational Database Modeling Specialist",
            "Authored sql/01_schema.sql, engineered 1:1 vertical table partitioning, primary/foreign key constraints, and PostgreSQL data types.",
        ],
        [
            "[TO BE FILLED: Student 3]",
            "[TO BE FILLED: ID 3]",
            "Data Quality & Cleansing Engineer",
            "Developed src/transform.py, regex Web Attack encoding sanitization, infinite/NaN filtering, negative duration purging, and unit tests.",
        ],
        [
            "[TO BE FILLED: Student 4]",
            "[TO BE FILLED: ID 4]",
            "Analytical Query & Optimization Specialist",
            "Authored sql/02_indexes.sql, sql/04_analytics.sql, post-load indexing benchmarks, and EXPLAIN ANALYZE query optimization.",
        ],
    ]
    add_styled_table(
        doc,
        t15_headers,
        t15_rows,
        col_widths=[1.5, 1.1, 1.6, 2.07],
        caption="Table 15: Comprehensive Team Contributions Matrix",
    )

    # --------------------------------------------------------------------------
    # 12. CONCLUSION
    # --------------------------------------------------------------------------
    add_heading_1(doc, "12. Conclusion")
    add_paragraph(
        doc,
        "This project successfully engineered and demonstrated a resilient, production-grade ETL pipeline and normalized relational data "
        "warehouse for network intrusion detection telemetry. By processing the benchmark CIC-IDS-2017 dataset, the architecture extracted "
        "2,830,743 raw records across 8 capture files, purged 214,477 invalid records through deterministic cleaning rules, and successfully "
        "ingested exactly 2,616,266 records into PostgreSQL with zero referential integrity violations.",
    )
    add_paragraph(
        doc,
        "Key engineering achievements include streaming binary COPY loading at 2,226 rows per second, strict memory bounding below 650 MB RAM, "
        "a 3.76x cache density improvement through 1:1 vertical table partitioning, and a 10.7x analytical query speedup via strategic post-load "
        "B-Tree indexing. The resulting system empowers security operations analysts to conduct rapid, forensic threat hunting across millions "
        "of network connections, providing a robust technical foundation for modern cybersecurity data engineering.",
    )

    # --------------------------------------------------------------------------
    # 13. REFERENCES AND APPENDICES
    # --------------------------------------------------------------------------
    add_heading_1(doc, "13. References")
    add_bullet(
        doc,
        "1. Sharafaldin, I., Lashkari, A. H., & Ghorbani, A. A. (2018). ",
        "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization. Proceedings of the 4th International Conference on Information Systems Security and Privacy (ICISSP 2018), pp. 108-116.",
    )
    add_bullet(
        doc,
        "2. Canadian Institute for Cybersecurity (CIC). ",
        "CIC-IDS-2017 Dataset Documentation and Feature Definitions. University of New Brunswick (UNB). https://www.unb.ca/cic/datasets/ids-2017.html",
    )
    add_bullet(
        doc,
        "3. PostgreSQL Global Development Group. (2024). ",
        "PostgreSQL 16 Documentation: Routine Vacuuming, Indexing Strategies, and COPY Protocol. https://www.postgresql.org/docs/16/",
    )
    add_bullet(
        doc,
        "4. McKinney, W. (2022). ",
        "Python for Data Analysis: Data Wrangling with pandas, NumPy, and Jupyter (3rd ed.). O'Reilly Media.",
    )
    add_bullet(
        doc,
        "5. Kaggle Dataset Mirror. ",
        "Network Intrusion Dataset (CIC-IDS-2017). Curated by Chethuhn. https://www.kaggle.com/datasets/chethuhn/network-intrusion-dataset",
    )

    doc.add_page_break()

    # Appendices
    add_heading_1(doc, "Appendix A: Project Repository and Source Code Link")
    add_paragraph(
        doc,
        "The complete, version-controlled source code, unit test suite, SQL DDL scripts, and report generators are hosted on GitHub:",
    )
    add_paragraph(
        doc,
        "GitHub Repository URL: https://github.com/NardosShumete/ids-etl-pipeline-postgres-assignment.git",
        bold_prefix="Repository: ",
    )

    add_heading_1(doc, "Appendix B: Project Folder Layout")
    tree_text = """ids-etl-pipeline-postgres-assignment/
├── .env.example              <- Template configuration file for database credentials
├── .gitignore                <- Strict gitignore excluding datasets, logs, and environments
├── README.md                 <- Complete setup, usage, and architectural documentation
├── requirements.txt          <- Pinned Python dependencies (pandas, psycopg2, docx, etc.)
├── data/
│   ├── archive.zip           <- Raw Kaggle CIC-IDS-2017 compressed dataset (229 MB)
│   └── raw/                  <- Extracted CSV files (843.66 MB total across 8 files)
├── docs/
│   ├── ETL_Pipeline_Report_Formatted.docx <- Formatted Word technical report
│   ├── ETL_Pipeline_Report_Formatted.pdf  <- Formatted PDF export of the technical report
│   ├── build_report.py       <- Automated report generator script

│   └── figures/              <- Publication-grade figures (300 DPI PNG diagrams and charts)
│       ├── architecture_diagram.png
│       ├── er_diagram.png
│       ├── attack_distribution.png
│       ├── top_attack_ports.png
│       ├── daily_traffic_volume.png
│       └── index_performance_comparison.png
├── logs/
│   └── etl.log               <- Execution log tracing chunk ingestion and timestamps
├── sql/
│   ├── 01_schema.sql         <- PostgreSQL DDL schema with 1:1 vertical partitioning
│   ├── 02_indexes.sql        <- Post-load B-Tree indexes and performance rationale
│   ├── 03_verification.sql   <- Comprehensive database integrity and quality queries
│   └── 04_analytics.sql      <- SOC intrusion threat-hunting analytical SQL queries
├── src/
│   ├── __init__.py           <- Package initialization
│   ├── config.py             <- Path management and strict credential validation
│   ├── create_database.py    <- Automated database creation and schema executor
│   ├── extract.py            <- Streaming CSV reader with dual-encoding fallback
│   ├── transform.py          <- Data cleansing rules, label repair, and vertical split
│   ├── load.py               <- High-throughput streaming COPY loader (psycopg2)
│   ├── logger.py             <- Dual console and file logging subsystem
│   ├── pipeline.py           <- End-to-end pipeline orchestrator and CLI entry point
│   └── verify.py             <- Automated database verification audit runner
└── tests/
    ├── test_config.py        <- Unit tests for configuration and password validation
    ├── test_schema.py        <- Integration tests for tables, PK/FKs, and check constraints
    └── test_transform.py     <- Unit tests for cleansing, deduplication, and partitioning"""
    add_code_block(doc, tree_text)

    add_heading_1(doc, "Appendix C: Complete PostgreSQL Schema DDL")
    schema_path = Path("sql/01_schema.sql")
    if schema_path.is_file():
        add_code_block(doc, schema_path.read_text(encoding="utf-8"))

    # Save Word document
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_docx)
    size_kb = output_docx.stat().st_size / 1024
    print(
        f"Successfully generated Word report: {output_docx} ({size_kb:.1f} KB)"
    )


if __name__ == "__main__":
    generate_etl_report()
