const API_BASE = "http://localhost:8000";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `request failed with status ${response.status}`);
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
