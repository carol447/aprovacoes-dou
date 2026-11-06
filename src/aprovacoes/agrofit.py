from __future__ import annotations

import csv
import io
from pathlib import Path
from urllib.request import Request, urlopen

from .models import ApprovalRecord, ProductType
from .rules import (
    CONCENTRATION_RE, FORMULATION_RE, STEREOCHEMISTRY_RE, fill_product_concentrations,
    normalize_formulated_product, technical_product_without_concentration,
)
from .text import clean_space, key, registry_key


FORMULATED_URL = "https://dados.agricultura.gov.br/dataset/6c913699-e82e-4da3-a0a1-fb6c431e367f/resource/d30b30d7-e256-484e-9ab8-cd40974e1238/download/agrofitprodutosformulados.csv"
TECHNICAL_URL = "https://dados.agricultura.gov.br/dataset/6c913699-e82e-4da3-a0a1-fb6c431e367f/resource/a200c70b-e025-4a9a-be1b-ec7275d7921f/download/agrofitprodutostecnicos.csv"


def download_database(product_type: ProductType, cache_dir: Path, timeout: int = 45) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"agrofit_{product_type.value}.csv"
    url = FORMULATED_URL if product_type is ProductType.FORMULADO else TECHNICAL_URL
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout) as response:
        target.write_bytes(response.read())
    return target


def _rows(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "latin1"):
        try:
            text = raw.decode(encoding)
            return list(csv.DictReader(io.StringIO(text), delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Não foi possível decodificar {path}")


def enrich(records: list[ApprovalRecord], product_type: ProductType, csv_path: Path) -> None:
    rows = _rows(csv_path)
    registry_column = "NR_REGISTRO" if product_type is ProductType.FORMULADO else "NUMERO_REGISTRO"
    product_column = "INGREDIENTE_ATIVO" if product_type is ProductType.FORMULADO else "INGREDIENTE_ATIVO(GRUPO_QUIMICI)(CONCENTRACAO)"
    formulation_column = "FORMULACAO"
    index = {registry_key(row.get(registry_column, "")): row for row in rows if registry_key(row.get(registry_column, ""))}
    for record in records:
        row = index.get(registry_key(record.registro))
        if not row:
            record.warnings.append("registro não encontrado no Agrofit")
            continue
        product = clean_space(row.get(product_column, ""))
        category = key(row.get("CLASSE", ""))
        record.biologico |= "biologico" in category
        if not product:
            continue
        if product_type is ProductType.FORMULADO:
            formulation = clean_space(row.get(formulation_column, ""))
            codes = FORMULATION_RE.findall(formulation.split(" - ", 1)[0])
            preserve_dou_name = STEREOCHEMISTRY_RE.search(record.produto) and not STEREOCHEMISTRY_RE.search(product)
            if CONCENTRATION_RE.search(record.produto) or preserve_dou_name:
                if not codes:
                    codes = FORMULATION_RE.findall(product)
                product = fill_product_concentrations(record.produto, normalize_formulated_product(product))
            record.produto = clean_space(f"{product} {' '.join(codes)}")
        else:
            record.produto = technical_product_without_concentration(product)
