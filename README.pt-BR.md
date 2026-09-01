<!-- 🇧🇷 Português — [🇺🇸 English version](README.md) -->

# cifra-text-as-data — Cifra

O **Cifra** é uma aplicação e biblioteca local-first desenvolvida para cientistas sociais (ciência política, sociologia, geografia) realizarem a codificação de textos não-estruturados (notícias, declarações, relatórios de segurança) em variáveis categóricas utilizando Modelos de Linguagem (LLMs) orientados por um manual de codificação teórico (**codebook**) — com um fluxo de validação estatística de primeira classe contra amostras codificadas por humanos.

---

## Por que o Cifra?

A classificação de texto por LLMs na ciência política corre o risco constante de violar a **validade de construto**: o modelo aplica a *sua* operacionalização específica de um conceito (ex.: diferenciar uma greve trabalhista de um protesto político), ou ele recai no conceito genérico aprendido durante o pré-treinamento? (Ver Halterman & Keith, *"Codebook LLMs: Evaluating LLMs as Measurement Tools for Political Science Concepts"*, *Political Analysis*, 2025).

No Cifra, a etapa de validação estatística ($\kappa$ de Cohen, $\alpha$ de Krippendorff, AC1 de Gwet, análise de discordâncias por categoria) não é um detalhe secundário — é o coração científico da ferramenta.

---

## Arquitetura

O Cifra adota uma arquitetura backend local em processo único no padrão **sidecar** (Python + FastAPI + SQLite com modo WAL habilitado):

```
                       ┌──────────────────────────────┐
                       │   API Sidecar FastAPI Cifra   │
                       └──────────────┬───────────────┘
                                      │
  ┌───────────────────┬───────────────┴───────────────┬───────────────────┐
  ▼                   ▼                               ▼                   ▼
┌───────────────┐   ┌───────────────┐               ┌───────────────┐   ┌───────────────┐
│   Motor de    │   │   Motor de    │               │   Motor de    │   │   Motor de    │
│  Provedores   │   │   Ingestão    │               │   Validação   │   │ Armazenamento │
│ • Instructor  │   │ • CSV/XLSX    │               │ • Cohen's κ   │   │ • SQLite WAL  │
│ • Claude CLI  │   │ • Process-Trac│               │ • Kripp. α    │   │ • Trajectory  │
│ • Ollama      │   │ • UTF-8/ftfy  │               │ • Gwet's AC1  │   │   Audit Log   │
└───────────────┘   └───────────────┘               └───────────────┘   └───────────────┘
```

- **Codebooks em YAML:** Manuais de codificação declarados em arquivos YAML legíveis por humanos e LLMs contendo conceitos, definições de categorias, exemplos positivos/negativos e notas de limite.
- **Motor Dual de Provedores:**
  1. **Modo API-Key:** Garantia de formatação de schema via `instructor` e Pydantic sobre OpenAI, Anthropic ou Gemini.
  2. **Modo CLI:** Extração de JSON sobre assinaturas CLI de texto puro (`claude -p` / `codex exec`) com recuperação por regex e limite rígido de 2 retentativas.
- **Modo Planejamento de Custos (`plan()`):** Contagem prévia de tokens e estimativa de custos financeiros antes da execução de lotes.
- **Trilha de Auditoria em SQLite:** Persistência de respostas brutas, templates de prompt, trechos de evidência (*evidence_span*) e timestamps em tabelas SQLite append-only para auditabilidade acadêmica.

---

## Instalação

```bash
pip install -e ".[dev]"
```

---

## Uso Rápido

### 1. Definir um Codebook em YAML

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

### 2. Iniciar o Servidor Sidecar FastAPI

```bash
uvicorn text_as_data.app:app --reload --port 8000
```

- **Checagem de Saúde:** `GET http://localhost:8000/health`
- **Upload de Codebook:** `POST http://localhost:8000/codebooks`
- **Upload de Corpus:** `POST http://localhost:8000/documents`
- **Execução de Lote:** `POST http://localhost:8000/runs`
- **Resultados:** `GET http://localhost:8000/runs/{run_id}/results`

---

## Testes

```bash
pytest
```

Executa a suíte de testes (40+ testes) cobrindo modelos de banco de dados, interpretador de manuais YAML, recuperação regex de CLI, endpoints FastAPI, ingestão da base piloto V7 e validação de métricas.
