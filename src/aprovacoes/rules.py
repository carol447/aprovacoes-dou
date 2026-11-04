from __future__ import annotations

import re

from .models import ApprovalRecord, ProductType
from .text import clean_space


REGISTRANT_EXCEPTIONS = {
    "AGRO": "AGROIMPORT",
    "AGROIMPORT": "AGROIMPORT",
    "BEM": "BEM BRASIL",
    "BOM": "BOM FUTURO",
    "OURO": "OURO FINO",
    "SIPCAM": "SIPCAM NICHINO",
    "SM": "SM AGROCARE",
}

TOX = {
    "produto nao classificado": "Não classificado",
    "produto improvavel de causar dano agudo": "Improvável de causar dano agudo",
    "produto pouco toxico": "Pouco tóxico",
    "produto moderadamente toxico": "Moderadamente tóxico",
    "produto altamente toxico": "Altamente tóxico",
    "o perfil toxicologico foi considerado equivalente ao produto tecnico de referencia": "Equivalente",
}

ENV = {
    "produto altamente perigoso ao meio ambiente": "Altamente perigoso",
    "produto muito perigoso ao meio ambiente": "Muito perigoso",
    "produto perigoso ao meio ambiente": "Perigoso",
    "produto pouco perigoso ao meio ambiente": "Pouco perigoso",
    "altamente perigoso ao meio ambiente": "Altamente perigoso",
    "muito perigoso ao meio ambiente": "Muito perigoso",
    "pouco perigoso ao meio ambiente": "Pouco perigoso",
    "perigoso ao meio ambiente": "Perigoso",
}


def strip_accents_key(text: str) -> str:
    from .text import key
    return key(text)


def normalize_registrant(value: str) -> str:
    value = clean_space(value).upper()
    value = re.sub(r"\s+-\s+(?:CNPJ|[A-ZÀ-Ý].*)$", "", value)
    first = re.sub(r"[^A-Z0-9]", "", value.split()[0]) if value else ""
    return REGISTRANT_EXCEPTIONS.get(first, first)


def normalize_brand(value: str, registry: str) -> str:
    brand = clean_space(value).rstrip(".").upper()
    brand = re.sub(r"\s*\([^)]*\)\s*$", "", brand).strip()
    return f"{brand} ({registry})" if brand and registry else brand


def normalize_use(value: str) -> str:
    value = clean_space(value).rstrip(".")
    value = re.split(r"\s+(?:[a-z]\s*\.\s*)?Classifica[cç][aã]o\s+toxicol[oó]gica\s*:", value, maxsplit=1, flags=re.I)[0]
    value = re.sub(r"^(?:Indica[cç][aã]o\s+de\s+uso\s*:\s*)+", "", value, flags=re.I)
    value = re.sub(r"^(?:Indicado\s+)?em\s+todas\s+as\s+culturas\s+com\s+ocorr[eê]ncia\s+dos?\s+alvos?\s+biol[oó]gicos?\s*", "Indicado para qualquer cultura com ocorrência dos alvos biológicos ", value, flags=re.I)
    value = re.sub(r"^Em\s+qualquer\s+cultura\s+com\s+a\s+ocorr[eê]ncia\s+dos?\s+alvos?\s+biol[oó]gicos?\s*", "Indicado para qualquer cultura com ocorrência dos alvos biológicos ", value, flags=re.I)
    value = re.sub(r"alvos?\s+biol[oó]gicos?(?=[A-ZÀ-Ý])", "alvos biológicos ", value, flags=re.I)
    value = re.sub(r"\bbiol[oó]gicos?\s+s\s+", "biológicos ", value, flags=re.I)
    value = re.sub(r"^Indicado\s+(?:nas|as)\s+culturas?\s+(?:de\s+)?", "", value, flags=re.I)
    value = re.sub(r"^Indicado\s+(?:para\s+)?as?\s+culturas?\s+d(?:e|a|o)\s+", "", value, flags=re.I)
    value = re.sub(r"^N(?:a|as)\s+culturas?\s*(?:de|da|do)?\s*", "", value, flags=re.I)
    if re.match(r"^Cigarrinha", value, re.I):
        value = "Indicado para qualquer cultura com ocorrência dos alvos biológicos " + value
    value = re.sub(r"([a-zà-ÿ])e(?=[A-ZÀ-Ý])", r"\1, ", value)
    for source, target in {
        "clerotinia sclerotiorum": "Sclerotinia sclerotiorum",
        "phenophorus levis": "Sphenophorus levis",
        "Plutellaxylostella": "Plutella xylostella",
        "tabaciraça": "tabaci raça",
    }.items():
        value = re.sub(re.escape(source), target, value, flags=re.I)
    value = re.sub(r"([a-z])\(", r"\1 (", value)
    # Pequenas omissões de vírgula presentes no texto do DOU.
    for source, target in {
        "Algodão feijão": "Algodão, feijão",
        "Algodão milho soja": "Algodão, milho, soja",
        "Algodão cana-de-açúcar": "Algodão, cana-de-açúcar",
        "Feijão soja": "Feijão, soja",
        "Milho soja trigo": "Milho, soja, trigo",
        "eucalipto pinus": "eucalipto, pinus",
        "Batata Duboisia": "Batata, Duboisia",
        "cana-açúcar": "cana-de-açúcar",
        "grão-debico": "grão-de-bico",
    }.items():
        value = re.sub(rf"\b{re.escape(source)}\b", target, value, flags=re.I)
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r",\s*(?:e|ou)\s+", ", ", value, flags=re.I)
    value = re.sub(r"\s+(?:e|ou)\s+(?=[^,]+$)", ", ", value, flags=re.I)
    if value and not re.match(r"^Indicado para qualquer cultura", value, re.I):
        value = value[0].upper() + value[1:]
    return value


def _category(text: str) -> str:
    match = re.search(r"(?:Categoria|Classe)\s*([1-5IVX]+)", text, re.I)
    return match.group(1).upper() if match else ""


def normalize_note(value: str) -> str:
    value = clean_space(value)
    if re.match(r"^(?:Clas\.\s*tox\.|Não classificado\b)", value, re.I):
        return value.rstrip(".") + "."
    parts = re.split(r"\s*\|\s*", value, maxsplit=1)
    tox_raw = parts[0] if parts else ""
    env_raw = parts[1] if len(parts) > 1 else ""
    tox_text = next((v for k, v in TOX.items() if k in strip_accents_key(tox_raw)), clean_space(tox_raw))
    env_text = next((v for k, v in ENV.items() if k in strip_accents_key(env_raw)), clean_space(env_raw))
    tox_cat, env_cat = _category(tox_raw), _category(env_raw)
    tox = "Não classificado" if tox_text == "Não classificado" else f"Clas. tox. {tox_cat} - {tox_text}".replace("  ", " ")
    env = f"Clas. amb. {env_cat} - {env_text}".replace("  ", " ") if env_text else ""
    return ". ".join(item.strip(" .-") for item in (tox, env) if item).strip() + "."


def normalize_manufacturer(value: str, product_type: ProductType) -> str:
    value = clean_space(value)
    value = re.split(r"\s*\*\s*N[aã]o\b", value, maxsplit=1, flags=re.I)[0]
    # Notas administrativas do DOU não integram a coluna de fabricante da revista.
    value = re.split(
        r"\s+(?=(?:LICENÇA DE PRODUÇÃO|REGISTRO NO PAÍS DE ORIGEM|"
        r"\(\d+\)\s*Fabricante|\*\s*Fabricante\b|\*\s*O endereço\b|"
        r"\*\s*N[aã]o\b|"
        r"O endereço do fabricante\b))",
        value,
        maxsplit=1,
        flags=re.I,
    )[0]
    value = re.sub(r"Fabricante\s+do\s+Produto\s+t[eé]cnico\s*:\s*", "", value, flags=re.I)
    value = re.sub(r"\bCNPJ\s*:\s*[\d./-]+", "", value, flags=re.I)
    value = re.sub(r"\bCEP\s*[:.]?\s*[\d.-]+", "", value, flags=re.I)
    value = re.sub(r"(?:\bNome\s*:\s*)+", "", value, flags=re.I)
    value = re.sub(r"\bEndere[cç]o\s*:\s*", " - ", value, flags=re.I)
    value = re.sub(r"Produto\s+t[eé]cnico\s*:\s*([^:;]+)\s*:\s*", r"(\1) ", value, flags=re.I)
    value = re.sub(r";\s*-\s*", " - ", value)
    value = re.sub(r"\s*;\s*", "; ", value)
    value = re.sub(r"\s*-\s*-\s*", " - ", value)
    value = re.sub(r"\.\s*-\s*-\s*", ". - ", value)
    # Padrão editorial da revista para endereços internacionais: remove
    # qualificadores de logradouro/localidade e abrevia termos empresariais.
    abbreviations = {
        r"\bBiotechnology\b": "Biotech.",
        r"\bEcological\b": "Eco.",
        r"\bChemical\b": "Chem.",
        r"\bTechnology\b": "Tech.",
        r"\bIndustrial\b": "Ind.",
        r"\bIndustry\b": "Ind.",
        r"\blndustry\b": "Ind.",
    }
    for pattern, replacement in abbreviations.items():
        value = re.sub(pattern, replacement, value, flags=re.I)
    value = re.sub(r"\b(?:Chemial|Chenlical)\b", "Chem.", value, flags=re.I)
    value = re.sub(r"\bDistrict\s+office\s+of\s+([^,(]+)", r"\1 Office", value, flags=re.I)
    value = re.sub(
        r"\s*\b(?:Road|Rd\.?|Rodovia|Rod\.?|Rua|Street|St\.?|Avenida|Av\.?|"
        r"Avenue|Highway|Hwy\.?|Lane|Ln\.?|Boulevard|Blvd\.?|Route|Rte\.?|"
        r"Estrada|Travessa|Alameda|Village|Vila|Town|District|County|Country|"
        r"City|Province)\b\s*",
        ", ",
        value,
        flags=re.I,
    )
    value = re.sub(r"\(\s*salt\s+Chem\.\s+Ind\.\s*,?\s*\)", "(Salt Chem. Ind.)", value, flags=re.I)
    value = re.sub(r"\b(?:No\.|N\s*[º°])\s*", "", value, flags=re.I)
    value = re.sub(r"\bBase\s+(?=[A-Z])", "Base, ", value)
    value = re.sub(r"\bChem\.\s+Ind\.\s*-\s*", "Chem. Ind., ", value, flags=re.I)
    value = re.sub(r"\bLtd\.\*", "Ltd.", value, flags=re.I)
    value = re.sub(r"\bBase,\s*Qingdao\s+Pingdu\b", "Base, Pingdu", value, flags=re.I)
    value = re.sub(r"\s*-\s*China\b", ", China", value, flags=re.I)
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",\s*,+", ",", value)
    value = re.sub(r"\s{2,}", " ", value)
    return clean_space(value).strip(" .;-")


def technical_product_without_concentration(value: str) -> str:
    value = clean_space(value)
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:g|kg|mg|mL|L|UFC|UI|unidades?)\s*/\s*(?:g|kg|mL|L)\b", "", value, flags=re.I)
    value = re.sub(r"\b\d+(?:[.,]\d+)?\s*%", "", value)
    value = re.sub(r"\s+-\s+.*$", "", value)
    value = re.sub(r"\s*;\s*", " + ", value)
    value = re.sub(r"\s*\+\s*", " + ", value)
    value = clean_space(value).strip(" ,;+.-").lower()
    if value:
        value = value[0].upper() + value[1:]
    for code in ("TC", "TK", "MP", "SC", "SL", "EC", "WG", "WP", "CS", "OD", "FS", "EW", "GR", "ME", "SP", "SG", "SE", "UL"):
        value = re.sub(rf"\b{code.lower()}\b", code, value)
    for strain_code in ("CCT", "IB", "IBCB", "ATCC"):
        value = re.sub(rf"\b{strain_code.lower()}\b", strain_code, value)
    return clean_space(value)


def normalize_formulated_product(value: str) -> str:
    """Condensa o produto formulado no padrão editorial da revista."""
    value = clean_space(value).rstrip(".")
    value = re.sub(r"\s+-\s+.*$", "", value)
    concentration = (
        r"\d+(?:[.,]\d+)?\s*(?:g|kg|mg|mL|L|UFC|UI|unidades?|indiv[ií]duos?)"
        r"\s*/\s*(?:g|kg|mL|L)"
    )
    value = re.sub(rf"\(\s*({concentration})\s*\)", r" \1 ", value, flags=re.I)
    value = re.sub(r"\(\s*(\d+(?:[.,]\d+)?\s*%)\s*\)", r" \1 ", value)
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"[()]", "", value)
    value = re.sub(r"\s*;\s*", " + ", value)
    value = re.sub(r"\s*\+\s*", " + ", value)
    value = clean_space(value).strip(" ,;+.-")
    value = value.lower()
    if value:
        value = value[0].upper() + value[1:]
    for code in ("SC", "SL", "EC", "WG", "WP", "CS", "OD", "FS", "EW", "GR", "ME", "SP", "SG", "SE", "UL"):
        value = re.sub(rf"\b{code.lower()}\b", code, value)
    value = re.sub(r"\bml\b", "mL", value)
    value = re.sub(r"/(?:ml|l)\b", lambda match: "/mL" if match.group(0).lower() == "/ml" else "/L", value)
    value = re.sub(r"\bufc\b", "UFC", value)
    value = re.sub(r"\bui\b", "UI", value)
    for strain_code in ("CCT", "IB", "IBCB", "ATCC"):
        value = re.sub(rf"\b{strain_code.lower()}\b", strain_code, value)
    return clean_space(value)


def apply_business_rules(record: ApprovalRecord, product_type: ProductType) -> ApprovalRecord:
    record.registrante = normalize_registrant(record.registrante)
    record.marca_comercial = normalize_brand(record.marca_comercial, record.registro)
    record.nota = normalize_note(record.nota)
    record.fabricante = normalize_manufacturer(record.fabricante, product_type)
    if product_type is ProductType.FORMULADO:
        record.recomendacao_uso = normalize_use(record.recomendacao_uso)
        record.produto = normalize_formulated_product(record.produto)
    else:
        record.produto = technical_product_without_concentration(record.produto)
    return record
