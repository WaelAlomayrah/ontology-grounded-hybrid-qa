import { FormEvent, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Result, SupportingGraph } from '../types/api';

const samplesByDataset: Record<string, string[]> = {
  policeuk: [
    'ما المناطق التي سجلت أعلى معدل لجرائم المركبات لكل ألف نسمة؟',
    'ما النتائج المسجلة لجرائم المركبات في المناطق ذات أعلى معدل؟',
    'اعرض الأدلة والعلاقات التي استخدمتها للوصول إلى هذه الإجابة.',
    'Which LSOAs recorded the highest vehicle-crime rate per 1,000 residents?',
  ],
  arabic_enterprise: [
    'في أي إدارة يعمل الموظف سعود العمري؟',
    'ما المورد الذي يورد نظام الموارد البشرية المؤسسية 1؟',
    'من هو مورد النظام المستخدم في مشروع تطوير الخدمات الرقمية 1؟',
    'من أعد المستند «إجراء إدارة البيانات رقم 1»؟',
    'كم عدد الموظفين في الإدارة التنفيذية؟',
    'ما الأنظمة التي تستخدمها مشاريع إدارة البيانات؟',
  ],
  kg2qa: [
    'What is "fitting procedures" relevant to?',
    'What is "DCE-to-DCE signalling" relevant to?',
    'What does "dense wavelength division multiplexing (DWDM) systems" limit?',
  ],
  sample: [
    'Which vendor supplies the system used by Project Atlas?',
    'Who manages the owner of the Case Management System?',
    'Which projects involve employees in Riyadh?',
  ],
};
type Turn = { question: string; result?: Result; pending?: boolean; error?: string };
type Session = { id: string; title: string; turns: Turn[]; updated: number };

export default function ChatPage() {
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [sessions, setSessions] = useState<Session[]>(() => { try { return JSON.parse(localStorage.getItem('ontology-chats') || '[]'); } catch { return []; } });
  const [sessionId, setSessionId] = useState<string>(() => sessions[0]?.id ?? crypto.randomUUID());
  const [turns, setTurns] = useState<Turn[]>(() => sessions[0]?.turns ?? []);
  const active = useQuery({ queryKey: ['active-dataset'], queryFn: api.activeDataset });
  const samples = samplesByDataset[active.data?.dataset ?? 'sample'] ?? samplesByDataset.sample;
  const bottom = useRef<HTMLDivElement>(null);
  const mutation = useMutation({ mutationFn: ({ text, selectedMode, history }: { text: string; selectedMode: string; history: { role: 'user' | 'assistant'; content: string }[] }) => api.chat(text, selectedMode, history) });
  useEffect(() => bottom.current?.scrollIntoView({ behavior: 'smooth' }), [turns]);
  useEffect(() => { const next = [{ id: sessionId, title: turns[0]?.question.slice(0, 48) || 'New investigation', turns: turns.filter(turn => !turn.pending), updated: Date.now() }, ...sessions.filter(item => item.id !== sessionId)].slice(0, 20); setSessions(next); localStorage.setItem('ontology-chats', JSON.stringify(next)); }, [turns]);

  function openSession(session: Session) { setSessionId(session.id); setTurns(session.turns); }
  function newSession() { setSessionId(crypto.randomUUID()); setTurns([]); }
  function renameSession(session: Session) { const title = window.prompt('Conversation name', session.title); if (title) { const next = sessions.map(item => item.id === session.id ? { ...item, title } : item); setSessions(next); localStorage.setItem('ontology-chats', JSON.stringify(next)); } }
  function removeSession(id: string) { const next = sessions.filter(item => item.id !== id); setSessions(next); localStorage.setItem('ontology-chats', JSON.stringify(next)); if (id === sessionId) newSession(); }

  async function ask(text: string) {
    const clean = text.trim();
    if (!clean || mutation.isPending) return;
    const index = turns.length;
    setTurns(previous => [...previous, { question: clean, pending: true }]);
    setQuestion('');
    try {
      const history = turns.flatMap(turn => turn.result ? [{ role: 'user' as const, content: turn.question }, { role: 'assistant' as const, content: turn.result.answer }] : []).slice(-8);
      const result = await mutation.mutateAsync({ text: clean, selectedMode: mode, history });
      setTurns(previous => previous.map((turn, i) => i === index ? { question: clean, result } : turn));
    } catch (error) {
      setTurns(previous => previous.map((turn, i) => i === index ? { question: clean, error: error instanceof Error ? error.message : 'Request failed' } : turn));
    }
  }
  function submit(event: FormEvent) { event.preventDefault(); void ask(question); }

  return <section className="chat-layout"><aside className="chat-sidebar"><button className="new-chat" onClick={newSession}>＋ New conversation</button><small>Saved investigations</small>{sessions.filter(item => item.turns.length).map(session => <div className={session.id === sessionId ? 'active' : ''} key={session.id}><button onClick={() => openSession(session)}><strong>{session.title}</strong><span>{new Date(session.updated).toLocaleDateString()}</span></button><button title="Rename" onClick={() => renameSession(session)}>✎</button><button title="Delete" onClick={() => removeSession(session.id)}>×</button></div>)}</aside><div className="chat-page">
    <div className="hero compact-hero">
      <div><span className="eyebrow">Knowledge workspace · {active.data?.dataset ?? 'loading dataset'}</span><h1>Ask, investigate, continue.</h1><p>Every response stays in context visually, with its evidence and ontology path close at hand.</p></div>
      <div className="mode-switch" aria-label="Retrieval mode">{['hybrid', 'graph_only', 'vector_only'].map(value => <button className={mode === value ? 'active' : ''} key={value} onClick={() => setMode(value)}>{value.replace('_', ' ')}</button>)}</div>
    </div>

    {turns.length === 0 && <div className="welcome-panel">
      <div className="orb">✦</div><h2>Start with a question about your data</h2><p>I’ll combine semantic retrieval with explicit graph relationships and show you why the answer is supported.</p>
      <div className="suggestion-grid">{samples.map((sample, index) => <button dir={active.data?.dataset === 'arabic_enterprise' ? 'rtl' : 'ltr'} key={sample} onClick={() => void ask(sample)}><span>{String(index + 1).padStart(2, '0')}</span>{sample}</button>)}</div>
    </div>}

    <div className="conversation">
      {turns.map((turn, index) => <div className="turn" key={`${turn.question}-${index}`}>
        <div className="user-message"><span>You</span><p>{turn.question}</p></div>
        {turn.pending && <div className="assistant-message loading-card"><div className="thinking"><i /><i /><i /></div><p>Traversing the graph and ranking evidence…</p></div>}
        {turn.error && <div className="error">{turn.error}</div>}
        {turn.result && <Answer result={turn.result} />}
      </div>)}
      <div ref={bottom} />
    </div>

    <form className="composer" onSubmit={submit}>
      <textarea value={question} onChange={event => setQuestion(event.target.value)} placeholder={turns.length ? 'Ask a follow-up question…' : 'Ask the knowledge graph…'} maxLength={1000} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(event); } }} />
      <div className="composer-footer"><span>↵ send · shift + ↵ new line</span><button disabled={mutation.isPending || !question.trim()}>Ask <b>→</b></button></div>
    </form>
  </div></section>;
}

function Answer({ result }: { result: Result }) {
  const [comparison, setComparison] = useState<{ graph?: Result; vector?: Result; loading?: boolean }>();
  async function compare() { setComparison({ loading: true }); const [graph, vector] = await Promise.all([api.chat(result.question, 'graph_only'), api.chat(result.question, 'vector_only')]); setComparison({ graph, vector }); }
  function openEntity(label: string) { sessionStorage.setItem('graphSearch', label); window.location.href = '/graph'; }
  function openSupportingGraph() {
    const payload: SupportingGraph = {
      graph: result.graph,
      facts: result.retrieval.graph_facts,
      question: result.question,
    };
    sessionStorage.setItem('supportingGraph', JSON.stringify(payload));
  }
  return <article className="assistant-message answer-card">
    <div className="answer-top"><div className="assistant-avatar">O</div><div><strong>Ontology assistant</strong><span>Grounded response</span></div><span className={`status-badge ${result.answer_status}`}>{result.answer_status.replaceAll('_', ' ')}</span></div>
    <p className="answer-text">{result.answer}</p>
    {result.warnings.map(warning => <p className="warning" key={warning}>{warning}</p>)}
    <div className="evidence-strip">
      <div><small>Confidence</small><strong>{Math.round(result.confidence * 100)}%</strong><span className="meter"><i style={{ width: `${result.confidence * 100}%` }} /></span></div>
      <div><small>Graph facts</small><strong>{result.retrieval.graph_facts.length}</strong></div>
      <div><small>Entities</small><strong>{result.entities.length}</strong></div>
      <div><small>Latency</small><strong>{Math.round(result.retrieval.timings_ms.total ?? 0)} ms</strong></div>
    </div>
    <div className="entity-chips">{result.entities.slice(0, 8).map(entity => <button onClick={() => openEntity(entity.label)} key={entity.entity_uri}>{entity.label}<small>{entity.source}</small></button>)}</div>
    <details><summary>Inspect supporting evidence</summary><pre>{JSON.stringify(result.retrieval.graph_facts, null, 2)}</pre></details>
    {comparison && <div className="comparison">{comparison.loading ? <p>Running baseline comparison…</p> : <><article><small>Graph only · {Math.round((comparison.graph?.confidence ?? 0) * 100)}%</small><p>{comparison.graph?.answer}</p></article><article><small>Vector only · {Math.round((comparison.vector?.confidence ?? 0) * 100)}%</small><p>{comparison.vector?.answer}</p></article></>}</div>}
    <div className="answer-actions"><Link className="button secondary" to="/graph" onClick={openSupportingGraph}>Open supporting graph</Link><button className="button secondary" onClick={() => void compare()}>Compare retrieval</button><span>Sources: {result.sources.join(', ') || 'none'}</span></div>
  </article>;
}
