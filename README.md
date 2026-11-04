# Aprovações DOU

Projeto para baixar atos de aprovação de agrotóxicos do Diário Oficial da União,
extrair os registros, aplicar as regras editoriais e gerar três planilhas:

- original em português;
- revista português–inglês;
- revista mandarim–inglês.

Há fluxos separados para produtos **formulados** e **técnicos**. O usuário escolhe o
tipo obrigatoriamente. A identificação pelo primeiro parágrafo é usada para conferir a
escolha e interrompe o processamento quando há contradição.

## Instalação

```powershell
cd "C:\Users\carol\Desktop\Aprovacoes formulados-DOU\aprovacoes"
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

## 1. Baixar o ato do DOU

```powershell
aprovacoes baixar --ato 50 --data 14/08/2026 --saida dados\ato_50.txt
```

Se a pesquisa oficial devolver mais de uma matéria, use `--resultado 2`, por exemplo.
Se o portal bloquear a pesquisa automatizada, copie a URL da matéria e use:

```powershell
aprovacoes baixar --url "https://www.in.gov.br/web/dou/-/ato-..." --saida dados\ato_50.txt
```

Também é possível informar diretamente ao processamento um TXT já obtido do DOU.

## 2. Conferir a sugestão automática

```powershell
aprovacoes identificar dados\ato_50.txt
```

## 3. Pipeline em etapas

Depois de baixar ou receber o TXT, a extração pode ser executada separadamente:

```powershell
aprovacoes extrair dados\ato_50.txt `
  --tipo formulado `
  --saida outputs\ato_50\ato_50_pt.xlsx
```

Em seguida, a tradução cria a planilha de controle com português, inglês e mandarim:

```powershell
aprovacoes traduzir outputs\ato_50\ato_50_pt.xlsx `
  --tipo formulado `
  --dicionario data\dicionario_final.xlsx `
  --saida outputs\ato_50\ato_50_controle_traduzido.xlsx
```

Por fim, o layout gera as duas revistas:

```powershell
aprovacoes layout outputs\ato_50\ato_50_controle_traduzido.xlsx `
  --tipo formulado `
  --saida outputs\ato_50 `
  --nome ato_50_formulados
```

Use `--sem-traducao-online` no comando `traduzir` quando quiser usar somente o
dicionário editorial. Sem essa opção, termos ausentes são enviados ao tradutor online
e continuam registrados no relatório quando a tradução falhar.

## 4. Pipeline completo

Formulados:

```powershell
aprovacoes processar dados\ato_50.txt `
  --tipo formulado `
  --dicionario data\dicionario_final.xlsx `
  --saida outputs\ato_50 `
  --nome ato_50_formulados
```

Técnicos:

```powershell
aprovacoes processar dados\ato_50.txt `
  --tipo tecnico `
  --dicionario data\dicionario_final.xlsx `
  --saida outputs\ato_50 `
  --nome ato_50_tecnicos
```

O processamento baixa a base Agrofit correspondente. Para trabalhar offline, passe
`--agrofit-csv caminho\base.csv`. Use `--sem-baixar-agrofit` somente para testar a
extração direta do DOU.

## Saídas

- `*_pt.xlsx`: conteúdo operacional original, com os cabeçalhos existentes;
- `*_controle_traduzido.xlsx`: base auditável usada na montagem das revistas;
- `*_pt_en.xlsx`: revista português–inglês;
- `*_cn_en.xlsx`: revista mandarim–inglês;
- `*_pendencias.json`: termos sem tradução e registros que precisam de conferência.

Nos produtos técnicos, `Produto` nunca inclui concentração. Nos formulados, produto,
concentração e formulação vêm da base Agrofit.

## Fontes de dados

- Diário Oficial da União: pesquisa e matéria publicadas pela Imprensa Nacional;
- Agrofit: bases de produtos formulados e produtos técnicos do MAPA;
- `data/dicionario_final.xlsx`: dicionário editorial PT/EN/CN fornecido para a revista.

## Testes

```powershell
python -m unittest discover -s tests -v
```
