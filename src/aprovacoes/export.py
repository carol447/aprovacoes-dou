from __future__ import annotations

import json
from copy import copy
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Font, PatternFill, Side, Border

from .models import ApprovalRecord, ProductType
from .rules import CONCENTRATION_RE, FORMULATION_RE, has_biological_product_hint
from .translations import Translator


def biological_rows(path: Path, column: str) -> set[int]:
    wb = load_workbook(path, rich_text=True)
    try:
        rows = wb.active.iter_rows()
        index = [cell.value for cell in next(rows)].index(column)
        return {
            number for number, row in enumerate(rows)
            if row[index].value and (
                row[index].font.italic
                or has_biological_product_hint(str(row[index].value))
                or (isinstance(row[index].value, CellRichText)
                    and any(isinstance(run, TextBlock) and run.font.i for run in row[index].value))
            )
        }
    finally:
        wb.close()


def write_xlsx(
    rows: list[dict[str, str]] | pd.DataFrame, path: Path, magazine: bool = False,
    italic_products: set[int] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    wb = load_workbook(path)
    ws = wb.active
    if magazine:
        green = PatternFill("solid", fgColor="C6E0B4")
        thin = Side(style="thin", color="666666")
        for cell in ws[1]:
            cell.fill = green
            cell.font = Font(name="Times New Roman", size=10, bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Times New Roman", size=9)
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        widths = [14, 22, 34, 26, 42, 24] if len(ws[1]) == 6 else [14, 26, 28, 48, 25]
        for index, width in enumerate(widths, start=1):
            ws.column_dimensions[ws.cell(1, index).column_letter].width = width
        ws.row_dimensions[1].height = 52
        ws.sheet_view.showGridLines = False
    for column in ws[1]:
        if column.value not in {"Produto", "produto_pt", "produto_en", "produto_cn", "Produto | Product", "产品 | Product"}:
            continue
        for number in italic_products or ():
            cell = ws.cell(number + 2, column.column)
            if not cell.value:
                continue
            if magazine:
                names, separator, last = cell.value.rpartition("\n")
                suffix = FORMULATION_RE.sub("", last).strip()
                if separator and (not suffix or CONCENTRATION_RE.search(suffix)):
                    cell.value = CellRichText(
                        TextBlock(InlineFont(rFont="Times New Roman", sz=9, i=True), names),
                        separator + last,
                    )
                    continue
            font = copy(cell.font)
            font.italic = True
            cell.font = font
    wb.save(path)


def export_all(
    records: list[ApprovalRecord], product_type: ProductType, translator: Translator,
    output_dir: Path, stem: str,
) -> dict[str, Path]:
    paths = {
        "pt": output_dir / f"{stem}_pt.xlsx",
        "pt_en": output_dir / f"{stem}_pt_en.xlsx",
        "cn_en": output_dir / f"{stem}_cn_en.xlsx",
        "pendencias": output_dir / f"{stem}_pendencias.json",
    }
    italic_products = {index for index, record in enumerate(records) if record.biologico}
    write_xlsx([record.operational_row(product_type) for record in records], paths["pt"], italic_products=italic_products)
    write_xlsx([translator.bilingual_row(record, product_type, "pt") for record in records], paths["pt_en"], True, italic_products)
    write_xlsx([translator.bilingual_row(record, product_type, "cn") for record in records], paths["cn_en"], True, italic_products)
    pending = {
        "termos_sem_traducao": sorted(item for item in translator.missing if item),
        "registros_com_alertas": [
            {"registro": r.registro, "marca": r.marca_comercial, "alertas": r.warnings}
            for r in records if r.warnings
        ],
    }
    paths["pendencias"].write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths
