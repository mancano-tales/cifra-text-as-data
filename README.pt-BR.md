<!-- 🇧🇷 Português — [🇺🇸 English version](README.md) -->

# cifra-text-as-data — Cifra

O **Cifra** é uma ferramenta local-first para transformar texto não estruturado (notícias, declarações políticas, relatórios de segurança pública) em dados categóricos usando um LLM orientado por um **codebook** explícito que você define — com uma etapa de validação contra rótulos codificados por humanos, porque LLMs não seguem a operacionalização específica de um codebook com fidelidade perfeita.

Não é uma ferramenta de codificação qualitativa manual (veja [Taguette](https://www.taguette.org/), [QualCoder](https://github.com/ccbogel/QualCoder) ou [QualiLab](https://github.com/LuizPF42/QualiLab) para isso). Você define um codebook, aponta para um corpus, e o Cifra chama o LLM sobre cada documento e preenche a tabela de output automaticamente.

**Status:** MVP completo — as cinco telas existem (Corpus, Codebook, Runs, Results, Validation). Ainda não há instalador empacotado; rodar o Cifra hoje exige iniciar dois servidores de desenvolvimento pelo terminal (veja "Executando" abaixo).

---

## Por que o Cifra?

A classificação de texto por LLMs corre o risco de **violar a validade de construto**: o modelo aplica a *sua* operacionalização específica de um conceito, ou recai no conceito genérico aprendido durante o pré-treinamento (ex.: contando uma greve trabalhista como "protesto" mesmo quando o codebook exclui isso)? Ver Halterman & Keith, *"Codebook LLMs: Evaluating LLMs as Measurement Tools for Political Science Concepts"* (*Political Analysis*, 2025). O Cifra trata a validação do output do LLM contra codificação humana como uma etapa central do pipeline, não um detalhe secundário.

---

## O que está construído

- **Motor de codebook** (`text_as_data.codebook`): carrega um conceito e suas categorias (definições, exemplos positivos/negativos, notas de limite) de um arquivo YAML e deriva um schema Pydantic e um system prompt em tempo de execução.
- **Dois modos de provedor de LLM** (`text_as_data.providers`):
  - **Modo API-key**: output estruturado via `instructor` sobre os SDKs da Anthropic ou OpenAI — o caminho confiável.
  - **Modo CLI**: chama um CLI já instalado e autenticado (`claude -p`, `agy -p` ou similar) em vez de uma chave de API avulsa. Best-effort — o schema é solicitado no prompt e a resposta JSON é extraída com retentativa em caso de output malformado.
- **Backend FastAPI + SQLite** (`text_as_data.app`, `text_as_data.db`): faz cache de extração por (documento, hash do codebook, modelo) para não repetir chamadas de documentos já codificados; retenta um documento com falha até 3 vezes e registra o erro em vez de travar a run. Cada extração persiste o prompt exato enviado e a resposta bruta do LLM para auditabilidade.
- **Validação** (`text_as_data.validation`): `agreement_report()` calcula acurácia, kappa de Cohen, precisão, recall e F1 por categoria contra um conjunto gold codificado por humanos, e retorna a lista de discordâncias para inspeção manual.
- **Frontend** (`frontend/`, Vite + React + TypeScript): cinco telas — Corpus (colar texto ou importar CSV/XLSX), Codebook (formulário estruturado + preview YAML), Runs (iniciar uma run, acompanhar progresso), Results (navegar na tabela de output, exportar CSV) e Validation (importar rótulos gold, ver métricas de concordância e discordâncias). Bilíngue PT-BR/EN.
- **Interop QualiLab** (`text_as_data.qualilab_interop`): importa pacotes `.qualilab` como fonte de rótulos gold para a etapa de validação.
- **Disclosure** (`text_as_data.disclosure`): gera um relatório estruturado de métodos para uma run concluída — qual modelo, qual codebook, qual prompt, qual taxa de reprodutibilidade.

**Ainda não construído:** importação de corpus TXT/DOCX/PDF. Instalador empacotado. Estimativa de custo em tokens antes de rodar um lote. Processamento paralelo de documentos (hoje é um documento por vez). Alpha de Krippendorff ou AC1 de Gwet (só o kappa de Cohen existe). Suporte a provedores além de Anthropic e OpenAI (sem Gemini, sem Ollama, sem endpoints locais). Entrada de credenciais na interface (hoje as chaves de API são lidas de variáveis de ambiente).

---

## Instalação (desenvolvimento)

```bash
pip install -e ".[dev]"
cd frontend && npm install && cd ..
```

Você também vai precisar de `ANTHROPIC_API_KEY` ou `OPENAI_API_KEY` como variável de ambiente (para modo API-key), ou de um CLI já instalado e autenticado como `claude` ou `agy` (para modo CLI).

> **Nota (ambientes com múltiplos worktrees):** `pip install -e .` registra o editable install globalmente, apontando para o checkout que rodou o comando por último. Se você tiver múltiplos worktrees, rode a suíte como `PYTHONPATH=src pytest` para contornar o editable install. Veja [`docs/MULTI_AGENT_WORKTREES.md`](docs/MULTI_AGENT_WORKTREES.md) para detalhes.

---

## Executando (desenvolvimento)

Ainda não há app empacotado — rodar o Cifra hoje significa iniciar o backend FastAPI e o frontend Vite juntos. `scripts/dev.sh` (macOS/Linux/Git Bash) e `scripts/dev.ps1` (PowerShell nativo) fazem isso com um comando em vez de dois terminais:

```bash
scripts/dev.sh              # backend em :8000, frontend em :5173
scripts/dev.sh 8010 5183    # opcional: sobrescrever as portas
```

```powershell
powershell -File scripts/dev.ps1
powershell -File scripts/dev.ps1 -BackendPort 8010 -FrontendPort 5183
```

Depois abra `http://localhost:5173`. Ctrl+C encerra os dois processos.

---

## Quickstart (API Python)

### 1. Definir um codebook em YAML

```yaml
concept: protest
description: Um evento público coletivo expressando uma demanda política ou social.
categories:
  - label: protest
    definition: Uma ocupação, marcha ou greve com demanda política declarada.
    positive_examples:
      - "Cerca de 200 estudantes marcharam até a prefeitura exigindo passe livre."
    negative_examples:
      - "Pessoas se reuniram para um festival de música."
    boundary_notes: Não inclui desfiles puramente cerimoniais.
  - label: not_protest
    definition: Qualquer evento que não atenda aos critérios acima.
```

### 2. Carregar e rodar uma extração

```python
import instructor
import pandas as pd
from anthropic import Anthropic

from text_as_data import Codebook, extract

codebook = Codebook.from_yaml_file("codebook.yaml")
client = instructor.from_anthropic(Anthropic())
texts = pd.DataFrame({"id": [1], "text": ["Cerca de 200 pessoas ocuparam a praça..."]})

predicted = extract(texts, codebook, client, model="claude-sonnet-5")
```

`extract()` é o bloco de base sobre o qual o backend FastAPI é implementado, útil principalmente para scripts avulsos. Use o backend se quiser cache, retentativa e suporte ao modo CLI.

### 3. Ou pelo backend

```bash
scripts/dev.sh   # em um terminal

curl -X POST http://localhost:8000/codebooks -H "Content-Type: application/json" -d '{
  "concept": "protest",
  "description": "Um evento público coletivo expressando uma demanda política ou social.",
  "categories": [
    {"label": "protest", "definition": "Uma ocupação, marcha ou greve com demanda política declarada."},
    {"label": "not_protest", "definition": "Qualquer evento que não atenda aos critérios acima."}
  ]
}'
curl -X POST http://localhost:8000/corpora/paste -H "Content-Type: application/json" \
  -d '{"name": "demo", "text": "Cerca de 200 pessoas ocuparam a praça..."}'
curl -X POST http://localhost:8000/runs -H "Content-Type: application/json" \
  -d '{"codebook_id": 1, "corpus_id": "demo", "model": "claude-sonnet-5"}'
curl http://localhost:8000/runs/1/results
```

---

## Testes

```bash
PYTHONPATH=src pytest
```

Executa 238 testes cobrindo o motor de codebook, os dois modos de provedor, os modelos SQLite, os endpoints FastAPI, a importação de corpus, o interop QualiLab, as métricas de validação e o módulo de disclosure.

---

## Empacotamento (não iniciado)

O plano (ver `AGENTS.md` § "Product trajectory") é um app desktop empacotado — o backend Python compilado em um único binário, rodando localmente, para que instalar o Cifra seja "baixar e abrir" em vez de "clonar o repositório e iniciar dois servidores de desenvolvimento". Esse trabalho ainda não começou. O `AGENTS.md` condiciona isso à validação do pipeline com uso real primeiro.
