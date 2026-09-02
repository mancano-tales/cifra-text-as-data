import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { getRunValidation, uploadGoldLabels } from "./api";
import type { ValidationReport } from "./api";

interface ValidationPanelProps {
  runId: number;
  onError: (err: unknown) => void;
}

export function ValidationPanel({ runId, onError }: ValidationPanelProps) {
  const { t } = useTranslation();
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function loadReport() {
    try {
      setReport(await getRunValidation(runId));
    } catch (err) {
      onError(err);
    }
  }

  useEffect(() => {
    setReport(null);
    loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (submitting || !file) return;
    setSubmitting(true);
    try {
      await uploadGoldLabels(runId, file);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadReport();
    } catch (err) {
      onError(err);
    } finally {
      setSubmitting(false);
    }
  }

  const hasMetrics = report !== null && "precision" in report.per_category;
  const categories = hasMetrics ? Object.keys((report!.per_category as { precision: Record<string, number> }).precision) : [];

  return (
    <div className="category-card">
      <div className="category-card-header">
        <span className="category-card-title">{t("validation.title")}</span>
      </div>

      {report && (
        <p className="empty-state">
          {t("validation.coverage", {
            labeled: report.coverage.labeled,
            total: report.coverage.total,
          })}
          {report.coverage.excluded_multi_coder > 0 &&
            ` · ${t("validation.excluded", { count: report.coverage.excluded_multi_coder })}`}
        </p>
      )}

      {hasMetrics && categories.length > 0 && (
        <table className="results-table">
          <thead>
            <tr>
              <th>{t("validation.colCategory")}</th>
              <th>{t("validation.colPrecision")}</th>
              <th>{t("validation.colRecall")}</th>
              <th>{t("validation.colF1")}</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((label) => {
              const metrics = report!.per_category as {
                precision: Record<string, number>;
                recall: Record<string, number>;
                f1: Record<string, number>;
              };
              return (
                <tr key={label}>
                  <td>{label}</td>
                  <td>{metrics.precision[label].toFixed(2)}</td>
                  <td>{metrics.recall[label].toFixed(2)}</td>
                  <td>{metrics.f1[label].toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {hasMetrics && (
        <p className="empty-state">
          {t("validation.overall", {
            accuracy: (report!.per_category as { accuracy: number }).accuracy.toFixed(2),
            kappa:
              (report!.per_category as { kappa: number | null }).kappa === null
                ? t("validation.kappaUndefined")
                : (report!.per_category as { kappa: number }).kappa.toFixed(2),
          })}
        </p>
      )}

      {report && report.disagreements.length > 0 && (
        <table className="results-table">
          <thead>
            <tr>
              <th>{t("runs.colDocument")}</th>
              <th>{t("validation.colPredicted")}</th>
              <th>{t("validation.colGold")}</th>
            </tr>
          </thead>
          <tbody>
            {report.disagreements.map((d) => (
              <tr key={d.document_id}>
                <td>{d.document_snippet}</td>
                <td>
                  <span className="pill">{d.predicted}</span>
                </td>
                <td>
                  <span className="pill">{d.gold}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form onSubmit={handleUpload} className="actions-row">
        <label className="field-label" htmlFor="gold-labels-file">
          {t("validation.uploadLabel")}
        </label>
        <input
          id="gold-labels-file"
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          required
        />
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {t("validation.upload")}
        </button>
      </form>
    </div>
  );
}
