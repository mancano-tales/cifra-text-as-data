import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { createCodebook, getCodebook, listCodebooks, updateCodebook } from "./api";
import type { CategorySpec, CodebookSpec, CodebookSummary } from "./api";
import { describeApiError } from "./errorMessages";

const EMPTY_CATEGORY: CategorySpec = {
  label: "",
  definition: "",
  positive_examples: [],
  negative_examples: [],
  boundary_notes: "",
};

function emptySpec(): CodebookSpec {
  return { concept: "", description: "", categories: [{ ...EMPTY_CATEGORY }] };
}

export function CodebookEditor() {
  const { t } = useTranslation();
  const [codebooks, setCodebooks] = useState<CodebookSummary[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [spec, setSpec] = useState<CodebookSpec>(emptySpec());
  const [yamlPreview, setYamlPreview] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);
  const shownError = error ? describeApiError(error, t) : null;

  // If the user clicks a different codebook in the list while a previous
  // loadCodebook() request is still in flight, that earlier response would
  // otherwise land after the newer one and silently overwrite the editor
  // with the wrong codebook's data. Every selection bumps the token; a
  // resolved request only applies its result if the token it was issued
  // under still matches (mirrors RunsPage's selectionTokenRef).
  const selectionTokenRef = useRef(0);

  async function refreshList() {
    try {
      setCodebooks(await listCodebooks());
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    refreshList();
  }, []);

  async function loadCodebook(id: number) {
    setError(null);
    selectionTokenRef.current += 1;
    const token = selectionTokenRef.current;
    try {
      const detail = await getCodebook(id);
      if (token !== selectionTokenRef.current) return;
      setEditingId(detail.id);
      setSpec({
        concept: detail.spec.concept,
        description: detail.spec.description,
        categories: detail.spec.categories.map((c) => ({
          label: c.label,
          definition: c.definition,
          positive_examples: c.positive_examples ?? [],
          negative_examples: c.negative_examples ?? [],
          boundary_notes: c.boundary_notes ?? "",
        })),
      });
      setYamlPreview(detail.yaml_raw);
    } catch (err) {
      if (token !== selectionTokenRef.current) return;
      setError(err);
    }
  }

  function startNew() {
    selectionTokenRef.current += 1;
    setEditingId(null);
    setSpec(emptySpec());
    setYamlPreview(null);
  }

  function updateCategoryField(index: number, patch: Partial<CategorySpec>) {
    setSpec((prev) => {
      const categories = [...prev.categories];
      categories[index] = { ...categories[index], ...patch };
      return { ...prev, categories };
    });
  }

  function addCategory() {
    setSpec((prev) => ({ ...prev, categories: [...prev.categories, { ...EMPTY_CATEGORY }] }));
  }

  function removeCategory(index: number) {
    setSpec((prev) => ({ ...prev, categories: prev.categories.filter((_, i) => i !== index) }));
  }

  function parseExampleList(raw: string): string[] {
    // Deliberately does NOT filter out blank lines here. This is a
    // controlled textarea whose `value` is `examples.join("\n")` -- if
    // onChange filtered blank lines on every keystroke, pressing Enter to
    // start a new line would immediately produce an empty trailing array
    // element, get filtered out on the very next render, and the newline
    // the user just typed would vanish. Blank lines are stripped once, in
    // handleSave, instead.
    return raw.split("\n");
  }

  function stripBlankExamples(spec: CodebookSpec): CodebookSpec {
    return {
      ...spec,
      categories: spec.categories.map((c) => ({
        ...c,
        positive_examples: c.positive_examples.filter((line) => line.trim() !== ""),
        negative_examples: c.negative_examples.filter((line) => line.trim() !== ""),
      })),
    };
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    // Captured (not bumped) at the start of the save -- if the user
    // navigates to a different codebook (or starts a new one) while this
    // save's requests are still in flight, loadCodebook()/startNew() bump
    // the token, and the result below is discarded instead of clobbering
    // whatever the user has since navigated to with this save's response.
    const token = selectionTokenRef.current;
    setSubmitting(true);
    try {
      const cleanedSpec = stripBlankExamples(spec);
      const result = editingId ? await updateCodebook(editingId, cleanedSpec) : await createCodebook(cleanedSpec);
      const detail = await getCodebook(result.id);
      if (token === selectionTokenRef.current) {
        setEditingId(detail.id);
        // Reflect the server's own (cleaned) spec back into the form --
        // without this, the textareas keep showing pre-strip blank lines
        // while the YAML preview shows the stripped version, and editing
        // further from here reintroduces the very thing just cleaned.
        setSpec({
          concept: detail.spec.concept,
          description: detail.spec.description,
          categories: detail.spec.categories.map((c) => ({
            label: c.label,
            definition: c.definition,
            positive_examples: c.positive_examples ?? [],
            negative_examples: c.negative_examples ?? [],
            boundary_notes: c.boundary_notes ?? "",
          })),
        });
        setYamlPreview(detail.yaml_raw);
      }
      await refreshList();
    } catch (err) {
      if (token === selectionTokenRef.current) setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="screen">
      {shownError && (
        <div className="banner-error">
          {shownError.message}
          {shownError.detail && <div className="banner-error-detail">{shownError.detail}</div>}
        </div>
      )}

      <div className="codebook-layout">
        <section className="card">
          <h2 className="card-title">{t("codebook.listTitle")}</h2>
          <button type="button" className="btn btn-ghost" onClick={startNew}>
            {t("codebook.newCodebook")}
          </button>
          {codebooks.length === 0 ? (
            <p className="empty-state">{t("codebook.none")}</p>
          ) : (
            <ul className="codebook-list">
              {codebooks.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => loadCodebook(c.id)}>
                    {c.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <form className="card" onSubmit={handleSave}>
          <div className="field">
            <label className="field-label" htmlFor="concept">
              {t("codebook.concept")}
            </label>
            <input
              id="concept"
              value={spec.concept}
              onChange={(e) => setSpec((prev) => ({ ...prev, concept: e.target.value }))}
              required
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="description">
              {t("codebook.description")}
            </label>
            <textarea
              id="description"
              value={spec.description}
              onChange={(e) => setSpec((prev) => ({ ...prev, description: e.target.value }))}
              required
            />
          </div>

          <hr className="section-divider" />

          {spec.categories.map((category, index) => (
            <div className="category-card" key={index}>
              <div className="category-card-header">
                <span className="category-card-title">{t("codebook.category", { n: index + 1 })}</span>
                {spec.categories.length > 1 && (
                  <button type="button" className="btn-danger-text" onClick={() => removeCategory(index)}>
                    {t("codebook.remove")}
                  </button>
                )}
              </div>
              <div className="field">
                <label className="field-label" htmlFor={`category-${index}-label`}>
                  {t("codebook.label")}
                </label>
                <input
                  id={`category-${index}-label`}
                  value={category.label}
                  onChange={(e) => updateCategoryField(index, { label: e.target.value })}
                  required
                />
              </div>
              <div className="field">
                <label className="field-label" htmlFor={`category-${index}-definition`}>
                  {t("codebook.definition")}
                </label>
                <textarea
                  id={`category-${index}-definition`}
                  value={category.definition}
                  onChange={(e) => updateCategoryField(index, { definition: e.target.value })}
                  required
                />
              </div>
              <div className="field">
                <label className="field-label" htmlFor={`category-${index}-positive-examples`}>
                  {t("codebook.positiveExamples")}
                </label>
                <textarea
                  id={`category-${index}-positive-examples`}
                  value={category.positive_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { positive_examples: parseExampleList(e.target.value) })
                  }
                />
              </div>
              <div className="field">
                <label className="field-label" htmlFor={`category-${index}-negative-examples`}>
                  {t("codebook.negativeExamples")}
                </label>
                <textarea
                  id={`category-${index}-negative-examples`}
                  value={category.negative_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { negative_examples: parseExampleList(e.target.value) })
                  }
                />
              </div>
              <div className="field">
                <label className="field-label" htmlFor={`category-${index}-boundary-notes`}>
                  {t("codebook.boundaryNotes")}
                </label>
                <textarea
                  id={`category-${index}-boundary-notes`}
                  value={category.boundary_notes}
                  onChange={(e) => updateCategoryField(index, { boundary_notes: e.target.value })}
                />
              </div>
            </div>
          ))}

          <div className="actions-row">
            <button type="button" className="btn" onClick={addCategory}>
              {t("codebook.addCategory")}
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {editingId ? t("codebook.saveChanges") : t("codebook.createCodebook")}
            </button>
          </div>
        </form>

        <section className="card">
          <h2 className="card-title">{t("codebook.yamlPreviewTitle")}</h2>
          {yamlPreview ? (
            <pre className="yaml-preview">{yamlPreview}</pre>
          ) : (
            <p className="empty-state">{t("codebook.yamlEmpty")}</p>
          )}
        </section>
      </div>
    </div>
  );
}
