import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { createCorpusFromCsv, createCorpusFromPaste, createCorpusFromXlsx, listCorpora } from "./api";
import type { CorpusSummary } from "./api";
import { describeApiError } from "./errorMessages";

export function CorpusPage() {
  const { t } = useTranslation();
  const [corpora, setCorpora] = useState<CorpusSummary[]>([]);
  const [error, setError] = useState<unknown>(null);
  const shownError = error ? describeApiError(error, t) : null;

  const [pasteName, setPasteName] = useState("");
  const [pasteText, setPasteText] = useState("");

  const [csvName, setCsvName] = useState("");
  const [csvColumn, setCsvColumn] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);

  const [xlsxName, setXlsxName] = useState("");
  const [xlsxColumn, setXlsxColumn] = useState("");
  const [xlsxFile, setXlsxFile] = useState<File | null>(null);

  async function refresh() {
    try {
      setCorpora(await listCorpora());
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handlePaste(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await createCorpusFromPaste(pasteName, pasteText);
      setPasteName("");
      setPasteText("");
      await refresh();
    } catch (err) {
      setError(err);
    }
  }

  async function handleCsv(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!csvFile) return;
    try {
      await createCorpusFromCsv(csvName, csvColumn, csvFile);
      setCsvName("");
      setCsvColumn("");
      setCsvFile(null);
      await refresh();
    } catch (err) {
      setError(err);
    }
  }

  async function handleXlsx(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!xlsxFile) return;
    try {
      await createCorpusFromXlsx(xlsxName, xlsxColumn, xlsxFile);
      setXlsxName("");
      setXlsxColumn("");
      setXlsxFile(null);
      await refresh();
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

      <section className="card">
        <h2 className="card-title">{t("corpus.existingTitle")}</h2>
        {corpora.length === 0 ? (
          <p className="empty-state">{t("corpus.empty")}</p>
        ) : (
          <ul className="corpus-list">
            {corpora.map((c) => (
              <li key={c.corpus_id}>
                <span className="corpus-id">{c.corpus_id}</span>
                <span className="pill">{t("corpus.docCount", { count: c.document_count })}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="card-grid">
        <form className="card" onSubmit={handlePaste}>
          <h3 className="card-title">{t("corpus.pasteTitle")}</h3>
          <div className="field">
            <label className="field-label" htmlFor="paste-name">
              {t("corpus.corpusName")}
            </label>
            <input
              id="paste-name"
              value={pasteName}
              onChange={(e) => setPasteName(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="paste-text">
              {t("corpus.text")}
            </label>
            <textarea id="paste-text" value={pasteText} onChange={(e) => setPasteText(e.target.value)} required />
          </div>
          <button className="btn btn-primary" type="submit">
            {t("corpus.add")}
          </button>
        </form>

        <form className="card" onSubmit={handleCsv}>
          <h3 className="card-title">{t("corpus.csvTitle")}</h3>
          <div className="field">
            <label className="field-label" htmlFor="csv-name">
              {t("corpus.corpusName")}
            </label>
            <input id="csv-name" value={csvName} onChange={(e) => setCsvName(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="csv-column">
              {t("corpus.textColumn")}
            </label>
            <input id="csv-column" value={csvColumn} onChange={(e) => setCsvColumn(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="csv-file">
              {t("corpus.file")}
            </label>
            <input
              id="csv-file"
              type="file"
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
              required
            />
          </div>
          <button className="btn btn-primary" type="submit">
            {t("corpus.upload")}
          </button>
        </form>

        <form className="card" onSubmit={handleXlsx}>
          <h3 className="card-title">{t("corpus.xlsxTitle")}</h3>
          <div className="field">
            <label className="field-label" htmlFor="xlsx-name">
              {t("corpus.corpusName")}
            </label>
            <input id="xlsx-name" value={xlsxName} onChange={(e) => setXlsxName(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="xlsx-column">
              {t("corpus.textColumn")}
            </label>
            <input id="xlsx-column" value={xlsxColumn} onChange={(e) => setXlsxColumn(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="xlsx-file">
              {t("corpus.file")}
            </label>
            <input
              id="xlsx-file"
              type="file"
              accept=".xlsx"
              onChange={(e) => setXlsxFile(e.target.files?.[0] ?? null)}
              required
            />
          </div>
          <button className="btn btn-primary" type="submit">
            {t("corpus.upload")}
          </button>
        </form>
      </div>
    </div>
  );
}
