import { useState } from "react";
import { useTranslation } from "react-i18next";
import { exportRunUrl, updateExtraction } from "./api";
import type { ExtractionResult } from "./api";

interface ResultsTableProps {
  runId: number;
  results: ExtractionResult[];
  codebookLabels: string[];
  onResultsChange: (results: ExtractionResult[]) => void;
  onError: (err: unknown) => void;
}

export function ResultsTable({ runId, results, codebookLabels, onResultsChange, onError }: ResultsTableProps) {
  const { t } = useTranslation();
  const [categoryFilter, setCategoryFilter] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editCategoria, setEditCategoria] = useState("");
  const [editJustificativa, setEditJustificativa] = useState("");

  function startEdit(row: ExtractionResult) {
    setEditingId(row.id);
    setEditCategoria(row.categoria);
    setEditJustificativa(row.justificativa);
  }

  async function saveEdit(row: ExtractionResult) {
    try {
      const updated = await updateExtraction(runId, row.id, editCategoria, editJustificativa);
      onResultsChange(results.map((r) => (r.id === row.id ? updated : r)));
      // Only clear the edit UI if the user is still editing this same row --
      // if they've since clicked "Edit" on a different row while this save
      // was in flight, clearing unconditionally would wipe that row's
      // in-progress (unsaved) edit instead.
      setEditingId((current) => (current === row.id ? null : current));
    } catch (err) {
      onError(err);
    }
  }

  const filteredResults = categoryFilter ? results.filter((r) => r.categoria === categoryFilter) : results;

  return (
    <div>
      <h3 className="card-title">{t("runs.resultsTitle")}</h3>
      <div className="field">
        <label className="field-label">{t("runs.filterByCategory")}</label>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
          <option value="">{t("runs.allCategories")}</option>
          {codebookLabels.map((label) => (
            <option key={label} value={label}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="actions-row">
        <a className="btn" href={exportRunUrl(runId, "csv")}>
          {t("runs.exportCsv")}
        </a>
        <a className="btn" href={exportRunUrl(runId, "xlsx")}>
          {t("runs.exportXlsx")}
        </a>
        <a className="btn" href={exportRunUrl(runId, "json")}>
          {t("runs.exportJson")}
        </a>
      </div>
      {filteredResults.length === 0 ? (
        <p className="empty-state">{t("runs.noResults")}</p>
      ) : (
        <table className="results-table">
          <thead>
            <tr>
              <th>{t("runs.colDocument")}</th>
              <th>{t("runs.colCategory")}</th>
              <th>{t("runs.colJustification")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredResults.map((row) => (
              <tr key={row.id}>
                <td>{row.document_snippet}</td>
                <td>
                  {editingId === row.id ? (
                    <select value={editCategoria} onChange={(e) => setEditCategoria(e.target.value)}>
                      {/* row.categoria can be a value not in codebookLabels -- the
                          "__error__" sentinel, or a label since removed from the
                          codebook. A <select> whose value matches no <option>
                          silently falls back to displaying the first option as
                          selected while the underlying state stays unchanged, so
                          clicking Save without noticing would submit the
                          original (invalid) value with no visible warning.
                          Surfacing it as its own option keeps what's displayed
                          in sync with what would actually be saved. */}
                      {!codebookLabels.includes(editCategoria) && (
                        <option value={editCategoria}>
                          {t("runs.unknownCategory", { value: editCategoria })}
                        </option>
                      )}
                      {codebookLabels.map((label) => (
                        <option key={label} value={label}>
                          {label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="pill">{row.categoria}</span>
                  )}
                </td>
                <td>
                  {editingId === row.id ? (
                    <textarea value={editJustificativa} onChange={(e) => setEditJustificativa(e.target.value)} />
                  ) : (
                    row.justificativa
                  )}
                </td>
                <td>
                  {editingId === row.id ? (
                    <button type="button" className="btn" onClick={() => saveEdit(row)}>
                      {t("runs.save")}
                    </button>
                  ) : (
                    <button type="button" className="btn-danger-text" onClick={() => startEdit(row)}>
                      {t("runs.edit")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
