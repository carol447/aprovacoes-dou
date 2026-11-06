import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aprovacoes.export import biological_rows, write_xlsx
from aprovacoes.models import ProductType
from aprovacoes.parser import detect_product_type, parse
from aprovacoes.rules import apply_business_rules, normalize_formulated_product, technical_product_without_concentration
from aprovacoes.stages import _formatted_product
from aprovacoes.translations import Translator
from openpyxl import load_workbook
import pandas as pd


FORMULADO = """
ATO Nº 50, DE 14 DE AGOSTO DE 2026
O Coordenador resolve dar publicidade ao resumo dos registros de produtos formulados.
1-a. Titular do registro: Empresa Exemplo Ltda. - CNPJ: 00.000.000/0001-00
b. Marca comercial: PRODUTO TESTE.
c. registro nº 00126
d. Fabricante do Produto técnico: Produto técnico: Acefato Técnico: Nome: Fábrica S.A.; Endereço: Rua Um - China
e. Nome comum: Acefato (750 g/kg)
f. Indicação de uso: Indicado para as culturas de Algodão, milho e soja.
j. Classificação toxicológica: Categoria 5 - Produto Improvável de Causar Dano Agudo
k. Classificação quanto ao potencial de periculosidade ambiental: Classe III - Produto Perigoso ao Meio Ambiente
"""

TECNICO = """
ATO Nº 50, 14 DE AGOSTO DE 2026.
O Coordenador-Geral de Agrotóxicos e Afins no uso das suas atribuições legais resolve dar publicidade ao resumo dos registros de produtos técnicos e pré-misturas concedidos.
1-a. Titular do registro: NORTOX S.A.
b. Marca comercial: ACEFATO TÉCNICO NORTOX
c. Registro: TC00126
d. Fabricante: Nome: Fábrica S.A.; Endereço: Rua Um - China
e. Nome comum: Acefato (970 g/kg)
j. Classificação toxicológica: O perfil toxicológico foi considerado equivalente ao produto técnico de referência
k. Classificação quanto ao potencial de periculosidade ambiental: Classe III - Produto Perigoso ao Meio Ambiente
"""


class PipelineTests(unittest.TestCase):
    def test_manufacturer_address_editorial_cleanup(self):
        from aprovacoes.rules import normalize_manufacturer

        raw = (
            "Nome: Qingdao Hengning Biotechnology Co., Ltd.- - No. 12, Haipu North Road, "
            "Xinhe Ecological Chemical Technology Industrial Base Pingdu City, "
            "Shandong Province - China"
        )
        self.assertEqual(
            normalize_manufacturer(raw, ProductType.FORMULADO),
            "Qingdao Hengning Biotech. Co., Ltd. - 12, Haipu North, "
            "Xinhe Eco. Chem. Tech. Ind. Base, Pingdu, Shandong, China",
        )

    def test_formulated_fabricante_manipulador_and_repeated_use_label(self):
        text = FORMULADO.replace(
            "d. Fabricante do Produto técnico:",
            "d. Fabricante/Manipulador:",
        ).replace(
            "e. Nome comum: Acefato (750 g/kg)",
            "e. Nome comum: Não se aplica\nf. Nome científico, no caso de agente biológico: Pseudomonas fluorescens CCT 8242",
        ).replace(
            "f. Indicação de uso: Indicado para as culturas de",
            "g. Indicação de uso: Indicação de uso: Indicado para as culturas do",
        )
        record = apply_business_rules(parse(text, ProductType.FORMULADO)[0], ProductType.FORMULADO)
        self.assertEqual(record.produto, "Pseudomonas fluorescens CCT 8242")
        self.assertEqual(record.recomendacao_uso, "Algodão, milho, soja")
        self.assertIn("Fábrica S.A.", record.fabricante)

    def test_manufacturer_address_removes_technical_footnote_and_location_hyphen(self):
        from aprovacoes.rules import normalize_manufacturer

        chizhou = "Chizhou Bioagriland Multichem Co., Ltd. - Xiangyu Chemical Industry - Dongzhi County, Chizhou City, Anhui - China"
        qingdao = "Qingdao Hengning Biotechnology Co., Ltd.* - No. 12, Haipu North Road, Xinhe Ecological Chemical Technology Industrial Base, Qingdao Pingdu City, Shandong - China"
        self.assertEqual(
            normalize_manufacturer(chizhou, ProductType.TECNICO),
            "Chizhou Bioagriland Multichem Co., Ltd. - Xiangyu Chem. Ind., Dongzhi, Chizhou, Anhui, China",
        )
        self.assertEqual(
            normalize_manufacturer(qingdao, ProductType.TECNICO),
            "Qingdao Hengning Biotech. Co., Ltd. - 12, Haipu North, Xinhe Eco. Chem. Tech. Ind. Base, Pingdu, Shandong, China",
        )

    def test_address_removes_road_and_locality_labels(self):
        from aprovacoes.rules import normalize_manufacturer

        raw = (
            "Empresa Ltda. - Rodovia Um, Rua Dois, Avenida Três, Main Street, North Avenue, "
            "West Highway, Test Village, Foo City, Bar County, Baz Province, China"
        )
        result = normalize_manufacturer(raw, ProductType.FORMULADO)
        for banned in ("Rodovia", "Rua", "Avenida", "Street", "Avenue", "Highway", "Village", "City", "County", "Province", "Rd."):
            self.assertNotIn(banned, result)

    def test_formulated_product_editorial_cleanup(self):
        self.assertEqual(
            normalize_formulated_product("tebuconazol (triazol) (750 g/kg) WG - Grânulos Dispersíveis em Água"),
            "Tebuconazol 750 g/kg WG",
        )
        self.assertEqual(
            normalize_formulated_product("CLORANTRANILIPROLE (20 g/L); CLORFENAPIR (300 g/L) SC - Suspensão Concentrada"),
            "Clorantraniliprole 20 g/L + clorfenapir 300 g/L SC",
        )
    def test_detects_both_types(self):
        self.assertIs(detect_product_type(FORMULADO), ProductType.FORMULADO)
        self.assertIs(detect_product_type(TECNICO), ProductType.TECNICO)

    def test_split_accepts_dou_numbering_variants(self):
        text = TECNICO + TECNICO.replace("1-a.", "2a.").replace("TC00126", "TC00226")
        text += TECNICO.replace("1-a.", "3.-a.").replace("TC00126", "TC00326")
        records = parse(text, ProductType.TECNICO)
        self.assertEqual([record.registro for record in records], ["TC00126", "TC00226", "TC00326"])

    def test_parenthesized_formulated_labels_from_new_dou_format(self):
        text = """
ATO Nº 58, DE 15 DE SETEMBRO DE 2026
O Coordenador resolve dar publicidade ao resumo dos registros de agrotóxicos e afins concedidos.
1-a) Nome do requerente ou titular: Empresa Exemplo Ltda.
b) Marca comercial: PRODUTO NOVO.
c) Resultado do pedido: Deferido. Concedido Certificado com registro nº 32526.
d) Fabricante do produto técnico: Nome: Fábrica S.A.; Endereço: Rua Um - China
g) Nomes comuns: Mesotriona; Ciproconazol.
h) Nome científico, no caso de agente biológico: Não se aplica i) Indicação de uso aprovada: nas culturas de milho e soja
j) Classificação toxicológica: Categoria 5 - Produto Improvável de Causar Dano Agudo.
k) Classificação do potencial de periculosidade ambiental: Classe III - Produto Perigoso ao Meio Ambiente.
"""
        record = parse(text, ProductType.FORMULADO)[0]
        self.assertEqual(record.registro, "32526")
        self.assertEqual(record.registrante, "Empresa Exemplo Ltda.")
        self.assertEqual(record.produto, "Mesotriona; Ciproconazol.")
        self.assertIn("milho e soja", record.recomendacao_uso)

    def test_formulated_headers_and_rules(self):
        record = apply_business_rules(parse(FORMULADO, ProductType.FORMULADO)[0], ProductType.FORMULADO)
        self.assertEqual(list(record.operational_row(ProductType.FORMULADO)), [
            "Registrante", "Marca comercial", "Recomendação de Uso", "Nota",
            "Fabricante do produto técnico", "Produto", "Registro",
        ])
        self.assertEqual(record.marca_comercial, "PRODUTO TESTE (00126)")
        self.assertEqual(record.recomendacao_uso, "Algodão, milho, soja")

    def test_technical_product_has_no_concentration(self):
        record = apply_business_rules(parse(TECNICO, ProductType.TECNICO)[0], ProductType.TECNICO)
        self.assertEqual(record.produto, "Acefato")
        self.assertIn("TC00126", record.marca_comercial)
        self.assertEqual(technical_product_without_concentration("Dicamba (970 g/kg)"), "Dicamba")
        self.assertEqual(
            technical_product_without_concentration(
                "CIALOFOPE BUTÍLICO (Cyhalofop-butyl) (970 g/kg) TC - Produto Técnico"
            ),
            "Cialofope butílico TC",
        )
        self.assertEqual(
            technical_product_without_concentration("FLUAZINAM (500 g/L) + TIOFANATO-METÍLICO (400 g/L) TK"),
            "Fluazinam + tiofanato-metílico TK",
        )

    def test_formulated_magazine_product_layout(self):
        row = pd.Series({
            "produto_pt": "Glufosinato - sal de amônio 200 g/L SL",
            "produto_en": "glufosinate-ammonium",
            "produto_cn": "草铵膦",
        })
        self.assertEqual(
            _formatted_product(row, "en", ProductType.FORMULADO),
            "Glufosinato - sal de amônio\nGlufosinate-ammonium\n200 g/L SL",
        )

    def test_multiple_ingredients_share_concentration_unit_on_final_line(self):
        row = pd.Series({
            "produto_pt": "clorantraniliprole (20 g/L) + clorfenapir (300 g/L) SC",
            "produto_en": "chlorantraniliprole + chlorfenapyr",
            "produto_cn": "氯虫苯甲酰胺 + 虫螨腈",
        })
        result = _formatted_product(row, "en", ProductType.FORMULADO)
        self.assertIn("20 + 300 g/L SC", result)
        self.assertNotIn("clorantraniliprole 20", result)

    def test_semicolon_separated_ingredients_are_all_kept_in_magazine(self):
        row = pd.Series({
            "produto_pt": "Fluazinam; Tiofanato-Metílico",
            "produto_en": "fluazinam + thiophanate-methyl",
            "produto_cn": "氟啶胺 + 甲基硫菌灵",
        })
        result = _formatted_product(row, "en", ProductType.FORMULADO)
        self.assertIn("Fluazinam + Tiofanato-Metílico", result)
        self.assertIn("\nFluazinam +", result)
        self.assertIn("thiophanate-methyl", result)

    def test_technical_magazine_never_reintroduces_concentration(self):
        row = pd.Series({
            "produto_pt": "Dicamba 970 g/kg",
            "produto_en": "dicamba 970 g/kg",
            "produto_cn": "麦草畏 970 g/kg",
        })
        self.assertEqual(_formatted_product(row, "en", ProductType.TECNICO), "Dicamba\nDicamba")

    def test_two_four_d_preserves_variant_and_other_ingredients(self):
        source = "2,4 d - sal de dimetilamina (Herbicida) (481.93 g/L) + aminopiralide (60.9 g/L) SL"
        product = normalize_formulated_product(source)
        dictionary = Path(__file__).resolve().parents[1] / "data" / "dicionario_final.xlsx"
        translator = Translator(dictionary, online_fallback=False)
        row = pd.Series({
            "produto_pt": product,
            "produto_en": translator.product(product, "en", ProductType.FORMULADO),
            "produto_cn": translator.product(product, "cn", ProductType.FORMULADO),
        })
        for language in ("en", "cn"):
            layout = _formatted_product(row, language, ProductType.FORMULADO)
            self.assertIn("2,4-D - sal de dimetilamina +", layout)
            self.assertTrue(layout.endswith("481.93 + 60.9 g/L SL"))
        self.assertEqual(translator.product("2,4-d", "cn", ProductType.TECNICO), "2,4-滴")
        self.assertEqual(
            translator.product("Azoxistrobina + ciproconazol", "en", ProductType.FORMULADO),
            "Azoxystrobin + cyproconazole",
        )
        self.assertEqual(
            technical_product_without_concentration("2,4-d (sal de colina) (970 g/kg) TC"),
            "2,4-D sal de colina TC",
        )

    def test_biological_product_layout_keeps_formula_and_concentration_outside_italics(self):
        row = pd.Series({
            "produto_pt": "bacillus subtilis (Microbiológico) (2 x 10^+8 UFC/g WG)",
            "produto_en": "bacillus subtilis (Microbial product)",
            "produto_cn": "bacillus subtilis (微生物制品)",
        })
        product = _formatted_product(row, "cn", ProductType.FORMULADO)
        self.assertEqual(product, "Bacillus subtilis\nBacillus subtilis\n2 x 10^+8 UFC/g WG")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "aprovados.xlsx"
            write_xlsx([{"produto_pt": "Micromus angulatus"}], path, italic_products={0})
            self.assertEqual(biological_rows(path, "produto_pt"), {0})
            write_xlsx([{"产品 | Product": product}], path, magazine=True, italic_products={0})
            workbook = load_workbook(path, rich_text=True)
            try:
                rich_text = workbook.active["A2"].value
                self.assertEqual(str(rich_text), product)
                self.assertTrue(rich_text[0].font.i)
                self.assertEqual(rich_text[1], "\n2 x 10^+8 UFC/g WG")
            finally:
                workbook.close()

    def test_product_removes_strains_without_losing_concentrations(self):
        self.assertEqual(
            normalize_formulated_product(
                "Trichoderma asperelloides, isolado ESALQ 1306 (20 g/L) + "
                "Bacillus velezensis (cepa CMRP6330) (80 g/L) SC"
            ),
            "Trichoderma asperelloides 20 g/L + bacillus velezensis 80 g/L SC",
        )
        self.assertEqual(
            technical_product_without_concentration("Bacillus velezensis, cepa CMRP6330"),
            "Bacillus velezensis",
        )

    def test_act_58_concentration_from_brand_in_existing_control(self):
        row = pd.Series({
            "produto_pt": "Azoxistrobina + ciproconazol",
            "produto_en": "azoxystrobin + cyproconazole",
            "produto_cn": "嘧菌酯 + 环丙唑醇",
            "marca_comercial": "AZOXYSTROBIN 200 G/L + CYPROCONAZOLE 80 G/L SC SINO-AGRI (32826)",
        })
        for language in ("en", "cn"):
            self.assertTrue(_formatted_product(row, language, ProductType.FORMULADO).endswith("200 + 80 g/L SC"))
        row["marca_comercial"] = "AZOXYSTROBIN 280 SC"
        self.assertNotIn("280", _formatted_product(row, "en", ProductType.FORMULADO))

    def test_brand_only_fills_missing_concentration_and_matches_ingredient_order(self):
        self.assertEqual(
            normalize_formulated_product(
                "Azoxistrobina 200 g/L + ciproconazol",
                "CYPROCONAZOLE 80 g/L + AZOXYSTROBIN 210 g/L SC",
            ),
            "Azoxistrobina 200 g/L + ciproconazol 80 g/L SC",
        )

    def test_strain_cleanup_preserves_scientific_strength_and_next_species(self):
        self.assertEqual(
            normalize_formulated_product(
                "Bacillus velezensiscepa RTI301 e Trichoderma harzianumCepa IB 19/17 2 x 10^+8 UFC/g WG"
            ),
            "Bacillus velezensis + trichoderma harzianum 2 x 10^+8 UFC/g WG",
        )


if __name__ == "__main__":
    unittest.main()
