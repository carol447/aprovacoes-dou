from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Side, Border

from .models import ApprovalRecord, ProductType
from .translations import Translator


def write_xlsx(rows: list[dict[str, str]], path: Path, magazine: bool = False) -> None:
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
    write_xlsx([record.operational_row(product_type) for record in records], paths["pt"])
    write_xlsx([translator.bilingual_row(record, product_type, "pt") for record in records], paths["pt_en"], True)
    write_xlsx([translator.bilingual_row(record, product_type, "cn") for record in records], paths["cn_en"], True)
    pending = {
        "termos_sem_traducao": sorted(item for item in translator.missing if item),
        "registros_com_alertas": [
            {"registro": r.registro, "marca": r.marca_comercial, "alertas": r.warnings}
            for r in records if r.warnings
        ],
    }
    paths["pendencias"].write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths
