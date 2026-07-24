import type { CsvConnector, DatasetInfo, Graph, IngestionJob, Monitoring, ObjectMapping, Ontology, Result, User } from '../types/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('ontology-token');
  const headers = new Headers(options?.headers);
  if (!(options?.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(url, { ...options, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message ?? 'Backend request failed');
  return data as T;
}

export const api = {
  login: (username: string, password: string) => request<User>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => request<Omit<User, 'token'>>('/api/v1/auth/me'),
  chat: (question: string, mode = 'hybrid', history: { role: 'user' | 'assistant'; content: string }[] = []) => request<Result>('/api/v1/chat', { method: 'POST', body: JSON.stringify({ question, mode, history }) }),
  health: () => request<Record<string, any>>('/health'),
  status: () => request<Record<string, any>>('/api/v1/ingestion/status'),
  datasets: () => request<DatasetInfo[]>('/api/v1/ingestion/datasets'),
  monitoring: () => request<Monitoring>('/api/v1/monitoring/overview'),
  ontology: () => request<Ontology>('/api/v1/graph/ontology'),
  mappings: () => request<ObjectMapping[]>('/api/v1/ingestion/mappings'),
  saveMappings: (dataset: string, mappings: ObjectMapping[]) => request<{ valid: boolean; errors: string[]; saved: boolean }>('/api/v1/ingestion/mappings', { method: 'PUT', body: JSON.stringify({ dataset, mappings }) }),
  activeDataset: () => request<{ dataset: string }>('/api/v1/ingestion/active'),
  setActiveDataset: (dataset: string) => request<{ dataset: string }>('/api/v1/ingestion/active', { method: 'PUT', body: JSON.stringify({ dataset }) }),
  startIngestion: (dataset: string, mode: 'reset' | 'append' = 'reset') => request<IngestionJob>('/api/v1/ingestion/jobs', { method: 'POST', body: JSON.stringify({ dataset, mode, load_graph: true, load_vectors: true }) }),
  ingestionJob: (id: string) => request<IngestionJob>(`/api/v1/ingestion/jobs/${id}`),
  csvConnectors: () => request<CsvConnector[]>('/api/v1/connectors/csv'),
  csvConnector: (id: string) => request<CsvConnector>(`/api/v1/connectors/csv/${id}`),
  uploadCsv: (file: File) => { const body = new FormData(); body.append('file', file); return request<CsvConnector>('/api/v1/connectors/csv', { method: 'POST', body }); },
  stats: () => request<Record<string, any>>('/api/v1/graph/stats'),
  search: (q: string) => request<{ entity: string; label: string; type?: string }[]>('/api/v1/graph/search?q=' + encodeURIComponent(q)),
  neighbors: (uri: string, depth = 1) => request<Graph>(`/api/v1/graph/neighbors?depth=${depth}&uri=${encodeURIComponent(uri)}`),
  evaluate: () => request<Record<string, unknown>>('/api/v1/evaluation/run', { method: 'POST' }),
  results: () => request<Record<string, unknown>>('/api/v1/evaluation/results'),
};
