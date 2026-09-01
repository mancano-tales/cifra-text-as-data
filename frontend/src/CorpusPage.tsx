import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createCorpusFromCsv, createCorpusFromPaste, createCorpusFromXlsx, listCorpora } from "./api";
import type { CorpusSummary } from "./api";

export function CorpusPage() {
  const [corpora, setCorpora] = useState<CorpusSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

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
      setError((err as Error).message);
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
      setError((err as Error).message);
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
      setError((err as Error).message);
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
      setError((err as Error).message);
    }
  }

  return (
    <div className="screen">
      {error && <div className="banner-error">{error}</div>}

      <section className="card">
        <h2 className="card-title">Existing corpora</h2>
        {corpora.length === 0 ? (
          <p className="empty-state">No corpora yet — import one below.</p>
        ) : (
          <ul className="corpus-list">
            {corpora.map((c) => (
              <li key={c.corpus_id}>
                <span className="corpus-id">{c.corpus_id}</span>
                <span className="pill">{c.document_count} docs</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="card-grid">
        <form className="card" onSubmit={handlePaste}>
          <h3 className="card-title">Paste text</h3>
          <div className="field">
            <label className="field-label" htmlFor="paste-name">
              Corpus name
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
              Text
            </label>
            <textarea id="paste-text" value={pasteText} onChange={(e) => setPasteText(e.target.value)} required />
          </div>
          <button className="btn btn-primary" type="submit">
            Add
          </button>
        </form>

        <form className="card" onSubmit={handleCsv}>
          <h3 className="card-title">Upload CSV</h3>
          <div className="field">
            <label className="field-label" htmlFor="csv-name">
              Corpus name
            </label>
            <input id="csv-name" value={csvName} onChange={(e) => setCsvName(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="csv-column">
              Text column
            </label>
            <input id="csv-column" value={csvColumn} onChange={(e) => setCsvColumn(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="csv-file">
              File
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
            Upload
          </button>
        </form>

        <form className="card" onSubmit={handleXlsx}>
          <h3 className="card-title">Upload XLSX</h3>
          <div className="field">
            <label className="field-label" htmlFor="xlsx-name">
              Corpus name
            </label>
            <input id="xlsx-name" value={xlsxName} onChange={(e) => setXlsxName(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="xlsx-column">
              Text column
            </label>
            <input id="xlsx-column" value={xlsxColumn} onChange={(e) => setXlsxColumn(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="xlsx-file">
              File
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
            Upload
          </button>
        </form>
      </div>
    </div>
  );
}
