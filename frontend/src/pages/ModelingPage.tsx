import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ObjectMapping, User } from '../types/api';

type View = 'connectors' | 'mapping' | 'ontology' | 'guide';
type ColumnRole = ObjectMapping['columns'][number]['role'];

const localName = (uri = '') => decodeURIComponent(uri.split(/[#/]/).pop() || '—').replaceAll('_', ' ');
const ingestionName = (dataset: string) => dataset.startsWith('csv:') ? dataset : dataset === 'KG2QA_ontology_dataset' ? 'kg2qa' : dataset === 'Northwind_dataset' ? 'northwind' : dataset === 'Arabic_enterprise_dataset' ? 'arabic_enterprise' : dataset.toLowerCase() === 'policeuk' ? 'policeuk' : 'sample';
const preparedDatasets = ['KG2QA_ontology_dataset', 'Northwind_dataset', 'Arabic_enterprise_dataset', 'policeuk'];
const roleOptions: { value: ColumnRole; label: string; help: string }[] = [
  { value: 'identifier', label: 'Unique ID', help: 'A stable value that distinguishes each item.' },
  { value: 'label', label: 'Display name', help: 'The name people should see.' },
  { value: 'attribute', label: 'Detail', help: 'A description, date, category, amount, or other fact.' },
  { value: 'source', label: 'From item', help: 'The ID where a connection starts.' },
  { value: 'target', label: 'To item', help: 'The ID where a connection ends.' },
  { value: 'predicate', label: 'Connection name', help: 'A column containing names such as worksFor.' },
  { value: 'ignore', label: 'Do not import', help: 'Leave this column out of the knowledge model.' },
];

function readiness(mapping: ObjectMapping): string[] {
  const roles = new Set(mapping.columns.map(column => column.role));
  const missing = mapping.mapping_kind === 'entity'
    ? [['identifier', 'a Unique ID'], ['label', 'a Display name']]
    : [['source', 'a From item'], ['target', 'a To item']];
  const issues = missing.filter(([role]) => !roles.has(role as ColumnRole)).map(([, label]) => `Choose ${label}`);
  if (!mapping.target_class.trim()) issues.unshift(`Name this ${mapping.mapping_kind === 'entity' ? 'type of thing' : 'connection'}`);
  return issues;
}

export default function ModelingPage({ role }: { role: User['role'] }) {
  const client = useQueryClient();
  const [view, setView] = useState<View>('connectors');
  const [dataset, setDataset] = useState('KG2QA_ontology_dataset');
  const [expanded, setExpanded] = useState<string>();
  const [drafts, setDrafts] = useState<ObjectMapping[]>([]);
  const [validation, setValidation] = useState<string[]>([]);
  const [actionError, setActionError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [jobId, setJobId] = useState<string>();
  const [mode, setMode] = useState<'reset' | 'append'>('append');
  const [embeddingModel, setEmbeddingModel] = useState('e5-large');
  const [embeddingDevice, setEmbeddingDevice] = useState<'cpu' | 'cuda'>('cpu');
  const [batchSize, setBatchSize] = useState(16);
  const [scope, setScope] = useState<'incremental' | 'graph_only' | 'vectors_only' | 'full_rebuild'>('incremental');
  const [savePrecomputed, setSavePrecomputed] = useState(false);
  const mappings = useQuery({ queryKey: ['object-mappings'], queryFn: api.mappings });
  const ingestionOptions = useQuery({ queryKey: ['ingestion-options'], queryFn: api.ingestionOptions });
  const ontology = useQuery({ queryKey: ['ontology'], queryFn: api.ontology });
  const active = useQuery({ queryKey: ['active-dataset'], queryFn: api.activeDataset });
  const job = useQuery({ queryKey: ['ingestion-job', jobId], queryFn: () => api.ingestionJob(jobId!), enabled: Boolean(jobId), refetchInterval: query => ['complete', 'failed'].includes(query.state.data?.status ?? '') ? false : 1200 });
  const datasetNames = useMemo(
    () => [...new Set([...preparedDatasets, ...(mappings.data?.map(item => item.dataset) ?? [])])],
    [mappings.data],
  );
  useEffect(() => setDrafts((mappings.data ?? []).filter(item => item.dataset === dataset)), [mappings.data, dataset]);
  useEffect(() => { if (job.data?.status === 'complete') void client.invalidateQueries({ queryKey: ['active-dataset'] }); }, [client, job.data?.status]);

  const editable = role !== 'viewer';
  const nativeFolderDataset = preparedDatasets.includes(dataset);
  const policeUkDataset = dataset === 'policeuk';
  const switchableDatasets = [...new Set(
    (ingestionOptions.data?.indexes ?? [])
      .filter(index => ingestionOptions.data?.graph_datasets.includes(index.dataset))
      .map(index => index.dataset),
  )];
  async function activateDataset(nextDataset: string) {
    if (!nextDataset || nextDataset === active.data?.dataset) return;
    setActionError('');
    try {
      const matchingIndex = ingestionOptions.data?.indexes.find(index => index.dataset === nextDataset);
      await api.setActiveDataset(nextDataset, matchingIndex?.embedding_model);
      await Promise.all([
        client.invalidateQueries({ queryKey: ['active-dataset'] }),
        client.invalidateQueries({ queryKey: ['ingestion-options'] }),
        client.invalidateQueries({ queryKey: ['evaluation-options'] }),
      ]);
      setActionMessage(`${nextDataset.replaceAll('_', ' ')} is now active.`);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : 'Dataset activation failed');
    }
  }
  function updateMapping(source: string, change: Partial<ObjectMapping>) {
    setDrafts(items => items.map(item => item.source === source ? { ...item, ...change } : item));
  }
  function updateColumn(source: string, columnName: string, field: 'target' | 'role', value: string) {
    setDrafts(items => items.map(item => item.source !== source ? item : {
      ...item,
      columns: item.columns.map(column => column.source === columnName ? { ...column, [field]: value } : column),
    } as ObjectMapping));
  }
  async function save() {
    setActionError(''); setActionMessage('');
    try {
      const result = await api.saveMappings(dataset, drafts);
      setValidation(result.errors);
      if (result.saved) {
        setActionMessage('Mapping checked and saved successfully.');
        await client.invalidateQueries({ queryKey: ['object-mappings'] });
      }
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : 'The mapping could not be saved.');
    }
  }
  async function ingest() {
    setActionError(''); setActionMessage('');
    try {
      const fullRebuild = scope === 'full_rebuild';
      const started = await api.startIngestion({
        dataset: ingestionName(dataset),
        mode: fullRebuild ? 'reset' : mode,
        load_graph: scope !== 'vectors_only',
        load_vectors: scope !== 'graph_only',
        embedding_model: embeddingModel,
        embedding_device: embeddingDevice,
        embedding_batch_size: batchSize,
        incremental: scope === 'incremental',
        use_precomputed: true,
        save_precomputed: savePrecomputed,
      });
      setJobId(started.id);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : 'The knowledge graph build could not be started.');
    }
  }

  return <section className="modeling-page">
    <div className="page-heading">
      <div><span className="eyebrow">Guided knowledge modeling</span><h1>Build a knowledge model</h1><p>No ontology or coding experience is needed. Describe what each row and column means in everyday language.</p></div>
      <label className="active-dataset">Active graph and vectors
        <select value={active.data?.dataset ?? ''} disabled={role === 'viewer'} onChange={event => void activateDataset(event.target.value)}>
          <option value={active.data?.dataset ?? ''}>{active.data?.dataset ?? 'checking'}</option>
          {switchableDatasets.filter(item => item !== active.data?.dataset).map(item => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
        </select>
      </label>
    </div>
    <div className="layer-tabs modeling-tabs">
      <button className={view === 'connectors' ? 'active' : ''} onClick={() => setView('connectors')}>1. Add data</button>
      <button className={view === 'mapping' ? 'active' : ''} onClick={() => setView('mapping')}>2. Describe data</button>
      <button className={view === 'ontology' ? 'active' : ''} onClick={() => setView('ontology')}>3. Review ontology</button>
      <button className={view === 'guide' ? 'active' : ''} onClick={() => setView('guide')}>Labeler guide</button>
    </div>
    {view === 'connectors' && <CsvConnectors role={role} onMap={source => { setDataset(source); setView('mapping'); void client.invalidateQueries({ queryKey: ['object-mappings'] }); }} />}
    {view === 'mapping' && <div className="model-panel labeler-workflow">
      <div className="model-toolbar">
        <div><h2>Describe your file</h2><p>Tell the system what one row represents, then give every useful column a meaning.</p></div>
        <label className="dataset-picker">File or dataset<select value={dataset} onChange={event => { setDataset(event.target.value); setValidation([]); setJobId(undefined); }}>{datasetNames.map(name => <option key={name} value={name}>{name.startsWith('csv:') ? `CSV · ${mappings.data?.find(item => item.dataset === name)?.source ?? name.slice(4, 12)}` : name.replaceAll('_', ' ')}</option>)}</select></label>
      </div>
      <div className="plain-tip">{nativeFolderDataset ? <><strong>{policeUkDataset ? 'Police.uk public-safety source selected.' : 'Prepared dataset detected.'}</strong> {policeUkDataset ? 'The loader downloads or reuses cached official Police.uk and ONS data, then builds the RDF graph, aggregates, provenance, and semantic index. CSV mapping is not required.' : 'Its validated graph, documents, ontology, and evaluation questions will be ingested together. CSV mapping is not required for this prepared dataset.'}</> : <><strong>Start with a list of things.</strong> For example, upload customers and products before uploading a file that connects customers to orders. Use the same IDs in every file.</>}</div>
      <div className="mapping-summary">
        <span><b>{drafts.length}</b> file objects</span>
        <span><b>{drafts.filter(item => readiness(item).length === 0).length}</b> ready</span>
        <span><b>{drafts.reduce((count, item) => count + readiness(item).length, 0)}</b> choices left</span>
        <div className="mapping-actions"><button className="button secondary" disabled={!editable} onClick={() => void save()}>Check and save</button></div>
      </div>
      {!editable && <div className="warning workflow-notice">Your account is read-only. Ask for a labeler account to describe data.</div>}
      {actionMessage && <div className="success workflow-notice"><strong>{actionMessage}</strong></div>}
      {actionError && <div className="error workflow-notice"><strong>Action failed</strong><p>{actionError}</p><p>Check your choices and try again. If the message names an unavailable service, ask an administrator to check Operations.</p></div>}
      {validation.length > 0 && <div className="error workflow-notice"><strong>Please fix these choices</strong>{validation.map(error => <p key={error}>{error}</p>)}</div>}
      <div className="mapping-list friendly-mappings">{drafts.map(mapping => {
        const issues = readiness(mapping);
        return <article key={`${mapping.dataset}-${mapping.source}`} className={expanded === mapping.source ? 'expanded' : ''}>
          <button className="mapping-head" onClick={() => setExpanded(expanded === mapping.source ? undefined : mapping.source)}>
            <span className={`readiness-dot ${issues.length ? 'needs-work' : 'ready'}`} />
            <div><small>Data source</small><strong>{mapping.source}</strong></div>
            <div><small>One row is</small><strong>{mapping.target_class || 'Not named yet'}</strong></div>
            <b className={issues.length ? 'needs-work' : 'ready'}>{issues.length ? `${issues.length} choice${issues.length > 1 ? 's' : ''} left` : 'Ready'}</b>
            <i>{expanded === mapping.source ? '−' : '+'}</i>
          </button>
          {expanded === mapping.source && <div className="friendly-editor">
            <div className="row-kind">
              <div><label>What does one row represent?</label><input value={mapping.target_class} disabled={!editable} placeholder={mapping.mapping_kind === 'entity' ? 'Example: Customer' : 'Example: works for'} onChange={event => updateMapping(mapping.source, { target_class: event.target.value })} /></div>
              <fieldset><legend>What kind of file is this?</legend>
                <label><input type="radio" checked={mapping.mapping_kind === 'entity'} disabled={!editable} onChange={() => updateMapping(mapping.source, { mapping_kind: 'entity' })} /><span><strong>A list of things</strong><small>People, products, orders, places…</small></span></label>
                <label><input type="radio" checked={mapping.mapping_kind === 'relationship'} disabled={!editable} onChange={() => updateMapping(mapping.source, { mapping_kind: 'relationship' })} /><span><strong>Connections between things</strong><small>Employee works for department</small></span></label>
              </fieldset>
            </div>
            {issues.length > 0 && <div className="mapping-checklist"><strong>To make this ready:</strong>{issues.map(issue => <span key={issue}>○ {issue}</span>)}</div>}
            <div className="column-map friendly-columns">
              <div className="column-map-head"><span>Column in your file</span><span>What does it mean?</span><span>Name in the model</span></div>
              {mapping.columns.map(column => {
                const option = roleOptions.find(item => item.value === column.role)!;
                return <div key={column.source}><code>{column.source}</code><label><select value={column.role} disabled={!editable} onChange={event => updateColumn(mapping.source, column.source, 'role', event.target.value)}>{roleOptions.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select><small>{option.help}</small></label><input value={column.target} disabled={!editable || column.role === 'ignore'} onChange={event => updateColumn(mapping.source, column.source, 'target', event.target.value)} /></div>;
              })}
            </div>
          </div>}
        </article>;
      })}</div>
      {drafts.length === 0 && <div className="connector-empty"><strong>No description is available</strong><span>Go to “Add data” and upload a CSV file first.</span></div>}
      <div className="ingestion-config">
        <div><span className="eyebrow">Ingestion configuration</span><h3>Choose how this dataset is indexed</h3><p>Indexes are isolated by dataset and embedding model, so experiments cannot overwrite each other.</p></div>
        <label>Operation<select value={scope} onChange={event => setScope(event.target.value as typeof scope)}>{ingestionOptions.data?.scopes.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <label>Embedding model<select value={embeddingModel} onChange={event => { const id = event.target.value; setEmbeddingModel(id); const selected = ingestionOptions.data?.models.find(item => item.id === id); if (selected) setBatchSize(selected.recommended_batch_size); }}>{ingestionOptions.data?.models.map(item => <option key={item.id} value={item.id}>{item.label} · {item.dimension}d</option>)}</select></label>
        <label>Processor<select value={embeddingDevice} onChange={event => setEmbeddingDevice(event.target.value as 'cpu' | 'cuda')}>{ingestionOptions.data?.devices.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <label>Embedding batch<select value={batchSize} onChange={event => setBatchSize(Number(event.target.value))}>{ingestionOptions.data?.batch_sizes.map(item => <option key={item} value={item}>{item} records</option>)}</select></label>
        <label className="cache-choice"><input type="checkbox" checked={savePrecomputed} onChange={event => setSavePrecomputed(event.target.checked)} /><span><b>Save reusable vectors</b><small>Include validated precomputed vectors in future dataset exports.</small></span></label>
        {scope !== 'full_rebuild' && scope !== 'vectors_only' && <div className="publish-mode"><label><input type="radio" checked={mode === 'append'} onChange={() => setMode('append')} /> Add to the graph</label><label><input type="radio" checked={mode === 'reset'} onChange={() => setMode('reset')} /> Replace the graph</label></div>}
      </div>
      <div className="publish-panel">
        <div><h3>Publish selected configuration</h3><p>{scope === 'incremental' ? 'Only new or changed searchable text will be embedded.' : scope === 'full_rebuild' ? 'The graph and selected model index will be rebuilt.' : 'Only the selected storage layer will be updated.'}</p></div>
        <div className="index-summary"><small>Target index</small><b>{ingestionName(dataset)} / {embeddingModel}</b><span>{embeddingDevice.toUpperCase()} · batch {batchSize}</span></div>
        <button className="button" disabled={role !== 'admin' || (!nativeFolderDataset && (validation.length > 0 || drafts.some(item => readiness(item).length > 0)))} onClick={() => void ingest()}>{nativeFolderDataset ? `Run ${policeUkDataset ? 'Police.uk' : 'dataset'} ingestion` : 'Build knowledge graph'}</button>
      </div>
      {job.data && <div className={`job-progress ${job.data.status}`}><div><strong>{job.data.status === 'complete' ? 'Knowledge graph built' : job.data.status === 'failed' ? 'Build failed' : `Working: ${job.data.phase.replaceAll('_', ' ')}`}</strong><span>{job.data.progress}%</span></div><div className="progress-track"><i style={{ width: `${job.data.progress}%` }} /></div>{job.data.report && <small>{String(job.data.report.entities_processed ?? 0)} items · {String(job.data.report.relationships_processed ?? 0)} connections · {String(job.data.report.vectors_generated ?? 0)} newly embedded · {String(job.data.report.vectors_reused ?? 0)} reused</small>}{job.data.status === 'failed' && <div className="job-error-detail"><strong>Why it failed</strong>{job.data.error ? <p>{job.data.error}</p> : job.data.report?.errors?.length ? job.data.report.errors.map((error, index) => <p key={`${index}-${error}`}>{error}</p>) : <p>The backend did not provide a reason. Check the Operations page and backend logs.</p>}</div>}{job.data.report?.warnings?.map((warning, index) => <p className="job-warning" key={`${index}-${warning}`}>Warning: {warning}</p>)}</div>}
    </div>}
    {view === 'ontology' && <OntologyViewer ontology={ontology.data} />}
    {view === 'guide' && <LabelerGuide />}
  </section>;
}

function CsvConnectors({ role, onMap }: { role: User['role']; onMap: (dataset: string) => void }) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<string>();
  const connectors = useQuery({ queryKey: ['csv-connectors'], queryFn: api.csvConnectors });
  const detail = useQuery({ queryKey: ['csv-connector', selected], queryFn: () => api.csvConnector(selected!), enabled: Boolean(selected) });
  const upload = useMutation({ mutationFn: api.uploadCsv, onSuccess: result => { setSelected(result.id); cache.setQueryData(['csv-connector', result.id], result); void cache.invalidateQueries({ queryKey: ['csv-connectors'] }); void cache.invalidateQueries({ queryKey: ['object-mappings'] }); } });
  const current = detail.data;
  return <div className="connector-layout"><div className="connector-catalog"><div className="connector-title"><div><span className="eyebrow">Step 1</span><h2>Add a spreadsheet saved as CSV</h2><p>We inspect the headings and show a preview. Nothing is published yet.</p></div><label className={`csv-upload ${role === 'viewer' ? 'disabled' : ''}`}>+ Choose CSV file<input type="file" accept=".csv,text/csv" disabled={role === 'viewer' || upload.isPending} onChange={event => { const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = ''; }} /></label></div>
    {upload.isPending && <div className="connector-message">Reading headings and sample rows…</div>}{upload.error && <div className="error connector-message">{upload.error.message}</div>}
    <div className="connector-list">{connectors.data?.map(item => <button key={item.id} className={selected === item.id ? 'active' : ''} onClick={() => setSelected(item.id)}><span className="csv-icon">CSV</span><div><strong>{item.name}</strong><small>{item.row_count.toLocaleString()} rows · {item.column_count} columns</small></div><b>{item.status}</b></button>)}{connectors.data?.length === 0 && <div className="connector-empty"><strong>No files added yet</strong><span>Choose a CSV file to begin.</span></div>}</div></div>
    <div className="connector-detail">{current ? <><div className="connector-detail-head"><div><span className="eyebrow">File checked</span><h2>{current.filename}</h2><p>We found {current.row_count.toLocaleString()} rows and {current.column_count} columns.</p></div><button onClick={() => onMap(current.dataset)}>Describe this data →</button></div><div className="schema-chips">{current.columns.map(column => <span key={column}>{column}</span>)}</div><h3>Does this preview look correct?</h3><div className="csv-preview"><table><thead><tr>{current.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{current.preview?.map((row, index) => <tr key={index}>{current.columns.map(column => <td key={column}>{row[column]}</td>)}</tr>)}</tbody></table></div></> : <div className="connector-placeholder"><span>CSV</span><h2>Select a file</h2><p>You will see its headings and first few rows here before describing it.</p></div>}</div>
  </div>;
}

function OntologyViewer({ ontology }: { ontology?: Awaited<ReturnType<typeof api.ontology>> }) {
  const [selected, setSelected] = useState<string>(); const [search, setSearch] = useState('');
  const classes = ontology?.classes.filter(item => (item.label || localName(item.class)).toLowerCase().includes(search.toLowerCase())) ?? [];
  const current = ontology?.classes.find(item => item.class === selected) ?? classes[0];
  const properties = ontology?.properties.filter(item => !current || item.domain === current.class || item.range === current.class) ?? [];
  function showInstances() { if (current) { sessionStorage.setItem('ontologyClassSearch', current.label || localName(current.class)); window.location.href = '/graph'; } }
  return <div className="ontology-viewer"><div className="class-browser"><div className="browser-title"><h2>Types of things</h2><span>{ontology?.classes.length ?? 0} types</span></div><input className="class-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Find a type…" /><div className="class-tree">{classes.map(item => <button className={current?.class === item.class ? 'active' : ''} key={item.class} onClick={() => setSelected(item.class)}><i>◆</i><span><strong>{item.label || localName(item.class)}</strong><small>{item.parent ? `belongs under ${localName(item.parent)}` : 'top-level type'}</small></span><b>{item.instances ?? 0}</b></button>)}</div></div>
    <div className="class-detail">{current ? <><span className="eyebrow">Selected type</span><div className="class-title"><div>◆</div><span><h2>{current.label || localName(current.class)}</h2><code>{current.class}</code></span></div><button className="button secondary" onClick={showInstances}>Show items and connections →</button><div className="class-metrics"><span><small>Items</small><b>{current.instances ?? 0}</b></span><span><small>Belongs under</small><b>{current.parent ? localName(current.parent) : 'None'}</b></span><span><small>Connected details</small><b>{properties.length}</b></span></div><h3>Details and connections</h3><div className="property-table"><div><span>Name</span><span>Kind</span><span>Used by</span><span>Points to</span></div>{properties.map(property => <div key={property.property}><strong>{property.label || localName(property.property)}</strong><span>{localName(property.kind)}</span><code>{localName(property.domain)}</code><code>{localName(property.range)}</code></div>)}</div></> : <div className="connector-placeholder"><h2>No ontology types yet</h2><p>Add and publish a file to create the first type.</p></div>}</div></div>;
}

function LabelerGuide() {
  return <div className="labeler-guide">
    <div className="guide-hero"><span className="eyebrow">Data labeler guide</span><h2>Turn rows into understandable knowledge</h2><p>Your job is to explain what the data means. The system handles the technical graph format.</p></div>
    <div className="guide-steps">
      <article><b>1</b><h3>Prepare the file</h3><p>Use one header row, one item per row, and a stable unique ID. Save it as UTF-8 CSV.</p></article>
      <article><b>2</b><h3>Add and preview</h3><p>Check that headings, characters, and sample rows look correct before continuing.</p></article>
      <article><b>3</b><h3>Describe one row</h3><p>Choose “list of things” for customers or products, or “connections” for links between IDs.</p></article>
      <article><b>4</b><h3>Describe columns</h3><p>Select Unique ID, Display name, Detail, From item, To item, or Do not import.</p></article>
      <article><b>5</b><h3>Check and save</h3><p>Resolve every “choice left” message. An administrator reviews and publishes the graph.</p></article>
    </div>
    <div className="guide-grid">
      <article><h3>Example: a list of things</h3><table><thead><tr><th>CSV column</th><th>Meaning</th></tr></thead><tbody><tr><td>customer_id</td><td>Unique ID</td></tr><tr><td>company_name</td><td>Display name</td></tr><tr><td>country</td><td>Detail</td></tr></tbody></table></article>
      <article><h3>Example: connections</h3><table><thead><tr><th>CSV column</th><th>Meaning</th></tr></thead><tbody><tr><td>employee_id</td><td>From item</td></tr><tr><td>department_id</td><td>To item</td></tr><tr><td>relation</td><td>Connection name</td></tr></tbody></table></article>
      <article><h3>Quality checklist</h3><ul><li>IDs are unique, stable, and reused across files.</li><li>Names are clear and consistently capitalized.</li><li>Empty rows and duplicate records are removed.</li><li>You did not guess missing meanings.</li><li>Sensitive columns are marked “Do not import”.</li></ul></article>
      <article><h3>When to ask for help</h3><ul><li>A column has several possible meanings.</li><li>Two files use different IDs for the same item.</li><li>A file contains confidential or personal data.</li><li>You are unsure whether to replace or add to the graph.</li></ul></article>
    </div>
    <div className="plain-tip"><strong>Remember:</strong> build item lists first, then connection files. Keep the same item ID everywhere so the system can join the knowledge correctly.</div>
  </div>;
}
