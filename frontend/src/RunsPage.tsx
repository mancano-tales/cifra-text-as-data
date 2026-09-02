import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getCodebook, getRun, getRunResults, listCodebooks, listCorpora, listRuns } from "./api";
import type { CodebookSummary, CorpusSummary, ExtractionResult, RunStatus, RunSummary } from "./api";
import { describeApiError } from "./errorMessages";
import { RunForm } from "./RunForm";
import { ResultsTable } from "./ResultsTable";

const ACTIVE_STATUSES = new Set(["pending", "running"]);

export function RunsPage() {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [corpora, setCorpora] = useState<CorpusSummary[]>([]);
  const [codebooks, setCodebooks] = useState<CodebookSummary[]>([]);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<RunStatus | null>(null);
  const [results, setResults] = useState<ExtractionResult[] | null>(null);
  const [codebookLabels, setCodebookLabels] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);
  const shownError = error ? describeApiError(error, t) : null;

  const pollRef = useRef<number | null>(null);

  async function refreshRuns() {
    try {
      setRuns(await listRuns());
    } catch (err) {
      setError(err);
    }
  }

  async function loadFormOptions() {
    try {
      const [corporaList, codebooksList] = await Promise.all([listCorpora(), listCodebooks()]);
      setCorpora(corporaList);
      setCodebooks(codebooksList);
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    refreshRuns();
    loadFormOptions();
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  function stopPolling() {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function loadRunDetail(runId: number, codebookId: number) {
    try {
      const status = await getRun(runId);
      setSelectedStatus(status);

      if (ACTIVE_STATUSES.has(status.status)) {
        if (!pollRef.current) {
          pollRef.current = window.setInterval(() => loadRunDetail(runId, codebookId), 2000);
        }
        return;
      }

      stopPolling();
      await refreshRuns();

      if (status.status === "done") {
        const [rows, codebookDetail] = await Promise.all([getRunResults(runId), getCodebook(codebookId)]);
        setResults(rows);
        setCodebookLabels(codebookDetail.spec.categories.map((c) => c.label));
      }
    } catch (err) {
      stopPolling();
      setError(err);
    }
  }

  function selectRun(run: RunSummary) {
    setError(null);
    stopPolling();
    setSelectedRunId(run.id);
    setResults(null);
    setCodebookLabels([]);
    loadRunDetail(run.id, run.codebook_id);
  }

  function startNewRun() {
    setError(null);
    stopPolling();
    setSelectedRunId(null);
    setSelectedStatus(null);
    setResults(null);
  }

  async function handleCreated(runId: number) {
    await refreshRuns();
    const run = (await listRuns()).find((r) => r.id === runId);
    if (run) selectRun(run);
  }

  return (
    <div className="screen">
      {shownError && (
        <div className="banner-error">
          {shownError.message}
          {shownError.detail && <div className="banner-error-detail">{shownError.detail}</div>}
        </div>
      )}

      <div className="runs-layout">
        <section className="card">
          <h2 className="card-title">{t("runs.listTitle")}</h2>
          <button type="button" className="btn btn-ghost" onClick={startNewRun}>
            {t("runs.newRun")}
          </button>
          {runs.length === 0 ? (
            <p className="empty-state">{t("runs.none")}</p>
          ) : (
            <ul className="codebook-list">
              {runs.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => selectRun(r)}>
                    #{r.id} {r.codebook_name} · {r.corpus_id} <span className="pill">{r.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="card">
          {selectedRunId === null && (
            <RunForm corpora={corpora} codebooks={codebooks} onCreated={handleCreated} onError={setError} />
          )}

          {selectedRunId !== null && selectedStatus && ACTIVE_STATUSES.has(selectedStatus.status) && (
            <div>
              <h3 className="card-title">{t("runs.inProgress")}</h3>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width:
                      selectedStatus.total > 0
                        ? `${(selectedStatus.processed / selectedStatus.total) * 100}%`
                        : "0%",
                  }}
                />
              </div>
              <p className="empty-state">
                {selectedStatus.processed} / {selectedStatus.total}
              </p>
            </div>
          )}

          {selectedRunId !== null && selectedStatus?.status === "error" && (
            <div className="banner-error">{t("runs.runFailed")}</div>
          )}

          {selectedRunId !== null && results && (
            <ResultsTable
              runId={selectedRunId}
              results={results}
              codebookLabels={codebookLabels}
              onResultsChange={setResults}
              onError={setError}
            />
          )}
        </div>
      </div>
    </div>
  );
}
