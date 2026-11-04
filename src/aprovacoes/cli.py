from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .dou import download_article, search_act
from .models import ProductType
from .parser import detect_product_type
from .pipeline import run
from .stages import create_magazine_layouts, extract_act, translate_extraction


def product_type(value: str) -> ProductType:
    return ProductType(value)


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="aprovacoes", description="Aprovações de agrotóxicos publicadas no DOU")
    commands = app.add_subparsers(dest="command", required=True)

    download = commands.add_parser("baixar", help="Pesquisar e baixar uma matéria do DOU")
    source = download.add_mutually_exclusive_group(required=True)
    source.add_argument("--ato", type=int, help="Número do ato para pesquisa no DOU")
    source.add_argument("--url", help="URL direta da matéria do DOU (contorna falhas da pesquisa)")
    download.add_argument("--data", help="Data do ato em DD/MM/AAAA; obrigatória com --ato")
    download.add_argument("--resultado", type=int, default=1, help="Resultado da pesquisa a baixar (inicia em 1)")
    download.add_argument("--saida", type=Path, required=True)

    inspect = commands.add_parser("identificar", help="Sugerir o tipo pelo primeiro parágrafo")
    inspect.add_argument("arquivo", type=Path)

    extract = commands.add_parser("extrair", help="Extrair e padronizar o ato em português")
    extract.add_argument("arquivo", type=Path, help="TXT do ato")
    extract.add_argument("--tipo", type=product_type, choices=list(ProductType), required=True)
    extract.add_argument("--agrofit-csv", type=Path)
    extract.add_argument("--sem-baixar-agrofit", action="store_true")
    extract.add_argument("--saida", type=Path, required=True, help="Planilha portuguesa de saída")

    translate = commands.add_parser("traduzir", help="Traduzir uma planilha já extraída")
    translate.add_argument("arquivo", type=Path, help="Planilha portuguesa extraída")
    translate.add_argument("--tipo", type=product_type, choices=list(ProductType), required=True)
    translate.add_argument("--dicionario", type=Path, required=True)
    translate.add_argument("--sem-traducao-online", action="store_true")
    translate.add_argument("--saida", type=Path, required=True, help="Planilha de controle traduzida")

    layout = commands.add_parser("layout", help="Criar as revistas PT/EN e mandarim/EN")
    layout.add_argument("arquivo", type=Path, help="Planilha de controle traduzida")
    layout.add_argument("--tipo", type=product_type, choices=list(ProductType), required=True)
    layout.add_argument("--saida", type=Path, required=True, help="Pasta das revistas")
    layout.add_argument("--nome", default="revista_aprovacoes")

    process = commands.add_parser("processar", help="Extrair, padronizar, traduzir e gerar as três saídas")
    process.add_argument("arquivo", type=Path, help="TXT do ato")
    process.add_argument("--tipo", type=product_type, choices=list(ProductType), required=True,
                         help="Escolha obrigatória para evitar classificação silenciosa incorreta")
    process.add_argument("--dicionario", type=Path, required=True)
    process.add_argument("--agrofit-csv", type=Path)
    process.add_argument("--sem-baixar-agrofit", action="store_true")
    process.add_argument("--sem-traducao-online", action="store_true")
    process.add_argument("--saida", type=Path, default=Path("outputs"))
    process.add_argument("--nome", default="revista_aprovacoes")
    return app


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "baixar":
        if args.url:
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(download_article(args.url), encoding="utf-8")
            print(f"Baixado: {args.url}\n{args.saida}")
            return 0
        if not args.data:
            print("--data é obrigatória quando --ato é usado.", file=sys.stderr)
            return 2
        act_date = datetime.strptime(args.data, "%d/%m/%Y").date()
        results = search_act(args.ato, act_date)
        if not results:
            print("Nenhuma matéria encontrada.", file=sys.stderr)
            return 2
        if not 1 <= args.resultado <= len(results):
            for index, result in enumerate(results, start=1):
                print(f"{index}: {result.title} — {result.url}")
            print("Índice de resultado inválido.", file=sys.stderr)
            return 2
        selected = results[args.resultado - 1]
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(download_article(selected.url), encoding="utf-8")
        print(f"Baixado: {selected.title}\n{args.saida}")
        return 0
    if args.command == "identificar":
        detected = detect_product_type(args.arquivo.read_text(encoding="utf-8"))
        print(detected.value if detected else "não identificado")
        return 0 if detected else 1
    if args.command == "extrair":
        path = extract_act(
            args.arquivo.read_text(encoding="utf-8"), args.tipo, args.saida,
            args.agrofit_csv, not args.sem_baixar_agrofit,
        )
        print(path)
        return 0
    if args.command == "traduzir":
        translated, pending = translate_extraction(
            args.arquivo, args.tipo, args.dicionario, args.saida,
            not args.sem_traducao_online,
        )
        print(f"controle: {translated}\npendências: {pending}")
        return 0
    if args.command == "layout":
        for name, path in create_magazine_layouts(args.arquivo, args.tipo, args.saida, args.nome).items():
            print(f"{name}: {path}")
        return 0
    paths = run(
        args.arquivo.read_text(encoding="utf-8"), args.tipo, args.dicionario,
        args.saida, args.nome, args.agrofit_csv, not args.sem_baixar_agrofit,
        not args.sem_traducao_online,
    )
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
