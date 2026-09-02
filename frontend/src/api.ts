const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function describeErrorDetail(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI's own 422 request-validation errors shape `detail` as a list
    // of {loc, msg, type} objects, not a string -- e.g. a required field
    // missing from the request body. Falling through to the generic
    // "request failed with status 422" message here would discard exactly
    // which field was wrong.
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : null))
      .filter((msg): msg is string => msg !== null);
    if (messages.length > 0) return messages.join("; ");
  }
  if (detail && typeof detail === "object") {
    // A handful of endpoints (e.g. the QualiLab label-import 422) raise a
    // structured object detail instead of a list or a string.
    return JSON.stringify(detail);
  }
  return `request failed with status ${status}`;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = describeErrorDetail(body.detail, response.status);
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export interface CorpusSummary {
  corpus_id: string;
  document_count: number;
}

export async function listCorpora(): Promise<CorpusSummary[]> {
  const response = await fetch(`${API_BASE}/corpora`);
  return handleResponse(response);
}

export async function createCorpusFromPaste(name: string, text: string): Promise<CorpusSummary> {
  const response = await fetch(`${API_BASE}/corpora/paste`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, text }),
  });
  return handleResponse(response);
}

async function uploadCorpusFile(
  endpoint: "csv" | "xlsx",
  name: string,
  textColumn: string,
  file: File
): Promise<CorpusSummary> {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("text_column", textColumn);
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/corpora/${endpoint}`, { method: "POST", body: formData });
  return handleResponse(response);
}

export const createCorpusFromCsv = (name: string, textColumn: string, file: File) =>
  uploadCorpusFile("csv", name, textColumn, file);

export const createCorpusFromXlsx = (name: string, textColumn: string, file: File) =>
  uploadCorpusFile("xlsx", name, textColumn, file);

export interface CategorySpec {
  label: string;
  definition: string;
  positive_examples: string[];
  negative_examples: string[];
  boundary_notes: string;
}

export interface CodebookSpec {
  concept: string;
  description: string;
  categories: CategorySpec[];
}

export interface CodebookSummary {
  id: number;
  name: string;
  created_at: string;
}

export interface CodebookDetail {
  id: number;
  name: string;
  spec: CodebookSpec;
  yaml_raw: string;
}

export async function listCodebooks(): Promise<CodebookSummary[]> {
  const response = await fetch(`${API_BASE}/codebooks`);
  return handleResponse(response);
}

export async function getCodebook(id: number): Promise<CodebookDetail> {
  const response = await fetch(`${API_BASE}/codebooks/${id}`);
  return handleResponse(response);
}

export async function createCodebook(spec: CodebookSpec): Promise<{ id: number; name: string }> {
  const response = await fetch(`${API_BASE}/codebooks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  return handleResponse(response);
}

export async function updateCodebook(id: number, spec: CodebookSpec): Promise<{ id: number; name: string }> {
  const response = await fetch(`${API_BASE}/codebooks/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  return handleResponse(response);
}

export interface RunSummary {
  id: number;
  corpus_id: string;
  codebook_id: number;
  codebook_name: string;
  model: string;
  status: string;
  processed: number;
  total: number;
  created_at: string;
}

export interface RunStatus {
  id: number;
  status: string;
  processed: number;
  total: number;
}

export interface ExtractionResult {
  id: number;
  run_id: number;
  document_id: number;
  categoria: string;
  justificativa: string;
  trecho_evidencia: string;
  tokens_used: number | null;
  document_snippet: string;
}

export interface CreateRunRequest {
  codebook_id: number;
  corpus_id: string;
  model: string;
  provider_mode: "api_key" | "cli";
  cli_command?: string[];
  cli_prompt_mode?: "stdin" | "arg";
}

export async function listRuns(): Promise<RunSummary[]> {
  const response = await fetch(`${API_BASE}/runs`);
  return handleResponse(response);
}

export async function getRun(id: number): Promise<RunStatus> {
  const response = await fetch(`${API_BASE}/runs/${id}`);
  return handleResponse(response);
}

export async function getRunResults(id: number): Promise<ExtractionResult[]> {
  const response = await fetch(`${API_BASE}/runs/${id}/results`);
  return handleResponse(response);
}

export async function createRun(request: CreateRunRequest): Promise<{ run_id: number }> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse(response);
}

export async function updateExtraction(
  runId: number,
  extractionId: number,
  categoria: string,
  justificativa: string
): Promise<ExtractionResult> {
  const response = await fetch(`${API_BASE}/runs/${runId}/results/${extractionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categoria, justificativa }),
  });
  return handleResponse(response);
}

export function exportRunUrl(runId: number, format: "csv" | "xlsx" | "json"): string {
  return `${API_BASE}/runs/${runId}/export?format=${format}`;
}
