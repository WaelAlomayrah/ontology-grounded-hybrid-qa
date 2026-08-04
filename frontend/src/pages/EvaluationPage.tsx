import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState, type CSSProperties } from 'react';
import { api } from '../api/client';

type Metric = 'keyword_coverage' | 'entity_recall' | 'graph_path_recall' | 'ontology_alignment';
type Row = Record<Metric, number> & { id: string; latency_ms: number; answer_status: string };
type Mode = { averages: Record<Metric | 'latency_ms', number>; questions: Row[] };
type Pair = { without: number; with: number };
type Evaluation = { created_at: string; question_count: number; dataset?: string; embedding_model?: string; modes: Record<string, Mode>; ontology?: { typed_entity_coverage: number; relationship_grounding: number; grounding_score: number; graph_activation_rate?: number; description: string }; ontology_ablation?: { without_ontology: number; with_ontology: number; absolute_gain: number; metrics?: Record<string, Pair>; method: string } };
const meta: Record<string, { label: string; color: string; note: string }> = {
  graph_only: { label: 'Graph', color: '#5b3fc0', note: 'Structured facts and paths' }, vector_only: { label: 'Vector', color: '#06756f', note: 'Semantic similarity' }, hybrid: { label: 'Hybrid', color: '#b54708', note: 'Graph + semantic evidence' },
};
const metrics: { key: Metric; label: string }[] = [{ key: 'keyword_coverage', label: 'Answer coverage' }, { key: 'entity_recall', label: 'Entity recall' }, { key: 'graph_path_recall', label: 'Path recall' }, { key: 'ontology_alignment', label: 'Typed entities' }];
const pct = (value = 0) => `${Math.round(value * 100)}%`;
const modeScore = (mode?: Mode) => mode ? (mode.averages.keyword_coverage + mode.averages.entity_recall + mode.averages.graph_path_recall) / 3 : 0;
const rowScore = (row: Row) => (row.keyword_coverage + row.entity_recall + row.graph_path_recall) / 3;

export default function EvaluationPage() {
  const options = useQuery({ queryKey: ['evaluation-options'], queryFn: api.evaluationOptions });
  const evaluationDatasets = [...new Set([...(options.data?.datasets ?? []), 'policeuk'])];
  const [dataset, setDataset] = useState('arabic_enterprise');
  const [embeddingModel, setEmbeddingModel] = useState('e5-large');
  const [jobId, setJobId] = useState<string | null>(null);
  useEffect(() => {
    if (!options.data) return;
    setDataset(options.data.active.active_dataset || 'arabic_enterprise');
    setEmbeddingModel(options.data.active.embedding_model || 'e5-large');
  }, [options.data]);
  const latest = useQuery({ queryKey: ['evaluation', dataset, embeddingModel], queryFn: () => api.results(dataset, embeddingModel), retry: false });
  const job = useQuery({
    queryKey: ['evaluation-job', jobId],
    queryFn: () => api.evaluationJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: query => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1000 : false,
  });
  const run = useMutation({ mutationFn: api.startEvaluation, onSuccess: result => setJobId(result.id) });
  useEffect(() => {
    if (job.data?.status === 'complete') void latest.refetch();
  }, [job.data?.status]);
  const data = latest.data as Evaluation | undefined;
  const running = run.isPending || job.data?.status === 'queued' || job.data?.status === 'running';
  const modes = data ? Object.entries(data.modes).filter(([key]) => meta[key]) : [];
  const ontology = data?.ontology?.grounding_score ?? ((data?.modes.hybrid?.averages.ontology_alignment ?? 0) + (data?.modes.hybrid?.averages.graph_path_recall ?? 0)) / 2;
  const withoutOntology = data?.ontology_ablation?.without_ontology ?? modeScore(data?.modes.vector_only);
  const withOntology = data?.ontology_ablation?.with_ontology ?? modeScore(data?.modes.hybrid);
  const ontologyGain = data?.ontology_ablation?.absolute_gain ?? withOntology - withoutOntology;
  const vector = data?.modes.vector_only, hybrid = data?.modes.hybrid;
  const pair = (key: string, fallback: Pair): Pair => data?.ontology_ablation?.metrics?.[key] ?? fallback;
  const impactMetrics = data && vector && hybrid ? [
    { label: 'Answer accuracy', detail: 'Expected answer keyword coverage', values: pair('answer_accuracy', { without: vector.averages.keyword_coverage, with: hybrid.averages.keyword_coverage }) },
    { label: 'Evidence accuracy', detail: 'Entity and relationship evidence recall', values: pair('evidence_accuracy', { without: (vector.averages.entity_recall + vector.averages.graph_path_recall) / 2, with: (hybrid.averages.entity_recall + hybrid.averages.graph_path_recall) / 2 }) },
    { label: 'Entity recall', detail: 'Expected entities retrieved', values: pair('entity_recall', { without: vector.averages.entity_recall, with: hybrid.averages.entity_recall }) },
    { label: 'Relationship grounding', detail: 'Expected graph paths recovered', values: pair('relationship_grounding', { without: vector.averages.graph_path_recall, with: hybrid.averages.graph_path_recall }) },
    { label: 'Answer reliability', detail: 'Questions completed with an answered status', values: { without: vector.questions.filter(row => row.answer_status === 'answered').length / vector.questions.length, with: hybrid.questions.filter(row => row.answer_status === 'answered').length / hybrid.questions.length } },
  ] : [];
  const best = modes.reduce((winner, item) => modeScore(item[1]) > modeScore(winner?.[1]) ? item : winner, modes[0]);
  return <section className="evaluation-page">
    <div className="evaluation-hero"><div><span className="eyebrow">Quality lab</span><h1>Retrieval evaluation</h1><p>Choose an indexed dataset and embedding model, then compare graph, vector, hybrid, and ontology grounding.</p></div><div className="evaluation-run-config"><label>Dataset<select value={dataset} onChange={event => setDataset(event.target.value)} disabled={running}>{evaluationDatasets.map(item => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></label><label>Embedding model<select value={embeddingModel} onChange={event => setEmbeddingModel(event.target.value)} disabled={running}>{options.data?.models.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><small>{running ? `${(job.data?.phase ?? 'starting').replaceAll('_', ' ')} · ${job.data?.progress ?? 0}%${job.data?.completed_questions ? ` · ${job.data.completed_questions}/${job.data.total_retrievals}` : ''}` : options.data?.indexed.some(item => item.dataset === dataset && item.embedding_model === embeddingModel) ? 'Index ready for evaluation' : 'Ingest this dataset/model combination first'}</small><div className="evaluation-actions"><button onClick={() => run.mutate({ dataset, embeddingModel })} disabled={running || !options.data?.indexed.some(item => item.dataset === dataset && item.embedding_model === embeddingModel)}>{running ? `Running ${job.data?.progress ?? 0}%` : 'Run evaluation'}</button>{data && <a className="button secondary" href={`data:application/json,${encodeURIComponent(JSON.stringify(data, null, 2))}`} download={`${dataset}-${embeddingModel}-evaluation.json`}>Export JSON</a>}</div></div></div>
    {(run.error || job.error || job.data?.status === 'failed') && <div className="error">{run.error?.message ?? job.error?.message ?? job.data?.error ?? 'Evaluation failed'}</div>}
    {!data && !latest.isLoading && <div className="empty-state"><h2>No evaluation results yet</h2><p>Run the benchmark to generate the dashboard.</p></div>}
    {data && <><div className="evaluation-meta"><span>{data.question_count} questions</span><span>Dataset: {data.dataset ?? dataset}</span><span>Model: {data.embedding_model ?? embeddingModel}</span><span>Last run {new Date(data.created_at).toLocaleString()}</span><span>Best overall: {best ? meta[best[0]].label : '—'}</span></div>
      <article className="evaluation-panel ablation-panel"><div className="impact-heading"><div><span className="eyebrow">Primary analysis</span><h2>What does the ontology improve?</h2><p>Controlled comparison across accuracy, evidence quality, and response cost.</p></div><div className={`impact-verdict ${ontologyGain < 0 ? 'negative' : ''}`}><small>Overall quality impact</small><strong>{ontologyGain >= 0 ? '+' : ''}{pct(ontologyGain)}</strong><span>{ontologyGain >= 0 ? 'improvement with ontology' : 'decrease with ontology'}</span></div></div><div className="impact-table"><div className="impact-header"><span>Evaluation ground</span><span>Without ontology</span><span>With ontology</span><span>Impact</span></div>{impactMetrics.map(metric => { const delta = metric.values.with - metric.values.without; return <div className="impact-row" key={metric.label}><div><b>{metric.label}</b><small>{metric.detail}</small></div><strong>{pct(metric.values.without)}</strong><strong className="ontology-value">{pct(metric.values.with)}</strong><span className={delta < 0 ? 'delta negative' : 'delta'}>{delta >= 0 ? '+' : ''}{pct(delta)}</span></div>; })}<div className="impact-row latency-impact"><div><b>Latency</b><small>Average end-to-end retrieval time</small></div><strong>{Math.round(vector?.averages.latency_ms ?? 0)} ms</strong><strong className="ontology-value">{Math.round(hybrid?.averages.latency_ms ?? 0)} ms</strong><span className={(hybrid?.averages.latency_ms ?? 0) <= (vector?.averages.latency_ms ?? 0) ? 'delta' : 'delta cost'}>{Math.round((hybrid?.averages.latency_ms ?? 0) - (vector?.averages.latency_ms ?? 0)) >= 0 ? '+' : ''}{Math.round((hybrid?.averages.latency_ms ?? 0) - (vector?.averages.latency_ms ?? 0))} ms</span></div></div><p className="method-note">{data.ontology_ablation?.method ?? 'Without ontology uses vector-only semantic retrieval. With ontology uses hybrid retrieval with typed Fuseki graph evidence.'}</p></article>
      <div className="supporting-title"><div><h2>Supporting retrieval detail</h2><p>Individual mode scores behind the ontology impact analysis.</p></div></div><div className="score-grid">{modes.map(([key, mode]) => <article className="score-card" key={key} style={{ '--accent': meta[key].color } as CSSProperties}><span>{meta[key].label}</span><strong>{pct(modeScore(mode))}</strong><p>{meta[key].note}</p><small>{Math.round(mode.averages.latency_ms)} ms average</small></article>)}<article className="score-card ontology-score"><span>Ontology grounding</span><strong>{pct(ontology)}</strong><p>Typed entities + relation grounding</p><small>{pct(data.ontology?.typed_entity_coverage ?? data.modes.hybrid?.averages.ontology_alignment)} typed coverage</small></article></div>
      <div className="evaluation-grid"><article className="evaluation-panel"><PanelTitle title="Quality by metric" subtitle="Higher is better" />{metrics.map(metric => <div className="metric-group" key={metric.key}><b>{metric.label}</b>{modes.map(([key, mode]) => <div className="metric-row" key={key}><span>{meta[key].label}</span><div className="bar-track"><i style={{ width: pct(mode.averages[metric.key]), background: meta[key].color }} /></div><strong>{pct(mode.averages[metric.key])}</strong></div>)}</div>)}</article>
        <article className="evaluation-panel"><PanelTitle title="Speed and reliability" subtitle="Latency and completed answers" /><div className="latency-list">{modes.map(([key, mode]) => { const answered = mode.questions.filter(row => row.answer_status === 'answered').length / mode.questions.length; return <div key={key}><div><i className="mode-dot" style={{ background: meta[key].color }} /><b>{meta[key].label}</b><strong>{Math.round(mode.averages.latency_ms)} ms</strong></div><div className="reliability"><i style={{ width: pct(answered), background: meta[key].color }} /><span>{pct(answered)} answered</span></div></div>; })}</div><div className="ontology-breakdown"><h3>Ontology grounding</h3><div><span>Graph activation</span><strong>{pct(data.ontology?.graph_activation_rate ?? 0)}</strong></div><div><span>Typed graph coverage</span><strong>{pct(data.ontology?.typed_entity_coverage ?? data.modes.hybrid?.averages.ontology_alignment)}</strong></div><div><span>Relationship grounding</span><strong>{pct(data.ontology?.relationship_grounding ?? data.modes.hybrid?.averages.graph_path_recall)}</strong></div><p>{data.ontology?.description ?? 'Calculated from typed entities and expected graph paths in hybrid retrieval.'}</p></div></article></div>
      <article className="evaluation-panel question-panel"><PanelTitle title="Question-level comparison" subtitle="Overall quality score for each benchmark question" /><div className="evaluation-table-wrap"><table><thead><tr><th>Question</th>{modes.map(([key]) => <th key={key}>{meta[key].label}</th>)}<th>Best</th></tr></thead><tbody>{data.modes.hybrid.questions.map((_, index) => { const rows = modes.map(([key, mode]) => [key, mode.questions[index]] as const); const winner = rows.reduce((a, b) => rowScore(b[1]) > rowScore(a[1]) ? b : a); return <tr key={winner[1].id}><td>{winner[1].id}</td>{rows.map(([key, row]) => <td key={key}><b style={{ color: meta[key].color }}>{pct(rowScore(row))}</b></td>)}<td><span className="winner-pill" style={{ color: meta[winner[0]].color }}>{meta[winner[0]].label}</span></td></tr>; })}</tbody></table></div></article>
    </>}
  </section>;
}
function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) { return <div className="panel-heading"><div><h2>{title}</h2><p>{subtitle}</p></div></div>; }
