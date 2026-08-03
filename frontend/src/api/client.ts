import type { CsvConnector, DatasetInfo, Graph, IngestionConfig, IngestionJob, IngestionOptions, Monitoring, ObjectMapping, Ontology, Result, User } from '../types/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('ontology-token');
  const headers = new Headers(options?.headers);
  if (!(options?.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(url, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const validation = Array.isArray(detail)
      ? detail.map(item => `${item.loc?.slice(1).join(' → ') || 'Input'}: ${item.msg || 'is invalid'}`).join('; ')
      : undefined;
    const message = data.error?.message
      ?? (typeof detail === 'string' ? detail : validation)
      ?? `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data as T;
}

export const api = {
  login: (username: string, password: string) => request<User>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => request<Omit<User, 'token'>>('/api/v1/auth/me'),
  chat: (question: string, mode = 'hybrid', history: { role: 'user' | 'assistant'; content: string }[] = []) => request<Result>('/api/v1/chat', { method: 'POST', body: JSON.stringify({ question, mode, history }) }),
  health: () => request<Record<string, any>>('/health'),
  status: () => request<Record<string, any>>('/api/v1/ingestion/status'),
  datasets: () => request<DatasetInfo[]>('/api/v1/ingestion/datasets'),
  exportDataset: async (dataset: string) => {
    const token = localStorage.getItem('ontology-token');
    const response = await fetch(`/api/v1/ingestion/datasets/${encodeURIComponent(dataset)}/export`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error?.message ?? data.detail ?? `Export failed (${response.status})`);
    }
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = href; anchor.download = `${dataset}.zip`; anchor.click();
    URL.revokeObjectURL(href);
  },
  monitoring: () => request<Monitoring>('/api/v1/monitoring/overview'),
  ontology: () => request<Ontology>('/api/v1/graph/ontology'),
  mappings: () => request<ObjectMapping[]>('/api/v1/ingestion/mappings'),
  saveMappings: (dataset: string, mappings: ObjectMapping[]) => request<{ valid: boolean; errors: string[]; saved: boolean }>('/api/v1/ingestion/mappings', { method: 'PUT', body: JSON.stringify({ dataset, mappings }) }),
  activeDataset: () => request<{ dataset: string; embedding_model: string }>('/api/v1/ingestion/active'),
  setActiveDataset: (dataset: string, embeddingModel?: string) => request<{ dataset: string; embedding_model: string; graph_uri: string }>('/api/v1/ingestion/active', { method: 'PUT', body: JSON.stringify({ dataset, embedding_model: embeddingModel }) }),
  ingestionOptions: () => request<IngestionOptions>('/api/v1/ingestion/options'),
  startIngestion: (config: IngestionConfig) => request<IngestionJob>('/api/v1/ingestion/jobs', { method: 'POST', body: JSON.stringify(config) }),
  ingestionJob: (id: string) => request<IngestionJob>(`/api/v1/ingestion/jobs/${id}`),
  csvConnectors: () => request<CsvConnector[]>('/api/v1/connectors/csv'),
  csvConnector: (id: string) => request<CsvConnector>(`/api/v1/connectors/csv/${id}`),
  uploadCsv: (file: File) => { const body = new FormData(); body.append('file', file); return request<CsvConnector>('/api/v1/connectors/csv', { method: 'POST', body }); },
  stats: () => request<Record<string, any>>('/api/v1/graph/stats'),
  search: (q: string) => request<{ entity: string; label: string; type?: string }[]>('/api/v1/graph/search?q=' + encodeURIComponent(q)),
  neighbors: (uri: string, depth = 1) => request<Graph>(`/api/v1/graph/neighbors?depth=${depth}&uri=${encodeURIComponent(uri)}`),
  evaluationOptions: () => request<{ datasets: string[]; models: { id: string; label: string }[]; indexed: { dataset: string; embedding_model: string; model_label: string; vectors: number }[]; active: { active_dataset: string; embedding_model: string } }>('/api/v1/evaluation/options'),
  startEvaluation: ({ dataset, embeddingModel }: { dataset: string; embeddingModel: string }) => request<{ id: string; status: string; phase: string; progress: number }>('/api/v1/evaluation/jobs', { method: 'POST', body: JSON.stringify({ dataset, embedding_model: embeddingModel }) }),
  evaluationJob: (jobId: string) => request<{ id: string; status: string; phase: string; progress: number; completed_questions?: number; total_retrievals?: number; error?: string }>(`/api/v1/evaluation/jobs/${encodeURIComponent(jobId)}`),
  results: (dataset?: string, embeddingModel?: string) => request<Record<string, unknown>>(`/api/v1/evaluation/results${dataset && embeddingModel ? `?dataset=${encodeURIComponent(dataset)}&embedding_model=${encodeURIComponent(embeddingModel)}` : ''}`),
};
