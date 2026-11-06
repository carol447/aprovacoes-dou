from __future__ import annotations

import re
from difflib import get_close_matches

from .models import ApprovalRecord, ProductType
from .text import clean_space, key


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


FORMULATION_RE = re.compile(
    r"(?<![\w-])(?:AL|CB|CF|CG|CS|DC|DP|DS|EC|EG|EO|EW|FD|FF|FS|FT|FU|FW|GB|GE|GL|"
    r"GR|HN|LS|ME|MG|MP|OD|PA|RB|SB|SC|SE|SG|SL|SO|SP|TB|TC|TK|UL|VP|WG|WP|WS|XX)(?![\w-])",
    re.I,
)
CONCENTRATION_RE = re.compile(
    r"(?<![\w/])(?P<amount>\d+(?:[.,]\d+)*(?:\s*(?:[×x*]\s*10(?:\^\s*[+-]?\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)|e[+-]?\d+))?)"
    r"\s*(?P<unit>%|(?:g|kg|mg|µg|mL|L|UFC|UI|unidades?|indiv[ií]duos?|"
    r"con[ií]dios?|esporos?)\s*/\s*(?:g|kg|mL|L)\b)",
    re.I,
)
BIOLOGICAL_NAME_RE = re.compile(
    r"\b(?:Bacillus|Beauveria|Heterorhabditis|Metarhizium|Ooencyrtus|"
    r"Pseudomonas|Trichoderma|Thymus)\s+[a-z]+\b", re.I,
)
TWO_FOUR_D_RE = re.compile(r"\b2\s*,\s*4\s*[-–]?\s*d\b", re.I)
STRAIN_RE = re.compile(
    r"\s*,?\s*(?:(?:\b(?:cepas?|isolados?|strains?|isolates?)|(?<=[a-z])(?:cepa|isolado))\b|菌株).*?"
    rf"(?=\s*(?:{CONCENTRATION_RE.pattern}|{FORMULATION_RE.pattern}\s*(?:[+;]|$)|[+;]|$))",
    re.I,
)


def remove_product_strain(value: str) -> str:
    value = re.sub(
        rf"\s*(?:\be\b|\band\b|和)\s*(?={BIOLOGICAL_NAME_RE.pattern})",
        " + ",
        value,
        flags=re.I,
    )
    return STRAIN_RE.sub(" ", value)


def split_product_ingredients(value: str) -> list[str]:
    parts = []
    start = 0
    for match in re.finditer(rf"{CONCENTRATION_RE.pattern}|(?P<separator>[+;])", value, re.I):
        if match["separator"]:
            parts.append(value[start:match.start()].strip())
            start = match.end()
    return parts + [value[start:].strip()]


def formulated_product_from_brand(value: str, brand: str) -> str:
    """Fill missing strengths from an explicit, unambiguous DOU brand."""
    ingredients = split_product_ingredients(value)
    if not all(ingredients) or ";" in brand or all(CONCENTRATION_RE.search(part) for part in ingredients):
        return value
    brand_parts = split_product_ingredients(brand)
    strengths = [list(CONCENTRATION_RE.finditer(part)) for part in brand_parts]
    if len(strengths) != len(ingredients) or any(len(matches) != 1 for matches in strengths):
        return value
    matches_by_name = strengths
    if len(ingredients) > 1:
        brand_names = [key(part[:matches[0].start()]) for part, matches in zip(brand_parts, strengths)]
        names = [
            get_close_matches(
                key(FORMULATION_RE.sub("", CONCENTRATION_RE.sub("", ingredient))),
                brand_names, n=2, cutoff=0.75,
            )
            for ingredient in ingredients
        ]
        if any(len(name) != 1 for name in names) or len({name[0] for name in names}) != len(ingredients):
            return value
        matches_by_name = [strengths[brand_names.index(name[0])] for name in names]
    product = " + ".join(
        ingredient if CONCENTRATION_RE.search(ingredient) else f"{ingredient.rstrip('. ')} {matches[0][0]}"
        for ingredient, matches in zip(ingredients, matches_by_name)
    )
    suffix = brand_parts[-1][strengths[-1][0].end():].lstrip(" )")
    code = FORMULATION_RE.match(suffix)
    if code and not FORMULATION_RE.search(value):
        product += f" {code[0]}"
    return product


def capitalize_product(value: str) -> str:
    value = TWO_FOUR_D_RE.sub("2,4-D", value)
    return re.sub(r"[^\W\d_]", lambda match: match[0].upper(), value, count=1)


def _remove_product_description(value: str) -> str:
    if TWO_FOUR_D_RE.search(value):
        value = re.sub(rf"({FORMULATION_RE.pattern})\s+-\s+.*$", r"\1", value, flags=re.I)
        return re.sub(r"\s+-\s+Produto T[eé]cnico\s*$", "", value, flags=re.I)
    return re.sub(r"\s+-\s+.*$", "", value)


def remove_product_parentheses(value: str) -> str:
    def replace(match: re.Match) -> str:
        content = match[1]
        if re.fullmatch(rf"{CONCENTRATION_RE.pattern}(?:\s+{FORMULATION_RE.pattern})?", content, re.I):
            return f" {content} "
        formulation = FORMULATION_RE.match(content)
        if formulation and re.fullmatch(r"(?:\s*-\s*.+)?", content[formulation.end():]):
            return f" {formulation[0]} "
        if re.match(r"(?:cepa|isolado|strain|isolate)\b", content, re.I):
            return f" {content} "
        if re.match(r"(?:sal|[ée]ster|amina|dimetilamina)\b", content, re.I):
            prefix = value[:match.start()].rstrip()
            if any(name.end() == len(prefix) for name in TWO_FOUR_D_RE.finditer(prefix)):
                return f" {content} "
        return " "

    return re.sub(r"\(\s*([^()]*?)\s*\)", replace, value)


def technical_product_without_concentration(value: str) -> str:
    value = clean_space(value)
    value = remove_product_strain(remove_product_parentheses(value))
    value = CONCENTRATION_RE.sub("", value)
    value = _remove_product_description(value)
    value = re.sub(r"\s*;\s*", " + ", value)
    value = re.sub(r"\s*\+\s*", " + ", value)
    value = clean_space(value).strip(" ,;+.-").lower()
    value = capitalize_product(value)
    value = FORMULATION_RE.sub(lambda match: match[0].upper(), value)
    for strain_code in ("CCT", "IB", "IBCB", "ATCC"):
        value = re.sub(rf"\b{strain_code.lower()}\b", strain_code, value)
    return clean_space(value)


def normalize_formulated_product(value: str, brand: str = "") -> str:
    """Condensa o produto formulado no padrão editorial da revista."""
    value = clean_space(value).rstrip(".")
    value = re.sub(rf"({FORMULATION_RE.pattern})\s+-\s+.*$", r"\1", value, flags=re.I)
    value = remove_product_strain(remove_product_parentheses(value))
    value = re.sub(r"[()]", "", value)
    value = formulated_product_from_brand(value, brand)
    value = re.sub(r"\s*;\s*", " + ", value)
    value = re.sub(r"(?<!\^)(?<!\d[eE])\s*\+\s*", " + ", value)
    value = clean_space(value).strip(" ,;+.-")
    value = value.lower()
    value = capitalize_product(value)
    value = FORMULATION_RE.sub(lambda match: match[0].upper(), value)
    value = re.sub(r"\bml\b", "mL", value)
    value = re.sub(r"/(?:ml|l)\b", lambda match: "/mL" if match.group(0).lower() == "/ml" else "/L", value)
    value = re.sub(r"\bufc\b", "UFC", value)
    value = re.sub(r"\bui\b", "UI", value)
    for strain_code in ("CCT", "IB", "IBCB", "ATCC"):
        value = re.sub(rf"\b{strain_code.lower()}\b", strain_code, value)
    return clean_space(value)


def apply_business_rules(record: ApprovalRecord, product_type: ProductType) -> ApprovalRecord:
    record.registrante = normalize_registrant(record.registrante)
    brand = record.marca_comercial
    record.marca_comercial = normalize_brand(record.marca_comercial, record.registro)
    record.nota = normalize_note(record.nota)
    record.fabricante = normalize_manufacturer(record.fabricante, product_type)
    if product_type is ProductType.FORMULADO:
        record.recomendacao_uso = normalize_use(record.recomendacao_uso)
        record.produto = normalize_formulated_product(record.produto, brand)
    else:
        record.produto = technical_product_without_concentration(record.produto)
    return record
