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
    <div>
      <h2>Corpus</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <h3>Existing corpora</h3>
      <ul>
        {corpora.map((c) => (
          <li key={c.corpus_id}>
            {c.corpus_id} ({c.document_count} documents)
          </li>
        ))}
      </ul>

      <h3>Paste text</h3>
      <form onSubmit={handlePaste}>
        <input
          placeholder="corpus name"
          value={pasteName}
          onChange={(e) => setPasteName(e.target.value)}
          required
        />
        <br />
        <textarea placeholder="text" value={pasteText} onChange={(e) => setPasteText(e.target.value)} required />
        <br />
        <button type="submit">Add</button>
      </form>

      <h3>Upload CSV</h3>
      <form onSubmit={handleCsv}>
        <input placeholder="corpus name" value={csvName} onChange={(e) => setCsvName(e.target.value)} required />
        <input
          placeholder="text column name"
          value={csvColumn}
          onChange={(e) => setCsvColumn(e.target.value)}
          required
        />
        <input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)} required />
        <button type="submit">Upload</button>
      </form>

      <h3>Upload XLSX</h3>
      <form onSubmit={handleXlsx}>
        <input placeholder="corpus name" value={xlsxName} onChange={(e) => setXlsxName(e.target.value)} required />
        <input
          placeholder="text column name"
          value={xlsxColumn}
          onChange={(e) => setXlsxColumn(e.target.value)}
          required
        />
        <input type="file" accept=".xlsx" onChange={(e) => setXlsxFile(e.target.files?.[0] ?? null)} required />
        <button type="submit">Upload</button>
      </form>
    </div>
  );
}
