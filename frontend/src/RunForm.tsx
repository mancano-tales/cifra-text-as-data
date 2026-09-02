import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { createRun } from "./api";
import type { CodebookSummary, CorpusSummary } from "./api";

interface RunFormProps {
  corpora: CorpusSummary[];
  codebooks: CodebookSummary[];
  onCreated: (runId: number) => Promise<void>;
  onError: (err: unknown) => void;
}

export function RunForm({ corpora, codebooks, onCreated, onError }: RunFormProps) {
  const { t } = useTranslation();
  const [corpusId, setCorpusId] = useState("");
  const [codebookId, setCodebookId] = useState("");
  const [model, setModel] = useState("claude-sonnet-5");
  const [providerMode, setProviderMode] = useState<"api_key" | "cli">("api_key");
  const [cliCommand, setCliCommand] = useState("claude -p");
  const [cliPromptMode, setCliPromptMode] = useState<"stdin" | "arg">("stdin");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmedModel = model.trim();
    if (!trimmedModel) {
      onError(new Error("Model cannot be empty."));
      return;
    }
    const commandParts = cliCommand.split(" ").filter(Boolean);
    if (providerMode === "cli" && commandParts.length === 0) {
      onError(new Error("CLI command cannot be empty."));
      return;
    }
    try {
      const { run_id } = await createRun({
        codebook_id: Number(codebookId),
        corpus_id: corpusId,
        model: trimmedModel,
        provider_mode: providerMode,
        ...(providerMode === "cli" ? { cli_command: commandParts, cli_prompt_mode: cliPromptMode } : {}),
      });
      await onCreated(run_id);
    } catch (err) {
      onError(err);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h3 className="card-title">{t("runs.newRun")}</h3>
      <div className="field">
        <label className="field-label">{t("runs.corpus")}</label>
        <select value={corpusId} onChange={(e) => setCorpusId(e.target.value)} required>
          <option value="" disabled>
            {t("runs.selectCorpus")}
          </option>
          {corpora.map((c) => (
            <option key={c.corpus_id} value={c.corpus_id}>
              {c.corpus_id} ({c.document_count})
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="field-label">{t("runs.codebook")}</label>
        <select value={codebookId} onChange={(e) => setCodebookId(e.target.value)} required>
          <option value="" disabled>
            {t("runs.selectCodebook")}
          </option>
          {codebooks.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="field-label">{t("runs.model")}</label>
        <input value={model} onChange={(e) => setModel(e.target.value)} required />
      </div>
      <div className="field">
        <label className="field-label">{t("runs.providerMode")}</label>
        <select value={providerMode} onChange={(e) => setProviderMode(e.target.value as "api_key" | "cli")}>
          <option value="api_key">{t("runs.providerApiKey")}</option>
          <option value="cli">{t("runs.providerCli")}</option>
        </select>
      </div>
      {providerMode === "cli" && (
        <>
          <div className="field">
            <label className="field-label">{t("runs.cliCommand")}</label>
            <input value={cliCommand} onChange={(e) => setCliCommand(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label">{t("runs.cliPromptMode")}</label>
            <select value={cliPromptMode} onChange={(e) => setCliPromptMode(e.target.value as "stdin" | "arg")}>
              <option value="stdin">stdin</option>
              <option value="arg">arg</option>
            </select>
          </div>
        </>
      )}
      <button type="submit" className="btn btn-primary">
        {t("runs.start")}
      </button>
    </form>
  );
}
