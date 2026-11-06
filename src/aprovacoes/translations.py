from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .models import ApprovalRecord, ProductType
from .rules import (
    BIOLOGICAL_NAME_RE, CONCENTRATION_RE, FORMULATION_RE, TWO_FOUR_D_RE,
    capitalize_product, remove_product_parentheses, remove_product_strain,
)
from .text import clean_space, key


CROPS = {
    "abacate": ("avocado", "鳄梨"), "abacaxi": ("pineapple", "菠萝"),
    "algodao": ("cotton", "棉花"), "algodao ogm": ("GMO cotton", "转基因棉花"),
    "alho": ("garlic", "大蒜"), "ameixa": ("plum", "李子"),
    "amendoim": ("peanut", "花生"), "arroz": ("rice", "水稻"),
    "arroz irrigado": ("irrigated rice", "灌溉水稻"), "aveia": ("oat", "燕麦"),
    "arroz sequeiro": ("upland rice", "旱稻"),
    "culturas do abacate": ("avocado crops", "鳄梨作物"),
    "palma forrageira": ("forage cactus", "饲用仙人掌"),
    "pinhao manso": ("physic nut", "麻疯树"),
    "alem de combate a gafanhotos": ("also for grasshopper control", "也用于防治蝗虫"),
    "banana": ("banana", "香蕉"), "batata": ("potato", "马铃薯"),
    "cafe": ("coffee", "咖啡"), "cana de acucar": ("sugarcane", "甘蔗"),
    "cebola": ("onion", "洋葱"), "cevada": ("barley", "大麦"),
    "citros": ("citrus", "柑橘"), "coco": ("coconut", "椰子"),
    "eucalipto": ("eucalyptus", "桉树"), "feijao": ("bean", "菜豆"),
    "fumo": ("tobacco", "烟草"), "girassol": ("sunflower", "向日葵"),
    "maca": ("apple", "苹果"), "mamao": ("papaya", "木瓜"),
    "mandioca": ("cassava", "木薯"), "melao": ("melon", "甜瓜"),
    "melancia": ("watermelon", "西瓜"), "milho": ("corn", "玉米"),
    "milho ogm": ("GMO corn", "转基因玉米"), "pastagem": ("pasture", "牧场"),
    "pera": ("pear", "梨"), "pessego": ("peach", "桃"),
    "pinus": ("pine", "松树"), "soja": ("soybean", "大豆"),
    "soja ogm": ("GMO soybean", "转基因大豆"), "sorgo": ("sorghum", "高粱"),
    "tomate": ("tomato", "番茄"), "trigo": ("wheat", "小麦"),
    "triticale": ("triticale", "小黑麦"), "uva": ("grape", "葡萄"),
    "abobora": ("pumpkin", "南瓜"), "abobrinha": ("zucchini", "西葫芦"),
    "acelga": ("chard", "莙达菜"), "acerola": ("acerola", "西印度樱桃"),
    "agriao": ("watercress", "西洋菜"), "alface": ("lettuce", "生菜"),
    "almeirao": ("chicory", "菊苣"), "amora": ("blackberry", "黑莓"),
    "anonaceas": ("Annonaceae", "番荔枝科作物"), "azeitona": ("olive", "橄榄"),
    "batata doce": ("sweet potato", "甘薯"), "batata yacon": ("yacon", "雪莲果"),
    "berinjela": ("eggplant", "茄子"), "beterraba": ("beet", "甜菜"),
    "brocolis": ("broccoli", "西兰花"), "cacau": ("cocoa", "可可"),
    "canola": ("canola", "油菜"), "cara": ("yam", "山药"),
    "cenoura": ("carrot", "胡萝卜"), "centeio": ("rye", "黑麦"),
    "chalota": ("shallot", "红葱头"), "chicoria": ("chicory", "菊苣"),
    "chuchu": ("chayote", "佛手瓜"), "couve": ("kale", "羽衣甘蓝"),
    "couve chinesa": ("Chinese cabbage", "大白菜"), "couve de bruxelas": ("Brussels sprout", "抱子甘蓝"),
    "couve flor": ("cauliflower", "花椰菜"), "crisantemo": ("chrysanthemum", "菊花"),
    "cupuacu": ("cupuaçu", "古布阿苏"), "duboisia": ("duboisia", "杜波伊斯木"),
    "ervilha": ("pea", "豌豆"), "espinafre": ("spinach", "菠菜"),
    "estevia": ("stevia", "甜叶菊"), "feijao caupi": ("cowpea", "豇豆"),
    "feijao fava": ("lima bean", "利马豆"), "feijao guandu": ("pigeon pea", "木豆"),
    "feijao mungo": ("mung bean", "绿豆"), "feijao vagem": ("green bean", "四季豆"),
    "feijoes": ("beans", "豆类"), "framboesa": ("raspberry", "覆盆子"),
    "gengibre": ("ginger", "姜"), "grao de bico": ("chickpea", "鹰嘴豆"),
    "guarana": ("guarana", "瓜拉纳"), "gerbera": ("gerbera", "非洲菊"),
    "inhame": ("yam", "山药"), "jilo": ("scarlet eggplant", "红茄"),
    "lentilha": ("lentil", "扁豆"), "lichia": ("lychee", "荔枝"),
    "macadamia": ("macadamia", "澳洲坚果"), "mandioquinha salsa": ("arracacha", "芹菜薯"),
    "manga": ("mango", "芒果"), "maracuja": ("passion fruit", "百香果"),
    "marmelo": ("quince", "榅桲"), "maxixe": ("West Indian gherkin", "西印度小黄瓜"),
    "milheto": ("pearl millet", "珍珠粟"), "mirtilo": ("blueberry", "蓝莓"),
    "morango": ("strawberry", "草莓"), "mostarda": ("mustard", "芥菜"),
    "nabo": ("turnip", "芜菁"), "nectarina": ("nectarine", "油桃"),
    "noz peca": ("pecan", "碧根果"), "nespera": ("loquat", "枇杷"),
    "pepino": ("cucumber", "黄瓜"), "pimenta": ("pepper", "辣椒"),
    "pimentao": ("bell pepper", "甜椒"), "pitaia": ("dragon fruit", "火龙果"),
    "pitaya": ("dragon fruit", "火龙果"), "pitanga": ("Surinam cherry", "巴西樱桃"),
    "quiabo": ("okra", "秋葵"), "rabanete": ("radish", "萝卜"),
    "repolho": ("cabbage", "卷心菜"), "roma": ("pomegranate", "石榴"),
    "rosa": ("rose", "玫瑰"), "rucula": ("arugula", "芝麻菜"),
    "seriguela": ("Spanish plum", "西班牙李"), "seringueira": ("rubber tree", "橡胶树"),
    "trigo mourisco": ("buckwheat", "荞麦"), "uva de mesa": ("table grape", "鲜食葡萄"),
    "acai": ("açaí", "巴西莓"), "alamo": ("poplar", "杨树"),
    "castanha do para": ("Brazil nut", "巴西坚果"), "dende": ("oil palm", "油棕"),
    "figo": ("fig", "无花果"), "gergelim": ("sesame", "芝麻"),
    "gladiolo": ("gladiolus", "唐菖蒲"), "goiaba": ("guava", "番石榴"),
    "kiwi": ("kiwi", "猕猴桃"), "linhaca": ("flax", "亚麻"),
    "mamona": ("castor bean", "蓖麻"), "pinhao": ("pine nut", "松子"),
    "pupunha": ("peach palm", "桃棕"), "roseira": ("rose", "玫瑰"),
    "algodao geneticamente modificado": ("genetically modified cotton", "转基因棉花"),
    "milho geneticamente modificado": ("genetically modified corn", "转基因玉米"),
    "soja geneticamente modificada": ("genetically modified soybean", "转基因大豆"),
    "alstroemeria": ("alstroemeria", "六出花"), "azaleia": ("azalea", "杜鹃花"),
    "begonia": ("begonia", "秋海棠"), "celosia": ("celosia", "鸡冠花"),
    "especies florestais eucalipto e pinus": ("forest species (eucalyptus and pine)", "林业树种（桉树和松树）"),
    "gramado producao": ("turf (production)", "草坪（生产）"),
    "ornamentais flores e plantas": ("ornamentals (flowers and plants)", "观赏植物（花卉和植物）"),
    "pastagens": ("pastures", "牧场"),
    "na pre emergencia na soja": ("pre-emergence in soybean", "大豆苗前期"),
    "milho ogm tolerante ao 2 4 d": ("2,4-D-tolerant GMO corn", "耐2,4-滴转基因玉米"),
    "soja ogm tolerante ao 2 4 d": ("2,4-D-tolerant GMO soybean", "耐2,4-滴转基因大豆"),
    "anonaceas graviola pinha cherimoia atemoia araticum fruta do conde": ("Annonaceae (soursop, sugar apple, cherimoya, atemoya, araticum, custard apple)", "番荔枝科（刺果番荔枝、番荔枝、毛叶番荔枝、杂交番荔枝、阿拉蒂库姆、牛心番荔枝）"),
    "arroz geneticamente modificado": ("genetically modified rice", "转基因水稻"),
    "canola tolerante ao grupo das imidazolinonas": ("imidazolinone-tolerant canola", "耐咪唑啉酮油菜"),
    "girassol tolerante ao grupo das imidazolinonas": ("imidazolinone-tolerant sunflower", "耐咪唑啉酮向日葵"),
    "trigo tolerante ao grupo das imidazolinonas": ("imidazolinone-tolerant wheat", "耐咪唑啉酮小麦"),
    "acacia negra": ("black wattle", "黑荆树"), "caju": ("cashew", "腰果"),
    "caqui": ("persimmon", "柿子"), "carambola": ("star fruit", "杨桃"),
    "mangaba": ("mangaba", "曼加巴果"), "plantas ornamentais": ("ornamental plants", "观赏植物"),
}

NOTE_EN = {
    "nao classificado": "Not classified", "equivalente": "Equivalent",
    "improvavel de causar dano agudo": "Unlikely to cause acute damage",
    "pouco toxico": "Slightly toxic", "moderadamente toxico": "Moderately toxic",
    "altamente toxico": "Highly toxic", "muito toxico": "Highly toxic",
    "pouco perigoso": "Slightly dangerous",
    "perigoso": "Dangerous", "muito perigoso": "Very dangerous",
    "altamente perigoso": "Highly dangerous",
}

NOTE_CN = {
    "nao classificado": "未分类", "equivalente": "等同",
    "improvavel de causar dano agudo": "不太可能造成急性损害",
    "pouco toxico": "低毒", "moderadamente toxico": "中等毒性",
    "altamente toxico": "高毒", "muito toxico": "高毒", "pouco perigoso": "轻度危险",
    "perigoso": "危险", "muito perigoso": "高危险",
    "altamente perigoso": "极高危险",
}

# Nomes comuns internacionais confirmados para ingredientes cujas monografias
# ainda não possuem nome inglês/chinês preenchido no dicionário legado.
INGREDIENT_OVERRIDES = {
    "carbossulfano": ("carbosulfan", "丁硫克百威"),
    "espinosade": ("spinosad", "多杀霉素"),
    "oxadiazona": ("oxadiazon", "噁草酮"),
    "haloxyfop p methyl": ("haloxyfop-P-methyl", "高效氟吡甲禾灵"),
    "haloxifope p metilico": ("haloxyfop-P-methyl", "高效氟吡甲禾灵"),
    "bicarbonato de potassio": ("potassium bicarbonate", "碳酸氢钾"),
    "cinamaldeido": ("cinnamaldehyde", "肉桂醛"),
    "metribuzim": ("metribuzin", "嗪草酮"),
    "metamitrona": ("metamitron", "苯嗪草酮"),
    "tembotriona": ("tembotrione", "环磺酮"),
    "tembotrione": ("tembotrione", "环磺酮"),
    "nicosulfurom": ("nicosulfuron", "烟嘧磺隆"),
    "propiconazole": ("propiconazole", "丙环唑"),
    "acetato de z 9 tetradecenila": ("(Z)-9-tetradecenyl acetate", "(Z)-9-十四碳烯乙酸酯"),
    "acetato de z 7 dodecenila": ("(Z)-7-dodecenyl acetate", "(Z)-7-十二碳烯乙酸酯"),
    "acetato de z 11 hexadecenila": ("(Z)-11-hexadecenyl acetate", "(Z)-11-十六碳烯乙酸酯"),
    "acetato de z 8 dodecenila": ("(Z)-8-dodecenyl acetate", "(Z)-8-十二碳烯乙酸酯"),
    "e 8 dodecenol": ("(E)-8-dodecenol", "(E)-8-十二碳烯醇"),
    "2 4 d": ("2,4-D", "2,4-滴"),
    "carfentrazona etilica": ("carfentrazone-ethyl", "唑酮草酯"),
    "cialofope butilico": ("cyhalofop-butyl", "氰氟草酯"),
    "fenpropimorfe": ("fenpropimorph", "丁苯吗啉"),
    "fipronil": ("fipronil", "氟虫腈"),
    "fluroxipir meptilico": ("fluroxypyr-meptyl", "氯氟吡氧乙酸异辛酯"),
    "fomesafem": ("fomesafen", "氟磺胺草醚"),
    "fosetil aluminio": ("fosetyl-aluminium", "三乙膦酸铝"),
    "glufosinato de amonio": ("glufosinate-ammonium", "草铵膦"),
    "imazapic": ("imazapic", "甲咪唑烟酸"),
    "mesotriona": ("mesotrione", "硝磺草酮"),
    "oxyfluorfen": ("oxyfluorfen", "乙氧氟草醚"),
    "triclopir butotilico": ("triclopyr butoxyethyl ester", "三氯吡氧乙酸丁氧基乙酯"),
    "benzovindiflupyr": ("benzovindiflupyr", "苯并烯氟菌唑"),
    "ciclobutrifluram": ("cyclobutrifluram", "环丁氟菌胺"),
    "flutriafol": ("flutriafol", "氟环唑"),
    "glifosato": ("glyphosate", "草甘膦"),
    "indaziflam": ("indaziflam", "茚嗪氟草胺"),
    "mancozebe": ("mancozeb", "代森锰锌"),
    "metalaxil m": ("metalaxyl-M", "精甲霜灵"),
    "oxicloreto de cobre": ("copper oxychloride", "碱式氯化铜"),
    "extrato de pongamia glabra": ("Pongamia glabra extract", "水黄皮提取物"),
    "clodinafope propargil": ("clodinafop-propargyl", "炔草酯"),
    "diafentiuron": ("diafenthiuron", "丁醚脲"),
    "dioxido de silicio": ("silicon dioxide", "二氧化硅"),
    "espirodiclofeno": ("spirodiclofen", "螺螨酯"),
    "fenpropidin": ("fenpropidin", "螺环菌胺"),
    "hexazinona": ("hexazinone", "环嗪酮"),
    "proexadiona calcica": ("prohexadione-calcium", "调环酸钙"),
    "acetato de z 11 hexadecenila": ("(Z)-11-hexadecenyl acetate", "(Z)-11-十六碳烯乙酸酯"),
    "acetato de z 7 dodecenila": ("(Z)-7-dodecenyl acetate", "(Z)-7-十二碳烯乙酸酯"),
    "acetato de z 9 tetradecenila": ("(Z)-9-tetradecenyl acetate", "(Z)-9-十四碳烯乙酸酯"),
    "enxofre": ("sulfur", "硫磺"),
    "metoxifenozida": ("methoxyfenozide", "甲氧虫酰肼"),
    "oxymatrine": ("oxymatrine", "苦参碱"),
    "piriofenone": ("pyriofenone", "吡噻菌胺"),
    "oleo de thymus vulgaris": ("Thymus vulgaris oil", "百里香油"),
    "bentazone": ("bentazone", "灭草松"),
    "espiromesifeno": ("spiromesifen", "螺甲螨酯"),
    "lufenurom": ("lufenuron", "虱螨脲"),
    "metomil": ("methomyl", "灭多威"),
    "quizalofope p etilico": ("quizalofop-P-ethyl", "精喹禾灵"),
    "ascarosideo ascr 18": ("ascaroside Ascr#18", "蛔苷Ascr#18"),
    "clorimurom etilico": ("chlorimuron-ethyl", "氯嘧磺隆"),
    "malationa": ("malathion", "马拉硫磷"),
    "sulfometuron metilico": ("sulfometuron-methyl", "甲磺隆"),
    "trinexapaque etilico": ("trinexapac-ethyl", "抗倒酯"),
}

FORMULATIONS = {
    "Produto Microbiológico": ("Microbial product", "微生物制品"),
    "Biológico": ("Biological", "生物制品"),
    "Pó Molhável": ("Wettable Powder", "可湿性粉剂"),
    "Dispersão de Óleo": ("Oil Dispersion", "可分散油悬浮剂"),
    "Concentrado Emulsionável": ("Emulsifiable Concentrate", "乳油"),
    "Suspensão Concentrada": ("Suspension Concentrate", "悬浮剂"),
    "Insetos Vivos": ("Live insects", "活体昆虫"),
}


def ingredient_key(value: object) -> str:
    normalized = key(value)
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    substitutions = {
        "sal de amonio": "de amonio",
        "sal potassico": "",
        "sal sodico": "",
        "trietanolamina": "",
        "dietanolamina": "",
        "monoetanolamina": "",
        "dimetilamina": "",
        "isopropilamina": "",
    }
    for source, target in substitutions.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:g l|g kg|kg|l|percent)\b", "", normalized)
    normalized = re.sub(r"\b(?:sc|sl|ec|wg|wp|cs|od|fs|ew|gr|me|sp|sg|se)\b", "", normalized)
    return clean_space(normalized)


@dataclass
class Translator:
    dictionary_path: Path
    online_fallback: bool = True
    ingredient_en: dict[str, str] = field(init=False, default_factory=dict)
    ingredient_cn: dict[str, str] = field(init=False, default_factory=dict)
    missing: set[str] = field(init=False, default_factory=set)
    _online_cache: dict[tuple[str, str], str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        df = pd.read_excel(self.dictionary_path).fillna("")
        required = {"ingrediente_pt", "nome_en", "nome_cn"}
        if not required.issubset(df.columns):
            raise ValueError(f"Dicionário sem as colunas obrigatórias: {sorted(required)}")
        for _, row in df.iterrows():
            source = ingredient_key(row["ingrediente_pt"])
            if source:
                if clean_space(row["nome_en"]):
                    self.ingredient_en[source] = clean_space(row["nome_en"])
                if clean_space(row["nome_cn"]):
                    self.ingredient_cn[source] = clean_space(row["nome_cn"])
        for source, (name_en, name_cn) in INGREDIENT_OVERRIDES.items():
            self.ingredient_en[source] = name_en
            self.ingredient_cn[source] = name_cn

    def ingredient(self, value: str, language: str) -> str:
        mapping = self.ingredient_en if language == "en" else self.ingredient_cn
        two_four_d = TWO_FOUR_D_RE.match(value)
        if two_four_d and value[two_four_d.end():].strip():
            # A busca parcial do dicionário perderia a variante ou o sal.
            value = TWO_FOUR_D_RE.sub("2,4-D", value)
            self.missing.add(value)
            return value
        normalized = ingredient_key(value)
        # Nomes científicos permanecem em latim. A verificação antecede a
        # busca parcial para impedir colisões acidentais no dicionário.
        if BIOLOGICAL_NAME_RE.search(value):
            translated = clean_space(value)
            replacements = {
                "isolado": ("isolate", "菌株"), "cepa": ("strain", "菌株"),
                "extrato metabólico": ("metabolic extract", "代谢提取物"),
                "célula lisada": ("lysed cell", "裂解细胞"),
            }
            for source, pair in replacements.items():
                translated = re.sub(rf"\b{source}\b", pair[0 if language == "en" else 1], translated, flags=re.I)
            translated = re.sub(
                r"\s+e\s+", "和" if language == "cn" else " and ",
                translated, flags=re.I,
            )
            for source, pair in FORMULATIONS.items():
                translated = re.sub(re.escape(source), pair[0 if language == "en" else 1], translated, flags=re.I)
            return translated
        if normalized in mapping:
            return mapping[normalized]
        # O processo legado usa busca parcial após remover concentração, formulação e sais.
        candidates = [
            (source, target) for source, target in mapping.items()
            if source and f" {source} " in f" {normalized} "
        ]
        if candidates:
            return max(candidates, key=lambda item: len(item[0]))[1]
        translated = self._online(value, language)
        if translated:
            return translated
        self.missing.add(clean_space(value))
        return clean_space(value)

    def _online(self, value: str, language: str) -> str:
        value = clean_space(value)
        if not self.online_fallback or not value:
            return ""
        cache_key = (value, language)
        if cache_key in self._online_cache:
            return self._online_cache[cache_key]
        try:
            from deep_translator import GoogleTranslator
            target = "en" if language == "en" else "zh-CN"
            translated = clean_space(GoogleTranslator(source="pt", target=target).translate(value))
        except Exception:
            translated = ""
        self._online_cache[cache_key] = translated
        return translated

    @staticmethod
    def _ingredient_part(value: str) -> str:
        value = CONCENTRATION_RE.sub("", remove_product_strain(remove_product_parentheses(clean_space(value))))
        value = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:g|kg|mg|mL|L|UFC|UI)(?:\s*/\s*(?:g|kg|mL|L))?\b", "", value, flags=re.I)
        value = FORMULATION_RE.sub("", value)
        return clean_space(value).strip(" ,;+-")

    def product(self, value: str, language: str, product_type: ProductType) -> str:
        value = CONCENTRATION_RE.sub("", remove_product_parentheses(clean_space(value)))
        parts = [self._ingredient_part(part) for part in re.split(r"\s*(?:\+|;)\s*", value)]
        return capitalize_product(" + ".join(self.ingredient(part, language) for part in parts if part))

    def use(self, value: str, language: str) -> str:
        value = clean_space(value)
        if re.fullmatch(r"Indicado para a cultura da", value, re.I):
            return "Crop not specified in the DOU" if language == "en" else "DOU中未指定作物"
        value = re.sub(r"^Indicado\s+para\s+(?:as?\s+culturas?\s+d(?:er|e)|Pastagens?)\s*", lambda m: "Pastagem" if "Pastag" in m.group(0) else "", value, flags=re.I)
        value = re.sub(r"(biol[oó]gicos?)(?=[A-Z])", r"\1 ", value)
        generic = re.match(r"Indicado para qualquer cultura com (?:ocorr[eê]ncia dos? )?alvos?(?: biol[oó]gicos?)?\s*(.*)", value, re.I)
        if generic:
            target = clean_space(generic.group(1))
            descriptor_map = {
                "Antracnose": ("Anthracnose", "炭疽病"),
                "Mancha-de-Phaeosphaeria": ("Phaeosphaeria leaf spot", "叶斑病"),
                "curuquerê-do algodoeiro": ("cotton leafworm", "棉叶虫"),
                "lagarta-militar": ("fall armyworm", "草地贪夜蛾"),
                "lagarta-da-soja": ("velvetbean caterpillar", "大豆毛虫"),
                "lagarta-falsa- medideira": ("soybean looper", "大豆尺蠖"),
                "mosca-branca": ("whitefly", "粉虱"),
                "moleque da bananeira": ("banana weevil", "香蕉象甲"),
                "acaro rajado": ("two-spotted spider mite", "二斑叶螨"),
                "Ácaro rajado": ("two-spotted spider mite", "二斑叶螨"),
                "cigarrinha do milho": ("corn leafhopper", "玉米叶蝉"),
                "Gorgulho-dacana": ("sugarcane weevil", "甘蔗象甲"),
                "gorgulho da cana": ("sugarcane weevil", "甘蔗象甲"),
                "broca-do-café": ("coffee berry borer", "咖啡果小蠹"),
                "Mofo-branco": ("white mold", "白霉病"),
                "mofo-branco": ("white mold", "白霉病"),
            }
            for source, pair in descriptor_map.items():
                target = re.sub(re.escape(source), pair[0 if language == "en" else 1], target, flags=re.I)
            return (
                f"Any crop with {target}" if language == "en"
                else f"任何出现以下生物靶标的作物：{target}"
            )
        specific = re.match(r"Indicado para (?:a cultura|o cultivo) d[ao]\s+(.+)$", value, re.I)
        if specific:
            crop = clean_space(specific.group(1))
            pair = CROPS.get(key(crop))
            translated_crop = (pair[0] if language == "en" else pair[1]) if pair else self._online(crop, language)
            if translated_crop:
                return f"Suitable for {translated_crop} crop" if language == "en" else f"适用于{translated_crop}种植"
        # Divide a lista somente em vírgulas externas a parênteses e protege
        # o nome 2,4-D, cuja vírgula não separa culturas.
        protected = re.sub(r"2\s*,\s*4\s*-\s*d", "2§4-D", value, flags=re.I)
        parts = re.split(r",\s*(?![^()]*\))", protected)
        translated: list[str] = []
        for item in [clean_space(part).replace("2§4-D", "2,4-D") for part in parts if clean_space(part)]:
            pair = CROPS.get(key(item))
            if pair:
                translated.append(pair[0] if language == "en" else pair[1])
            elif re.fullmatch(r"[A-Z][a-z]+ [a-z]+", item):
                # Os nomes científicos dos alvos já estão em latim.
                translated.append(item)
            else:
                online = self._online(item, language)
                if online:
                    translated.append(online)
                else:
                    self.missing.add(item)
                    translated.append(item)
        return (", " if language == "en" else "，").join(translated)

    def note(self, value: str, language: str) -> str:
        mapping = NOTE_EN if language == "en" else NOTE_CN
        normalized = key(value)
        tox_keys = [
            "nao classificado", "equivalente", "improvavel de causar dano agudo",
            "moderadamente toxico", "altamente toxico", "muito toxico", "pouco toxico",
        ]
        env_keys = ["altamente perigoso", "muito perigoso", "pouco perigoso", "perigoso"]
        tox_key = next((item for item in tox_keys if item in normalized), "")
        env_key = next((item for item in env_keys if item in normalized), "")
        tox_category = re.search(r"Clas\.\s*tox\.\s*([1-5IVX]+)", value, re.I)
        env_category = re.search(r"Clas\.\s*amb\.\s*([1-5IVX]+)", value, re.I)
        if language == "en":
            tox_label, env_label = "Tox. clas.", "Env. clas."
        else:
            tox_label, env_label = "毒性等级", "环境等级"
        pieces: list[str] = []
        if tox_key:
            category = f" {tox_category.group(1)}" if tox_category else ""
            pieces.append(f"{tox_label}{category}: {mapping.get(tox_key, tox_key)}")
        if env_key:
            category = f" {env_category.group(1)}" if env_category else ""
            pieces.append(f"{env_label}{category} - {mapping.get(env_key, env_key)}")
        return ". ".join(pieces) + ("." if pieces else "")

    def bilingual_row(self, record: ApprovalRecord, product_type: ProductType, first: str) -> dict[str, str]:
        second = "en"
        if product_type is ProductType.FORMULADO:
            if first == "pt":
                headers = (
                    "Registrante\nRegistrant", "Marca comercial\n(Registro)\nBrand Name\n(Registration)",
                    "Recomendação de Uso\nUse Recommendation", "Nota | Note",
                    "Fabricante do produto técnico\nManufacturer of Technical Product", "Produto | Product",
                )
                use_first, note_first, product_first = record.recomendacao_uso, record.nota, record.produto
            else:
                headers = (
                    "登记持有人\nRegistrant", "商品名(注册号)\nBrand Name\n(Registration)",
                    "建议使用\nUse Recommendation", "笔记 | Note",
                    "原药生产商\nManufacturer of\nTechnical Product", "产品 | Product",
                )
                use_first = self.use(record.recomendacao_uso, "cn")
                note_first = self.note(record.nota, "cn")
                product_first = self.product(record.produto, "cn", product_type)
            return dict(zip(headers, (
                record.registrante,
                record.marca_comercial.replace(" (", "\n("),
                f"{use_first}\n{self.use(record.recomendacao_uso, second)}",
                f"{note_first}\n{self.note(record.nota, second)}",
                record.fabricante,
                f"{product_first}\n{self.product(record.produto, second, product_type)}",
            )))
        if first == "pt":
            headers = (
                "Registrante\nRegistrant", "Marca comercial (Registro)\nBrand Name (Registration)",
                "Nota | Note", "Fabricante\nManufacturer", "Produto | Product",
            )
            note_first, product_first = record.nota, record.produto
        else:
            headers = (
                "登记持有人\nRegistrant", "商品名(注册号)\nBrand Name (Registration)",
                "笔记 | Note", "生产商\nManufacturer", "产品 | Product",
            )
            note_first = self.note(record.nota, "cn")
            product_first = self.product(record.produto, "cn", product_type)
        return dict(zip(headers, (
            record.registrante, record.marca_comercial,
            f"{note_first}\n{self.note(record.nota, second)}", record.fabricante,
            f"{product_first}\n{self.product(record.produto, second, product_type)}",
        )))
