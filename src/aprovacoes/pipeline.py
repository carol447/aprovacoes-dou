from __future__ import annotations

from pathlib import Path

from .models import ProductType
from .stages import create_magazine_layouts, extract_act, translate_extraction


def run(
    text: str, product_type: ProductType, dictionary_path: Path, output_dir: Path,
    stem: str, agrofit_csv: Path | None = None, download_agrofit: bool = True,
    online_translation: bool = True,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted = output_dir / f"{stem}_pt.xlsx"
    control = output_dir / f"{stem}_controle_traduzido.xlsx"
    extract_act(text, product_type, extracted, agrofit_csv, download_agrofit)
    translated, pending = translate_extraction(
        extracted, product_type, dictionary_path, control, online_translation
    )
    paths = create_magazine_layouts(translated, product_type, output_dir, stem)
    return {"pt": extracted, "controle": translated, **paths, "pendencias": pending}
