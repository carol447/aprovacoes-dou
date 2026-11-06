from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .agrofit import download_database, enrich
from .export import biological_rows, write_xlsx
from .models import ApprovalRecord, ProductType
from .parser import detect_product_type, parse
from .rules import (
    CONCENTRATION_RE, FORMULATION_RE, apply_business_rules, capitalize_product,
    formulated_product_from_brand, normalize_formulated_product, remove_product_parentheses, remove_product_strain,
    split_product_ingredients,
    technical_product_without_concentration,
)
from .text import clean_space
from .translations import Translator


FORMULATED_CONTROL_COLUMNS = [
    "registrante", "marca_comercial", "recomendacao_uso_pt", "recomendacao_uso_en",
    "recomendacao_uso_cn", "nota_pt", "nota_en", "nota_cn", "fabricante_produto",
    "produto_pt", "produto_en", "produto_cn", "registro", "formulacao",
]

TECHNICAL_CONTROL_COLUMNS = [
    "registrante", "marca_comercial", "nota_pt", "nota_en", "nota_cn",
    "fabricante", "produto_pt", "produto_en", "produto_cn",
]


def _validate_type(text: str, product_type: ProductType) -> None:
    detected = detect_product_type(text)
    if detected is not None and detected is not product_type:
        raise ValueError(
            f"O primeiro parágrafo indica '{detected.value}', mas foi escolhido "
            f"'{product_type.value}'. Revise a seleção."
        )


def extract_act(
    text: str,
    product_type: ProductType,
    output_path: Path,
    agrofit_csv: Path | None = None,
    download_agrofit: bool = True,
) -> Path:
    _validate_type(text, product_type)
    records = parse(text, product_type)
    if not records:
        raise ValueError("Nenhum bloco de registro foi encontrado no ato")
    if agrofit_csv is None and download_agrofit:
        agrofit_csv = download_database(product_type, output_path.parent / "cache")
    if agrofit_csv is not None:
        enrich(records, product_type, agrofit_csv)
    records = [apply_business_rules(record, product_type) for record in records]
    write_xlsx(
        [record.operational_row(product_type) for record in records], output_path,
        italic_products={index for index, record in enumerate(records) if record.biologico},
    )
    return output_path


def _control_from_operational(input_path: Path, product_type: ProductType) -> pd.DataFrame:
    source = pd.read_excel(input_path, dtype=str).fillna("")
    if product_type is ProductType.FORMULADO:
        required = [
            "Registrante", "Marca comercial", "Recomendação de Uso", "Nota",
            "Fabricante do produto técnico", "Produto", "Registro",
        ]
        missing = [column for column in required if column not in source.columns]
        if missing:
            raise ValueError(f"Cabeçalhos ausentes no arquivo formulado: {missing}")
        control = pd.DataFrame({
            "registrante": source["Registrante"],
            "marca_comercial": source["Marca comercial"],
            "recomendacao_uso_pt": source["Recomendação de Uso"],
            "recomendacao_uso_en": "",
            "recomendacao_uso_cn": "",
            "nota_pt": source["Nota"],
            "nota_en": "",
            "nota_cn": "",
            "fabricante_produto": source["Fabricante do produto técnico"],
            "produto_pt": [
                normalize_formulated_product(product, brand)
                for product, brand in zip(source["Produto"], source["Marca comercial"])
            ],
            "produto_en": "",
            "produto_cn": "",
            "registro": source["Registro"],
            "formulacao": source["Formulação"] if "Formulação" in source.columns else "",
        })
        return control[FORMULATED_CONTROL_COLUMNS]
    required = ["Registrante", "Marca comercial", "Nota", "Fabricante", "Produto"]
    missing = [column for column in required if column not in source.columns]
    if missing:
        raise ValueError(f"Cabeçalhos ausentes no arquivo técnico: {missing}")
    control = pd.DataFrame({
        "registrante": source["Registrante"], "marca_comercial": source["Marca comercial"],
        "nota_pt": source["Nota"], "nota_en": "", "nota_cn": "",
        "fabricante": source["Fabricante"],
        "produto_pt": source["Produto"].map(technical_product_without_concentration),
        "produto_en": "", "produto_cn": "",
    })
    return control[TECHNICAL_CONTROL_COLUMNS]


def translate_extraction(
    input_path: Path,
    product_type: ProductType,
    dictionary_path: Path,
    output_path: Path,
    online_fallback: bool = True,
) -> tuple[Path, Path]:
    control = _control_from_operational(input_path, product_type)
    translator = Translator(dictionary_path, online_fallback=online_fallback)
    control["produto_en"] = control["produto_pt"].map(lambda value: translator.product(value, "en", product_type))
    control["produto_cn"] = control["produto_pt"].map(lambda value: translator.product(value, "cn", product_type))
    control["nota_en"] = control["nota_pt"].map(lambda value: translator.note(value, "en"))
    control["nota_cn"] = control["nota_pt"].map(lambda value: translator.note(value, "cn"))
    if product_type is ProductType.FORMULADO:
        control["recomendacao_uso_en"] = control["recomendacao_uso_pt"].map(lambda value: translator.use(value, "en"))
        control["recomendacao_uso_cn"] = control["recomendacao_uso_pt"].map(lambda value: translator.use(value, "cn"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_xlsx(control, output_path, italic_products=biological_rows(input_path, "Produto"))
    pending_path = output_path.with_name(f"{output_path.stem}_pendencias.json")
    pending = {"termos_sem_traducao": sorted(item for item in translator.missing if item)}
    if product_type is ProductType.FORMULADO:
        pending["formulados_sem_concentracao"] = [
            {"registro": row.registro, "marca": row.marca_comercial}
            for row in control.itertuples()
            if any(not CONCENTRATION_RE.search(part) for part in split_product_ingredients(row.produto_pt))
        ]
    pending_path.write_text(
        json.dumps(pending, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path, pending_path


def _product_parts(value: str, formulation_field: str = "") -> tuple[list[str], str]:
    value = remove_product_strain(remove_product_parentheses(clean_space(value)))
    concentrations = list(CONCENTRATION_RE.finditer(value))
    formulations = FORMULATION_RE.findall(value) or FORMULATION_RE.findall(formulation_field)
    formulation = " ".join(dict.fromkeys(code.upper() for code in formulations))
    names = CONCENTRATION_RE.sub("", value)
    names = re.sub(rf"\s+{FORMULATION_RE.pattern}\s+-\s+.*$", "", names, flags=re.I)
    names = FORMULATION_RE.sub("", names)
    names = re.sub(
        r"\s*-\s*(?:Suspo-Emuls[aã]o|Concentrado Emulsion[aá]vel|P[oó] Molh[aá]vel|"
        r"Suspens[aã]o Concentrada(?:\s+p/\s*Trat\.\s*Sementes)?|Dispers[aã]o de [oó]leo|"
        r"Concentrado Sol[uú]vel|Insetos Vivos)\s*$",
        "",
        names,
        flags=re.I,
    )
    names = re.sub(r"\s+(?:Insetos|[ÁA]caros|Nemat[oó]ides)\s+vivos\s*$", "", names, flags=re.I)
    parts = [clean_space(part).strip(" ,;+-") for part in re.split(r"\s*(?:\+|;)\s*", names)]
    concentration_line = ""
    if concentrations:
        units = [re.sub(r"\s*/\s*", "/", match["unit"].lower()) for match in concentrations]
        units = [
            re.sub(r"\b(?:ml|l|ufc|ui)\b", lambda part: {"ml": "mL"}.get(part[0], part[0].upper()), unit)
            for unit in units
        ]
        amounts = [match["amount"] for match in concentrations]
        if len(set(unit.casefold() for unit in units)) == 1:
            concentration_line = " + ".join(amounts) + f" {units[-1]}"
        else:
            concentration_line = " + ".join(f"{amount} {unit}" for amount, unit in zip(amounts, units))
    return [part for part in parts if part], clean_space(f"{concentration_line} {formulation}")


def _formatted_product(row: pd.Series, language: str, product_type: ProductType) -> str:
    pt = clean_space(row["produto_pt"])
    first = pt if language == "en" else clean_space(row["produto_cn"])
    second = clean_space(row["produto_en"])
    if product_type is ProductType.TECNICO:
        return (
            f"{technical_product_without_concentration(first)}\n"
            f"{technical_product_without_concentration(second)}"
        )
    pt = formulated_product_from_brand(pt, clean_space(row.get("marca_comercial", "")))
    formulation = clean_space(row.get("formulacao", "")) or f"{first} {second}"
    pt_parts, final_line = _product_parts(pt, formulation)
    first_parts = pt_parts if language == "en" else _product_parts(first)[0]
    second_parts = _product_parts(second)[0]
    if len(pt_parts) <= 1:
        return "\n".join(filter(None, [
            capitalize_product(" + ".join(first_parts)),
            capitalize_product(" + ".join(second_parts)),
            final_line,
        ]))
    first_line = capitalize_product(" + ".join(first_parts))
    second_line = capitalize_product(" +\n".join(second_parts))
    return "\n\n".join(filter(None, [first_line, second_line, final_line]))


def _brand_for_magazine(value: str, separate_registration: bool) -> str:
    value = clean_space(value)
    if separate_registration:
        return re.sub(r"\s+(\([^)]*\))$", r"\n\1", value)
    return value


def create_magazine_layouts(
    translated_control: Path,
    product_type: ProductType,
    output_dir: Path,
    stem: str,
) -> dict[str, Path]:
    df = pd.read_excel(translated_control, dtype=str).fillna("")
    output_dir.mkdir(parents=True, exist_ok=True)
    if product_type is ProductType.FORMULADO:
        pt_rows, cn_rows = [], []
        for _, row in df.iterrows():
            pt_rows.append({
                "Registrante\nRegistrant": row["registrante"],
                "Marca comercial\n(Registro)\nBrand Name\n(Registration)": _brand_for_magazine(row["marca_comercial"], True),
                "Recomendação de Uso\nUse Recommendation": f'{row["recomendacao_uso_pt"]}\n{row["recomendacao_uso_en"]}',
                "Nota | Note": f'{row["nota_pt"]}\n{row["nota_en"]}',
                "Fabricante do produto técnico\nManufacturer of Technical Product": row["fabricante_produto"],
                "Produto | Product": _formatted_product(row, "en", product_type),
            })
            cn_rows.append({
                "登记持有人\nRegistrant": row["registrante"],
                "商品名(注册号)\nBrand Name\n(Registration)": _brand_for_magazine(row["marca_comercial"], True),
                "建议使用\nUse Recommendation": f'{row["recomendacao_uso_cn"]}\n{row["recomendacao_uso_en"]}',
                "笔记 | Note": f'{row["nota_cn"]}\n{row["nota_en"]}',
                "原药生产商\nManufacturer of\nTechnical Product": row["fabricante_produto"],
                "产品 | Product": _formatted_product(row, "cn", product_type),
            })
    else:
        pt_rows, cn_rows = [], []
        for _, row in df.iterrows():
            pt_rows.append({
                "Registrante\nRegistrant": row["registrante"],
                "Marca comercial (Registro)\nBrand Name (Registration)": row["marca_comercial"],
                "Nota | Note": f'{row["nota_pt"]}\n{row["nota_en"]}',
                "Fabricante\nManufacturer": row["fabricante"],
                "Produto | Product": _formatted_product(row, "en", product_type),
            })
            cn_rows.append({
                "登记持有人\nRegistrant": row["registrante"],
                "商品名(注册号)\nBrand Name (Registration)": row["marca_comercial"],
                "笔记 | Note": f'{row["nota_cn"]}\n{row["nota_en"]}',
                "生产商\nManufacturer": row["fabricante"],
                "产品 | Product": _formatted_product(row, "cn", product_type),
            })
    paths = {"pt_en": output_dir / f"{stem}_pt_en.xlsx", "cn_en": output_dir / f"{stem}_cn_en.xlsx"}
    italic_products = biological_rows(translated_control, "produto_pt")
    write_xlsx(pt_rows, paths["pt_en"], magazine=True, italic_products=italic_products)
    write_xlsx(cn_rows, paths["cn_en"], magazine=True, italic_products=italic_products)
    return paths
