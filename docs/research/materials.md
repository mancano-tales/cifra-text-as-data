# Research Materials & Literature Index — Cifra (`cifra-text-as-data`)

*Date: September 1, 2026*  
*Target Application:* Cifra (`cifra-text-as-data`)

This directory catalogs primary research papers, literature reviews, codebase deep dives, and empirical pilot datasets supporting the development of **Cifra**.

---

## 1. Primary Research Papers & Preprints

### A. Halterman & Keith (2025) — "Codebook LLMs"
- **File**: `2407.10747v2.pdf` (arXiv:2407.10747v2, Jan 2025)
- **Title**: *Codebook LLMs: Evaluating LLMs as Measurement Tools for Political Science Concepts*
- **Authors**: Andrew Halterman (Michigan State Univ) & Katherine A. Keith (Williams College)
- **Summary**: Introduces the foundational five-stage framework for operationalizing social science codebooks into LLMs, highlighting construct validity risks and behavioral testing.
- **Detailed Dialogue**: [`2026-09-01_halterman_keith_codebook_llms_dialogue_and_cifra.md`](2026-09-01_halterman_keith_codebook_llms_dialogue_and_cifra.md)

### B. DATALUTA News Automation Paper (NERA/UNESP, 2025/2026)
- **Title**: *O Banco de Dados da Luta pela Terra (DATALUTA): Automatização de Coleta e Registro de Notícias*
- **Authors**: NERA / UNESP (Sobreiro Filho et al., 2025/2026)
- **Summary**: Documents the field-by-field automated pipeline for coding news articles into ~25 agrarian conflict variables using BeautifulSoup, SpaCy NER, RAG, and fine-tuned BERTimbau-large models.
- **Detailed Analysis**: [`2026-09-01_dataluta_paper_analysis_and_cifra_synergy.md`](2026-09-01_dataluta_paper_analysis_and_cifra_synergy.md)

---

## 2. Research Reports & Codebase Deep Dives

| Document | Focus & Scope |
| :--- | :--- |
| **[`2026-08-31_llm_text_coding_literature_and_landscape.md`](2026-08-31_llm_text_coding_literature_and_landscape.md)** | Ecosystem survey across Python ML frameworks, R CSS packages, CAQDAS tools, and top Political Science papers (*Political Analysis*, *APSR*, *PNAS*, *ACL*). |
| **[`2026-08-31_codebase_deep_dive_and_benchmarks.md`](2026-08-31_codebase_deep_dive_and_benchmarks.md)** | Line-by-line inspection of 7 cloned reference repos (`deepseek-harness`, `quallmer`, `autolabel`, `instructor`, `codebook-lab`, `potato`, `LLM4Humanities`). |
| **[`2026-08-31_adversarial_codebase_audit_and_pitfalls.md`](2026-08-31_adversarial_codebase_audit_and_pitfalls.md)** | Zero-happy-path adversarial failure mode analysis and 5 real-world edge-case mitigations for Cifra (SQLite WAL, Windows encoding, etc.). |
| **[`2026-09-01_dataluta_paper_analysis_and_cifra_synergy.md`](2026-09-01_dataluta_paper_analysis_and_cifra_synergy.md)** | Empirical analysis of the NERA/UNESP DATALUTA paper, BERTimbau limitations, and Cifra orchestration synergy. |
| **[`2026-09-01_halterman_keith_codebook_llms_dialogue_and_cifra.md`](2026-09-01_halterman_keith_codebook_llms_dialogue_and_cifra.md)** | Detailed dialogue with Halterman & Keith (2025) mapping Stage 0–4 framework onto Cifra's architecture. |

---

## 3. Real-World Pilot Datasets

1. **`Reforming-TE-PT` (Bayesian Process Tracing Workbook V7)**:
   - Source: `Reforming-TE-PT/v7_banco_process_tracing_baesiano_abdutivo_manual.xlsx`
   - Content: Folha articles (1990s–2010s) evaluated on a 7-level verbal probability scale across competing hypothesis pairs ($H_1, H_2$).
   - Integration script: `examples/reforming_te_pt/load_pilot.py`

2. **DATALUTA Agrarian Conflict Corpus (NERA/UNESP)**:
   - Source: Historical news spreadsheets (2021–2023) covering land occupations, action scales, and UN SDGs (ODS 1–17).
