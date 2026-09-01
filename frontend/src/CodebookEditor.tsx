import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createCodebook, getCodebook, listCodebooks, updateCodebook } from "./api";
import type { CategorySpec, CodebookSpec, CodebookSummary } from "./api";

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
  const [codebooks, setCodebooks] = useState<CodebookSummary[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [spec, setSpec] = useState<CodebookSpec>(emptySpec());
  const [yamlPreview, setYamlPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshList() {
    try {
      setCodebooks(await listCodebooks());
    } catch (err) {
      setError((err as Error).message);
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
      setError((err as Error).message);
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
      setError((err as Error).message);
    }
  }

  return (
    <div>
      <h2>Codebook</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
        <div>
          <h3>Existing codebooks</h3>
          <button type="button" onClick={startNew}>
            + New codebook
          </button>
          <ul>
            {codebooks.map((c) => (
              <li key={c.id}>
                <button type="button" onClick={() => loadCodebook(c.id)}>
                  {c.name}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <form onSubmit={handleSave} style={{ flex: 1 }}>
          <label>
            Concept
            <br />
            <input
              value={spec.concept}
              onChange={(e) => setSpec((prev) => ({ ...prev, concept: e.target.value }))}
              required
            />
          </label>
          <br />
          <label>
            Description
            <br />
            <textarea
              value={spec.description}
              onChange={(e) => setSpec((prev) => ({ ...prev, description: e.target.value }))}
              required
            />
          </label>

          <h3>Categories</h3>
          {spec.categories.map((category, index) => (
            <fieldset key={index}>
              <legend>Category {index + 1}</legend>
              <label>
                Label
                <br />
                <input
                  value={category.label}
                  onChange={(e) => updateCategoryField(index, { label: e.target.value })}
                  required
                />
              </label>
              <br />
              <label>
                Definition
                <br />
                <textarea
                  value={category.definition}
                  onChange={(e) => updateCategoryField(index, { definition: e.target.value })}
                  required
                />
              </label>
              <br />
              <label>
                Positive examples (one per line)
                <br />
                <textarea
                  value={category.positive_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { positive_examples: parseExampleList(e.target.value) })
                  }
                />
              </label>
              <br />
              <label>
                Negative examples (one per line)
                <br />
                <textarea
                  value={category.negative_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { negative_examples: parseExampleList(e.target.value) })
                  }
                />
              </label>
              <br />
              <label>
                Boundary notes
                <br />
                <textarea
                  value={category.boundary_notes}
                  onChange={(e) => updateCategoryField(index, { boundary_notes: e.target.value })}
                />
              </label>
              <br />
              {spec.categories.length > 1 && (
                <button type="button" onClick={() => removeCategory(index)}>
                  Remove category
                </button>
              )}
            </fieldset>
          ))}
          <button type="button" onClick={addCategory}>
            + Add category
          </button>

          <div>
            <button type="submit">{editingId ? "Save changes" : "Create codebook"}</button>
          </div>
        </form>

        {yamlPreview && (
          <div>
            <h3>YAML preview</h3>
            <pre>{yamlPreview}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
