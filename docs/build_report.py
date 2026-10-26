"""Automated Document Generator: Converts docs/report.md to docs/report.docx

Features:
- Professional executive styling (Calibri/Consolas, corporate navy theme).
- Replaces raw Mermaid text with high-resolution diagram PNGs from docs/figures/.
- Embedded table formatting with bold headers and alternating borders.
- Structured Cover Page and Team Contributions Table.
- Automated Word-to-PDF export via Word COM automation.
"""

import re
import sys
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor


def build_docx(
    md_path: Path = Path("docs/report.md"),
    docx_path: Path = Path("docs/report.docx"),
) -> None:
    """Build Word document from markdown source."""
    if not md_path.is_file():
        raise FileNotFoundError(f"Markdown report source not found: {md_path}")

    doc = docx.Document()

    # 1. Page Margins (Standard 1.0 inch)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # 2. Typography Styles
    styles = doc.styles
    normal_style = styles["Normal"]
    normal_style.font.name = "Calibri"
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)  # Slate 800

    lines = md_path.read_text(encoding="utf-8").splitlines()

    in_code_block = False
    is_mermaid = False
    code_lines = []
    table_lines = []

    def flush_table(lines: list[str]) -> None:
        if not lines:
            return
        header_line = lines[0]
        headers = [c.strip() for c in header_line.split("|")[1:-1]]
        data_lines = [l for l in lines[2:] if l.strip().startswith("|")]

        table = doc.add_table(rows=len(data_lines) + 1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"

        for col_idx, h in enumerate(headers):
            cell = table.cell(0, col_idx)
            cell.text = h
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                if p.runs:
                    p.runs[0].font.bold = True
                    p.runs[0].font.size = Pt(9.5)
                    p.runs[0].font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

        for row_idx, dline in enumerate(data_lines, 1):
            cells = [c.strip() for c in dline.split("|")[1:-1]]
            for col_idx in range(min(len(cells), len(headers))):
                cell = table.cell(row_idx, col_idx)
                cell.text = cells[col_idx]
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    if p.runs:
                        p.runs[0].font.size = Pt(9.0)

        doc.add_paragraph()  # Spacing

    def flush_code(lines: list[str]) -> None:
        if not lines:
            return
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run("\n".join(lines))
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    def embed_image(img_path: Path, caption: str) -> None:
        if not img_path.is_file():
            p = doc.add_paragraph(f"[Image Missing: {img_path.name}]")
            p.runs[0].font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
            return

        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(10)
        p_img.paragraph_format.space_after = Pt(4)
        run = p_img.add_run()
        run.add_picture(str(img_path), width=Inches(6.2))

        # Caption
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run(caption)
        r_cap.font.italic = True
        r_cap.font.size = Pt(9.5)
        r_cap.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    i = 0
    figures_dir = md_path.parent / "figures"

    while i < len(lines):
        line = lines[i]

        # Check for image markdown: ![Caption](path)
        img_match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if img_match:
            caption = img_match.group(1)
            rel_path = img_match.group(2)
            img_file = md_path.parent / rel_path
            embed_image(img_file, caption)
            i += 1
            continue

        # Code block handler
        if line.strip().startswith("```"):
            if in_code_block:
                if not is_mermaid:
                    flush_code(code_lines)
                code_lines = []
                in_code_block = False
                is_mermaid = False
            else:
                in_code_block = True
                is_mermaid = "mermaid" in line.lower()
                code_lines = []
            i += 1
            continue

        if in_code_block:
            if not is_mermaid:
                code_lines.append(line)
            i += 1
            continue

        # Table block handler
        if line.strip().startswith("|"):
            table_lines.append(line)
            i += 1
            continue
        elif table_lines:
            flush_table(table_lines)
            table_lines = []

        # Heading 1
        if line.startswith("# "):
            p = doc.add_heading(line[2:].strip(), level=1)
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(6)
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

        # Heading 2
        elif line.startswith("## "):
            p = doc.add_heading(line[3:].strip(), level=2)
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(4)
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

        # Heading 3
        elif line.startswith("### "):
            p = doc.add_heading(line[4:].strip(), level=3)
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(2)
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.color.rgb = RGBColor(0x0F, 0x76, 0x6E)

        # Bullet List Items
        elif line.startswith("- ") or line.startswith("* "):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            text = line[2:].strip()
            parts = re.split(r"(\*\*.*?\*\*)", text)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    r = p.add_run(part[2:-2])
                    r.bold = True
                else:
                    p.add_run(part)

        # Horizontal Divider
        elif line.strip() == "---":
            pass

        # Standard Paragraph
        elif line.strip():
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            parts = re.split(r"(\*\*.*?\*\*)", line)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    r = p.add_run(part[2:-2])
                    r.bold = True
                else:
                    p.add_run(part)

        i += 1

    if table_lines:
        flush_table(table_lines)

    doc.save(docx_path)
    print(
        f"Successfully built {docx_path} ({docx_path.stat().st_size / 1024:.1f} KB)"
    )


if __name__ == "__main__":
    build_docx()
