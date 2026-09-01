import { useEffect, useState } from "react";
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
  const shownError = error ? describeApiError(error, t) : null;

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
    try {
      const detail = await getCodebook(id);
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
      setError(err);
    }
  }

  function startNew() {
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
    return raw.split("\n").filter((line) => line.trim() !== "");
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result = editingId ? await updateCodebook(editingId, spec) : await createCodebook(spec);
      const detail = await getCodebook(result.id);
      setEditingId(detail.id);
      setYamlPreview(detail.yaml_raw);
      await refreshList();
    } catch (err) {
      setError(err);
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
                <label className="field-label">{t("codebook.label")}</label>
                <input
                  value={category.label}
                  onChange={(e) => updateCategoryField(index, { label: e.target.value })}
                  required
                />
              </div>
              <div className="field">
                <label className="field-label">{t("codebook.definition")}</label>
                <textarea
                  value={category.definition}
                  onChange={(e) => updateCategoryField(index, { definition: e.target.value })}
                  required
                />
              </div>
              <div className="field">
                <label className="field-label">{t("codebook.positiveExamples")}</label>
                <textarea
                  value={category.positive_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { positive_examples: parseExampleList(e.target.value) })
                  }
                />
              </div>
              <div className="field">
                <label className="field-label">{t("codebook.negativeExamples")}</label>
                <textarea
                  value={category.negative_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { negative_examples: parseExampleList(e.target.value) })
                  }
                />
              </div>
              <div className="field">
                <label className="field-label">{t("codebook.boundaryNotes")}</label>
                <textarea
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
            <button type="submit" className="btn btn-primary">
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
