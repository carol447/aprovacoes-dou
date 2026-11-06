from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProductType(str, Enum):
    FORMULADO = "formulado"
    TECNICO = "tecnico"


@dataclass
class ApprovalRecord:
    registrante: str = ""
    marca_comercial: str = ""
    recomendacao_uso: str = ""
    nota: str = ""
    fabricante: str = ""
    produto: str = ""
    registro: str = ""
    source_index: int = 0
    warnings: list[str] = field(default_factory=list)
    biologico: bool = False

    def operational_row(self, product_type: ProductType) -> dict[str, str]:
        if product_type is ProductType.FORMULADO:
            return {
                "Registrante": self.registrante,
                "Marca comercial": self.marca_comercial,
                "Recomendação de Uso": self.recomendacao_uso,
                "Nota": self.nota,
                "Fabricante do produto técnico": self.fabricante,
                "Produto": self.produto,
                "Registro": self.registro,
            }
        return {
            "Registrante": self.registrante,
            "Marca comercial": self.marca_comercial,
            "Nota": self.nota,
            "Fabricante": self.fabricante,
            "Produto": self.produto,
        }
