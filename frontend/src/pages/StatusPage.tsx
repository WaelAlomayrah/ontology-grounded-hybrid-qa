import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import type { ContainerLoad, User } from '../types/api';

const bytes = (value = 0) => value > 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(1)} GB` : `${(value / 1024 ** 2).toFixed(0)} MB`;
const rate = (value = 0) => value > 1024 ** 2 ? `${(value / 1024 ** 2).toFixed(1)} MB/s` : `${(value / 1024).toFixed(1)} KB/s`;
const cleanName = (name: string) => name.replace('ontology-ai-pilot-', '').replace(/-1$/, '').replaceAll('-', ' ');

export default function StatusPage({ role }: { role: User['role'] }) {
  const [exporting, setExporting] = useState<string>();
  const [exportError, setExportError] = useState('');
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 10000 });
  const status = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 15000 });
  const monitoring = useQuery({ queryKey: ['monitoring'], queryFn: api.monitoring, refetchInterval: 10000 });
  const datasets = useQuery({ queryKey: ['datasets'], queryFn: api.datasets });
  const services = health.data?.services ?? {};
  const activeContainers = monitoring.data?.containers.filter(container => container.running && container.name !== 'docker runtime').length;
  async function exportDataset(dataset: string) {
    setExporting(dataset); setExportError('');
    try { await api.exportDataset(dataset); }
    catch (reason) { setExportError(reason instanceof Error ? reason.message : 'Dataset export failed'); }
    finally { setExporting(undefined); }
  }

  return <section className="operations-page">
    <div className="page-heading"><div><span className="eyebrow">Live operations</span><h1>System observability</h1><p>Health, container load, ingestion state, and available research datasets in one view.</p></div><a className="button secondary" href="http://localhost:3001" target="_blank" rel="noreferrer">Open Grafana ↗</a></div>
    <div className="summary-grid">
      <article><span className="summary-icon green">✓</span><div><small>Platform status</small><strong>{health.data?.status ?? 'Checking'}</strong><span>Core retrieval services</span></div></article>
      <article><span className="summary-icon blue">◫</span><div><small>Active containers</small><strong>{activeContainers ?? '—'}</strong><span>Reported by Docker Engine</span></div></article>
      <article><span className="summary-icon purple">◇</span><div><small>Indexed vectors</small><strong>{status.data?.vector_count ?? '—'}</strong><span>Milvus collection</span></div></article>
      <article><span className="summary-icon amber">▤</span><div><small>Datasets found</small><strong>{datasets.data?.length ?? '—'}</strong><span>Mounted under /data</span></div></article>
    </div>
    <div className="ingestion-status"><div><span className="eyebrow">Active workspace</span><h2>{status.data?.workspace?.active_dataset ?? 'sample'}</h2><p>Activated {status.data?.workspace?.activated_at ? new Date(status.data.workspace.activated_at).toLocaleString() : 'before status tracking'}</p></div><div><span className="eyebrow">Latest ingestion</span><h2>{status.data?.latest_report ? `${status.data.latest_report.entities_processed} entities` : 'No report since restart'}</h2><p>{status.data?.latest_report ? `${status.data.latest_report.vectors_generated} vectors · ${status.data.latest_report.elapsed_time}s` : 'Persisted vectors remain available in Milvus.'}</p></div></div>

    <div className="section-title"><div><h2>Container status & load</h2><p>{monitoring.data?.load_scope ?? 'Live service probes and two-minute resource rates, refreshed every 10 seconds.'}</p></div><span className="refresh-dot"><i /> Live</span></div>
    {monitoring.data?.available === false && <div className="warning">Prometheus metrics are temporarily unavailable.</div>}
    <div className="container-grid">{monitoring.data?.containers.map(container => <ContainerCard key={container.name} container={container} />)}</div>

    <div className="ops-columns">
      <div><div className="section-title"><div><h2>Service targets</h2><p>Application checks and Prometheus scrape state.</p></div></div><div className="service-list">
        {Object.entries(services).map(([name, value]) => { const up = typeof value === 'boolean' ? value : Boolean((value as { healthy?: boolean } | null)?.healthy); return <div key={name}><span className={up ? 'service-up' : 'service-down'}>{up ? '✓' : '!'}</span><div><strong>{name}</strong><small>{up ? 'Healthy and responding' : 'Unavailable'}</small></div><b>{up ? 'Online' : 'Offline'}</b></div>; })}
        {monitoring.data?.targets.map(target => <div key={`${target.job}-${target.instance}`}><span className={target.up ? 'service-up' : 'service-down'}>{target.up ? '✓' : '!'}</span><div><strong>{target.job}</strong><small>{target.instance}</small></div><b>{target.up ? 'Scraping' : 'Down'}</b></div>)}
      </div></div>
      <div><div className="section-title"><div><h2>Available datasets</h2><p>Download a complete, self-contained ZIP without changing source files.</p></div></div>{exportError && <div className="error dataset-export-error">{exportError}</div>}<div className="dataset-list">{datasets.data?.map(dataset => <article key={dataset.id}><div className="dataset-head"><span>DB</span><div><h3>{dataset.name}</h3><small>{dataset.files} files · {dataset.data_files} data tables/resources</small></div><b className={dataset.supported_for_ingestion ? 'ready-tag' : 'source-tag'}>{dataset.supported_for_ingestion ? 'ingestion ready' : 'source available'}</b>{dataset.exportable !== false && <button className="dataset-export" disabled={role === 'viewer' || exporting === dataset.id} onClick={() => void exportDataset(dataset.id)}>{exporting === dataset.id ? 'Preparing…' : 'Export ZIP'}</button>}</div>{dataset.archive_preview.length > 0 && <details><summary>{dataset.archives} archive · preview contents</summary><p>{dataset.archive_preview.slice(0, 8).join(' · ')}</p></details>}</article>)}</div></div>
    </div>
  </section>;
}

function ContainerCard({ container }: { container: ContainerLoad }) {
  const legacy = container as ContainerLoad & { cpu_cores?: number };
  const cpuPercent = Math.min(container.cpu_percent ?? (legacy.cpu_cores ?? 0) * 100, 100);
  const running = container.running !== false;
  const hasLoad = container.cpu_percent !== undefined || legacy.cpu_cores !== undefined || container.memory_bytes !== undefined;
  const state = container.health && container.health !== 'none' ? container.health : container.state ?? (running ? 'running' : 'unavailable');
  return <article className="container-card"><div className="container-head"><span className="cube">◇</span><div><strong>{cleanName(container.name)}</strong><small className={running ? '' : 'offline'}><i /> {state}</small>{container.status && <em>{container.status}</em>}</div><b>{hasLoad ? `${cpuPercent.toFixed(1)}%` : '—'}</b></div><div className="load-row"><span>CPU</span><div><i style={{ width: `${hasLoad ? Math.max(cpuPercent, 1) : 0}%` }} /></div><b>{hasLoad ? `${cpuPercent.toFixed(1)}%` : 'n/a'}</b></div><div className="metric-row"><span><small>Memory</small><b>{hasLoad ? bytes(container.memory_bytes) : 'n/a'}</b></span><span><small>Network ↓</small><b>{hasLoad ? rate(container.network_receive_bps) : 'n/a'}</b></span><span><small>Network ↑</small><b>{hasLoad ? rate(container.network_transmit_bps) : 'n/a'}</b></span></div></article>;
}
