# Lessons from Open Notebook (lfnovo/open-notebook) for Cifra

> Read the real source (not just the README) of a shallow clone of
> `lfnovo/open-notebook` @ `main` (commit corresponding to v1.14.0, tested
> locally via Docker on 2026-09-01). Cross-checked against this repo's
> `AGENTS.md` (`text-as-data`), commit `29f2327` at read time.

## State note — an inconsistency found, not resolved here

This repo's `AGENTS.md` still says `Working product name: "Codifica"`
(line 35) on `main` (`29f2327`), but `README.md`/`README.pt-BR.md` were
already updated to "Cifra" by a concurrent session (commits
`docs: rename the product from Codifica to Cifra` and
`docs(readme): update README.md and README.pt-BR.md for Cifra`). The
`AGENTS.md` rename lives on a separate branch/worktree
(`worktree-slice-1-backend-skeleton`) and never reached `main`. This
document uses "Cifra" (the more recent decision, made in chat) but does
not edit `AGENTS.md` — reconciling that merge is out of scope for this
task.

**Two premises from the original request that did not hold up under
source reading, recorded here instead of forced**:
- **There is no `desktop/electron` folder in the repository.** A search of
  the full tree (`git ls-tree -r main`) for `desktop|electron|tauri`
  returned zero results, checked twice. Open Notebook has no desktop
  packaging at all — it's Next.js (frontend) + FastAPI (backend) running
  via Docker Compose, no native shell. There is nothing to learn here
  about Tauri/PyInstaller from this project; Cifra's Phase 2 plan
  (`AGENTS.md` § Product trajectory) remains without direct precedent.
- **The multi-LLM-provider abstraction is not the `ai-prompter` lib** —
  it's a separate library, **`esperanto`** (`AIFactory`). `ai-prompter`
  does exist, but covers something else: prompt templating (Jinja), not
  provider selection/routing. See §1 and §2 below.

**On language, for this document specifically**: Open Notebook advertises
a 6-language UI (English, Portuguese, Chinese Simplified/Traditional,
Japanese, Russian, Bengali — `README.md` feature list). That breadth isn't
a relevant comparison point for Cifra. The two languages that actually
matter for Cifra's real context are **English and Brazilian Portuguese**:
this repository's own `AGENTS.md` mandates English for everything in the
codebase, while the actual research content Cifra processes — the
`Reforming-TE-PT` pilot corpus, the Halterman & Keith dialogue in §6 below
— is Brazilian Portuguese. Cifra has no product reason to chase Open
Notebook's full i18n surface; it has a concrete reason to make sure
PT-BR text (accents, `boundary_notes` written in Portuguese) round-trips
correctly through whichever provider/encoding path is chosen — which is
exactly the class of bug `AGENTS.md`'s Slice 1 section already documents
being found and fixed (`cp1252` double-encoding of `instituições`).

---

## 1. Multi-provider abstraction: `esperanto`, not `ai-prompter`

**Where**: `open_notebook/ai/models.py` (`ModelManager.get_model`),
`open_notebook/ai/provision.py`.

`esperanto.AIFactory` exposes `create_language()`, `create_embedding()`,
`create_speech_to_text()`, `create_text_to_speech()` — each takes
`model_name`, `provider` (a normalized string: the DB stores underscores,
Esperanto expects hyphens — there's an explicit normalization line just
for that) and `config` (a dict with `api_key`, `base_url`, etc.). The
returned object has `.to_langchain()`, converting it into a standard
LangChain `BaseChatModel` — from that point on the rest of the code only
uses the LangChain interface, with no knowledge of which provider is
behind it.

**Models are registered as database rows** (table `model`: `name`,
`provider`, `type`, `credential`), not as static config in code. A
`DefaultModels` singleton holds, per *role* (`default_chat_model`,
`default_transformation_model`, `default_embedding_model`,
`large_context_model`, `default_tools_model`, TTS/STT) — which `model.id`
fills that role. Changing "which model does summarization" is writing to
a field, not editing code.

**Model selection is dynamic based on content size**
(`provision.py::provision_langchain_model`): if the payload exceeds 105k
tokens, it automatically uses `large_context_model` instead of the
requested type's default — a model swap driven by a context heuristic,
transparent to the caller.

**A security detail genuinely applicable to Cifra**: `models.py` closes an
explicit TOCTOU (time-of-check-to-time-of-use) window — a
user-configured provider URL (e.g. an Ollama/OpenAI-compatible endpoint)
is re-validated (`_revalidate_config_urls`) *immediately before* each
real call, not only when the credential is saved, because "a hostname
that resolved to a public IP when saved can later be repointed to an
internal/metadata address, and Esperanto/httpx re-resolve DNS fresh on
every connection." **This applies to Cifra**: if Cifra's CLI/API-key mode
ever accepts a custom endpoint (e.g. a self-hosted OpenAI-compatible
provider), the same window exists and deserves the same protection — this
isn't hypothetical, it's the same kind of data (a user-configured URL,
used at runtime).

### What's directly reusable (the pattern, not the library itself)

- **Registering the model-per-role in a database**, not hardcoded — Cifra
  already does something similar implicitly (`get_client(mode, provider)`
  cited in `AGENTS.md`), but the explicit pattern "role → `model_id` →
  versionable, swappable-without-redeploy registration" is worth copying
  if Cifra grows beyond 2 modes (CLI/API-key) to multiple API-key
  providers.
- **Re-validating a URL before every use**, not only on save — applicable
  the day Cifra accepts a custom endpoint.

### What's not worth adopting as-is

- **The `esperanto` library as a whole is not a clear upgrade** for Cifra:
  it buys support for 10+ providers, but in exchange gives up the
  structured function-calling that `instructor` already guarantees in
  Cifra's API-key mode (see §3). Switching isn't strictly better, it's a
  different trade-off — more providers, less schema guarantee.

---

## 2. `ai-prompter`: prompt management via named Jinja templates

**Where**: used in `open_notebook/graphs/{prompt,transformation,ask}.py`.

`Prompter(prompt_template="ask/entry", parser=parser).render(data=state)`
— loads a Jinja template by **name/path** (not an inline string) from a
versioned prompts directory, injects the state data and (if a `parser` is
passed) also injects the parser's format instructions into the template
itself.

**A concrete security lesson, with an associated CVE (GHSA-f35w-wx37-26q7)**,
repeated as a mandatory comment in at least two files:

> Never compile caller-supplied free text as Jinja template *source*
> (`Prompter(template_text=...)`) — pass it as a plain render variable
> into a fixed, developer-authored template instead.

**This applies to Cifra directly.** Cifra's `codebook.py` derives a
Pydantic schema from YAML written by the researcher — free text
(definitions, `boundary_notes`, examples) that ends up in the LLM prompt.
Today (Slice 1) that text becomes configuration data, not template
source; but if Cifra ever adopts a templating engine (Jinja or otherwise)
to assemble the system prompt from the codebook, Open Notebook's rule is
worth following exactly: codebook content is a **render variable**,
never **compilable template source** — otherwise a `boundary_notes` field
containing Jinja syntax (`{{ }}`/`{% %}`) becomes code execution, not
text.

### What's directly reusable

- **The security rule above**, as a design principle to document in
  Cifra's `AGENTS.md` now, before a templating engine exists — cheaper to
  prevent now than to discover later.
- **Named, versioned templates** instead of prompt strings scattered
  through the code — even without adopting `ai-prompter` as a dependency,
  the pattern "a prompt lives in a named file, not inline" is good
  hygiene, and Cifra hasn't decided this explicitly yet.

### What's not urgent to adopt

- The `ai-prompter` library itself — Cifra *dynamically* derives its
  schema from the codebook's YAML (`AGENTS.md` § Codebook format), which
  is already a more direct abstraction than "render a Jinja template over
  a generic payload." Adopting `ai-prompter` would only make sense if
  Cifra grows into multiple prompt types (e.g. a triage prompt before
  extraction, a separate summarization prompt) that benefit from shared
  templates — not the case today.

---

## 3. Structured output: JSON via prompt + `PydanticOutputParser`, **not** function-calling

**Where**: `open_notebook/graphs/ask.py::call_model_with_messages`.

Open Notebook **does not use function-calling/tool-calling** for
structured output. The flow is:

1. Define Pydantic models (`Strategy`, `Search`).
2. `PydanticOutputParser(pydantic_object=Strategy)` — generates "format
   instructions" that get injected into the prompt text itself (via
   `Prompter(..., parser=parser)`).
3. Pass `structured=dict(type="json")` as a best-effort kwarg to the
   provider (roughly equivalent to JSON mode, when the provider supports
   it).
4. Get the response as free text, strip "thinking" tags (extended-thinking
   models), and **only then** `parser.parse(cleaned_content)` — Pydantic
   validation happens after the call, with no automatic retry-on-
   `ValidationError` loop visible in this file (unlike `instructor`'s
   `reask` pattern, which this repository's own `deepseek-harness`
   research has already documented).

**This is the single most important finding of this reading, and it's a
"do not copy" lesson.** Cifra already decided (via `instructor`, in
API-key mode) to use real function-calling — the schema is enforced by
the provider's API, not "politely asked for" in the prompt text. That is
strictly stronger than what Open Notebook does. **There is nothing to
import here** — Cifra is already in a better architectural position than
this reference on this specific point. The only lesson is a negative one:
it confirms Cifra's choice (`instructor` in API-key mode, accepting
"best-effort" only in CLI mode, where there is no alternative) is aligned
with the field's more rigorous practice, not with what Open Notebook does.

---

## 4. Content extraction: `content-core` — a real candidate for direct dependency

**Where**: `open_notebook/graphs/source.py::content_process`.

`content_core.extract_content(url=, file_path=, content=, config=)` →
`ExtractionOutput` (`.content`, `.title`). A single function covers:

- **Documents**: PDF/DOCX/etc., with a selectable engine
  (`auto`/`docling`/`simple`) — `docling` brings OCR, formula recognition
  and computer vision for scanned PDFs, as an *opt-in*
  (`OPEN_NOTEBOOK_ENABLE_DOCLING` env var), because it's a heavy ML
  stack.
- **URLs**: selectable engine (`auto`/`simple`/`firecrawl`/`jina`/
  `crawl4ai`), including YouTube (transcription, configurable preferred
  language list).
- **Soft failure treated as a real error**: `content-core` signals a
  failed extraction by returning `title="Error"` and content prefixed
  with `"Failed to extract content:"` instead of raising — Open Notebook
  explicitly detects that sentinel and converts it into a `ValueError`
  with a clear message, so it never saves a "completed source" whose body
  is an error string.

**This maps almost 1:1 onto a real, named gap in Cifra**: `AGENTS.md`
lists "Import corpus: CSV/XLSX ... standalone TXT/DOCX/PDF" in MVP scope
(Screen 1), but also lists "image/scanned-PDF extraction (OCR)" as
**explicitly out of MVP scope**. `content-core` already handles PDF/DOCX
natively and treats OCR as an opt-in env-var flag — i.e. what Cifra
deferred to later, this library already ships as a flag, not a rewrite.

### Concrete recommendation

**`content-core` is worth evaluating as a direct dependency for Cifra's
Screen 1 (corpus import)**, instead of reimplementing DOCX/PDF extraction
from scratch — exactly the kind of "mechanical engineering already solved
by a third party" that the Tote Labs `AGENTS.md` itself endorses as
posture (implement/contribute upstream/adapt instead of duplicating).
Caveats before deciding:
- It's a dependency from the Posit/lfnovo ecosystem, not tested here for
  install overhead (the `docling` stack is heavy — Open Notebook's own
  docs treat it as opt-in for that reason).
- Cifra's CSV/XLSX (the format most used in the MVP, given the
  `Reforming-TE-PT` pilot) does not go through `content-core` in Open
  Notebook — it's only used for a standalone URL/document, not a tabular
  spreadsheet. Cifra would still need its own CSV/XLSX import path
  (column → text mapping) regardless; `content-core` would only cover the
  TXT/DOCX/PDF subset.
- Not tested this round whether `content-core` works well on native
  Windows (Cifra's actual development environment) — it was only observed
  running inside Open Notebook's Docker container.

---

## 5. SurrealDB vs. SQLite — why Cifra's choice remains correct

**Where**: `docker-compose.yml` (`surrealdb` service, `rocksdb` engine),
`open_notebook/database/migrations/1.surrealql` (`fn::vector_search`
function), `open_notebook/domain/notebook.py::vector_search`.

Facts verified, not assumed:

- SurrealDB runs in **embedded storage mode** (`rocksdb:/mydata/
  mydatabase.db` — a local disk engine, not a distributed cluster), but
  **still as a separate process/server**, spoken to over WebSocket
  (`SURREAL_URL=ws://surrealdb:8000/rpc`) — it's a second container in
  `docker-compose.yml`, not an in-process library the way SQLite is.
- **Vector search uses the native `vector::similarity::cosine()`
  function**, called inside a custom SurrealQL function
  (`fn::vector_search`) that does a `SELECT ... FROM source_embedding
  LIMIT $match_count` computing cosine per row. **No `DEFINE INDEX` with
  `HNSW`/`MTREE` was found** anywhere in the migrations — i.e. this is
  brute-force full-scan vector search with a limit, not indexed
  approximate search. That's fine at the scale of a personal notebook
  (hundreds/thousands of chunks); it would not perform the same at
  millions of vectors without adding an index.

**Conclusion for Cifra**: SurrealDB's central value proposition — vector +
graph + relational in one engine — solves Open Notebook's problem
(conversational RAG over your own notes: "ask something, find the most
semantically similar chunks"). **Cifra does not have that problem.**
Cifra's core task is categorical classification against an explicit
codebook (a fixed enum of categories, validated via kappa against human
gold labels) — not semantic similarity search over free text. Adopting
SurrealDB would trade SQLite's operational simplicity (zero extra
process, single file, already decided and working in Slice 1) for an
extra running process, in exchange for a capability (vector search) Cifra
doesn't use today and whose product design doesn't call for. **Nothing
here justifies reopening the architecture decision already closed in
`AGENTS.md`** ("Architecture — closed decision, do not reopen without a
strong reason") — if anything, this reading reinforces that SQLite is the
right choice for the shape of Cifra's problem.

If Cifra ever gains a semantic-search feature over already-coded corpora
(e.g. "find documents similar to this one that was coded as X"), SQLite
has lighter equivalent paths (`sqlite-vec`, or even `numpy`/`scikit-learn`
in-memory at the scale of a research project) without needing to import
SurrealDB just for that.

---

## 6. Cross-reference: Halterman & Keith (2025) makes §3's finding sharper

This repository already has a dedicated dialogue with Halterman & Keith's
paper — see
[`docs/research/2026-09-01_halterman_keith_codebook_llms_dialogue_and_cifra.md`](./research/2026-09-01_halterman_keith_codebook_llms_dialogue_and_cifra.md),
written by a concurrent session the same day as this document. It's worth
reading together with §3 above, because they reinforce the same point
from two different angles.

Halterman & Keith's central empirical finding is that zero-shot LLMs fail
codebook-grounded classification in two specific ways: **instruction
omission** (given only a bare label name, the model guesses the boundary)
and **pre-training shortcut bias** (given a full codebook, the model still
falls back on lexical pattern-matching from pre-training instead of the
codebook's actual definition — e.g. predicting `RALLY` whenever the word
"rally" appears, regardless of whether the text matches the codebook's
definition of `DEMONSTRATION`). Their proposed mitigation, at the
schema level, is forcing the model to externalize *why* it chose a label,
not just the label itself.

**This is precisely what Open Notebook's structured-output pattern (§3)
does not do.** A `PydanticOutputParser` that only recovers a label-shaped
object after the fact has no mechanism forcing the model to justify a
classification against a specific codebook definition — it validates the
*shape* of the output, not the *reasoning*. Cifra's schema already goes
further than Halterman & Keith's own baseline setup by forcing two
additional fields per classification, per the other document's §4.1:
`rationale` (a step-by-step justification grounded in the codebook) and
`evidence_span` (a verbatim quote from the source text). Read next to
Open Notebook's actual code, this isn't a redundant design choice — it's
the concrete, code-level answer to a documented, named failure mode
(pre-training shortcut bias) that a weaker structured-output pattern like
Open Notebook's would have no way to catch. The two documents corroborate
each other: one from reading a competing implementation, the other from
reading the methodology paper the competing implementation ignores.

---

## Summary — what to do with this

| Finding | Recommended action |
|---|---|
| `content-core` (DOCX/PDF/OCR extraction) | **Evaluate as a direct dependency** before writing document extraction from scratch on Screen 1 — weight/Windows caveats above, not yet tested |
| Jinja rule "never compile user text as template-source" | **Document in Cifra's `AGENTS.md` now**, as a preventive principle, even without a templating engine yet |
| Re-validating a URL before every use (not only on save) | **Keep in mind for when** Cifra accepts a custom provider endpoint |
| `esperanto` (multi-provider) | **Do not adopt** — would trade `instructor`'s schema guarantee for more providers; not a worthwhile trade-off today |
| `ai-prompter` (named Jinja templates) | **Not urgent to adopt** — the pattern (prompts in named files, not inline) is worth following without the library |
| Structured output via prompt+parser (not function-calling) | **Do not copy** — Cifra already does this better via `instructor` |
| SurrealDB vs. SQLite | **Do not reopen the decision** — SQLite remains correct for Cifra's problem shape |
| Desktop packaging (`desktop/electron`) | **Does not exist in Open Notebook** — no lesson to extract; Cifra's Phase 2 plan remains without direct precedent here |
| Halterman & Keith (2025) vs. Open Notebook's structured output | **Corroborating evidence, not a new action** — §6 shows Cifra's `rationale`+`evidence_span` fields are the concrete answer to the paper's "pre-training shortcut bias" finding, which Open Notebook's weaker output pattern has no mechanism to catch |
