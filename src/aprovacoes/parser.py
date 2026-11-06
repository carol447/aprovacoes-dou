from __future__ import annotations

import re

from .models import ApprovalRecord, ProductType
from .rules import BIOLOGICAL_NAME_RE
from .text import clean_space, preserve_tc_registry


LABELS = {
    "titular": r"(?:Titular\s+do\s+registro|Nome\s+do\s+requerente\s+ou\s+titular)",
    "marca": r"Marca\s+comercial",
    "fabricante_tecnico": r"Fabricantes?\s+do\s+Produto\s+t[eé]cnico(?:\s*\([^:\n]*\))?",
    "fabricante": r"Fabricantes?(?:\(s\))?(?:\s+e\s+formulador(?:es)?(?:\(es\))?)?(?:\s*/\s*(?:Formulador(?:es)?(?:\s*/\s*Manipulador(?:es)?)?|Manipulador(?:es)?))?",
    "uso": r"Indica[cç][aã]o\s+de\s+uso(?:\s+aprovada)?",
    "produto": r"Nomes?\s+(?:comum|comuns)",
    "cientifico": r"Nome\s+cient[ií]fico(?:,\s*no\s+caso\s+de\s+agente\s+biol[oó]gico)?",
    "tox": r"Classifica[cç][aã]o\s+toxicol[oó]gica",
    "amb": r"Classifica[cç][aã]o\s+(?:quanto\s+ao|do)\s+potencial\s+de\s+periculosidade\s+ambiental",
}


def normalize_dou_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def detect_product_type(text: str) -> ProductType | None:
    intro = clean_space(normalize_dou_text(text)[:2500]).casefold()
    if re.search(r"produtos?\s+t[eé]cnicos?\s+e\s+pr[eé]-misturas", intro):
        return ProductType.TECNICO
    if re.search(r"registros?\s+de\s+produtos?\s+formulados", intro):
        return ProductType.FORMULADO
    if re.search(r"registros?\s+de\s+agrot[oó]xicos?\s+e\s+afins\s+concedidos", intro):
        return ProductType.FORMULADO
    return None


def split_blocks(text: str) -> list[str]:
    text = normalize_dou_text(text)
    item_start = r"\d+\s*(?:(?:\.\s*)?-\s*)?a\s*[.)]\s*"
    blocks = re.split(rf"(?m)^\s*{item_start}", text)
    if len(blocks) > 1:
        return [block.strip() for block in blocks[1:] if block.strip()]
    # Reserva para textos copiados do HTML que perderam a quebra antes de "n-a."
    blocks = re.split(rf"\s+{item_start}", text)
    return [block.strip() for block in blocks[1:] if block.strip()]


def field(block: str, label: str) -> str:
    pattern = LABELS[label]
    match = re.search(
        rf"(?:^|\n)\s*[a-z]\s*[.)]\s*{pattern}\s*:[ \t]*(.*?)"
        rf"(?=\n\s*[a-z]\s*[.)]\s*|\s+[a-l]\)\s*(?=[A-ZÀ-Ý])|\Z)",
        block,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        match = re.search(
            rf"{pattern}\s*:[ \t]*(.*?)(?=\n\s*[a-z]\s*[.)]\s*|\s+[a-l]\)\s*(?=[A-ZÀ-Ý])|\Z)",
            block,
            re.IGNORECASE | re.DOTALL,
        )
    return clean_space(match.group(1)) if match else ""


def extract_registry(block: str, product_type: ProductType) -> str:
    if product_type is ProductType.TECNICO:
        return preserve_tc_registry(block)
    match = re.search(r"registro\s+n[ºo°]?\s*([0-9][0-9./-]*)", block, re.IGNORECASE)
    return re.sub(r"\D", "", match.group(1)) if match else ""


def parse(text: str, product_type: ProductType) -> list[ApprovalRecord]:
    records: list[ApprovalRecord] = []
    for index, block in enumerate(split_blocks(text), start=1):
        registro = extract_registry(block, product_type)
        fabricante_label = "fabricante_tecnico" if product_type is ProductType.FORMULADO else "fabricante"
        fabricante = field(block, fabricante_label)
        if product_type is ProductType.FORMULADO and not fabricante:
            fabricante = field(block, "fabricante")
        cientifico = field(block, "cientifico")
        nome_biologico = BIOLOGICAL_NAME_RE.search(cientifico) or re.match(
            r"^[^\W\d_]+\s+(?!(?:da|das|de|do|dos|se)\b)[^\W\d_]+", cientifico, re.I
        )
        produto = field(block, "produto")
        if not produto or clean_space(produto).casefold().rstrip(" .") == "não se aplica":
            produto = cientifico
        record = ApprovalRecord(
            registrante=field(block, "titular"),
            marca_comercial=field(block, "marca"),
            recomendacao_uso=field(block, "uso") if product_type is ProductType.FORMULADO else "",
            fabricante=fabricante,
            produto=produto,
            registro=registro,
            source_index=index,
            biologico=bool(nome_biologico),
        )
        tox, amb = field(block, "tox"), field(block, "amb")
        record.nota = " | ".join(part for part in (tox, amb) if part)
        for name in ("registrante", "marca_comercial", "fabricante", "registro"):
            if not getattr(record, name):
                record.warnings.append(f"campo ausente: {name}")
        records.append(record)
    # Algumas páginas do DOU mantêm duas cópias responsivas do mesmo ato no
    # texto renderizado. A revista deve conter cada registro uma única vez.
    unique: list[ApprovalRecord] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        key = (
            record.registro.casefold(),
            record.marca_comercial.casefold(),
            record.produto.casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)

    # Corrige omissões tipográficas do número TC somente quando os vizinhos
    # provam uma sequência consecutiva com o mesmo sufixo de ano.
    if product_type is ProductType.TECNICO:
        for index in range(1, len(unique) - 1):
            if unique[index].registro:
                continue
            previous = re.fullmatch(r"TC(\d+)(\d{2})", unique[index - 1].registro)
            following = re.fullmatch(r"TC(\d+)(\d{2})", unique[index + 1].registro)
            if not previous or not following or previous.group(2) != following.group(2):
                continue
            before, after = int(previous.group(1)), int(following.group(1))
            if after == before + 2:
                unique[index].registro = f"TC{before + 1}{previous.group(2)}"
                unique[index].warnings = [
                    warning for warning in unique[index].warnings
                    if warning != "campo ausente: registro"
                ]
                unique[index].warnings.append("registro inferido pela sequência do ato")
    return unique
