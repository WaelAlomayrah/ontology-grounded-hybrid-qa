import { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape, { Core, EdgeSingular } from 'cytoscape';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Graph, Node } from '../types/api';

const palette = ['#2dd4bf', '#60a5fa', '#c084fc', '#fb7185', '#fbbf24', '#34d399', '#f97316', '#a3e635', '#38bdf8', '#e879f9'];
const localName = (uri = '') => decodeURIComponent(uri.split(/[#/]/).pop() || 'Thing').replaceAll('_', ' ');
const colorFor = (type: string) => palette[[...type].reduce((sum, char) => sum + char.charCodeAt(0), 0) % palette.length];

export default function GraphPage() {
  const host = useRef<HTMLDivElement>(null);
  const cy = useRef<Core>();
  const history = useRef<string[][]>([]);
  const directionRef = useRef<'outgoing' | 'incoming' | 'both'>('outgoing');
  const [query, setQuery] = useState('Project Atlas');
  const [selected, setSelected] = useState<Node>();
  const [depth, setDepth] = useState(1);
  const [layer, setLayer] = useState<'instances' | 'ontology'>('instances');
  const [counts, setCounts] = useState({ nodes: 0, edges: 0 });
  const [direction, setDirection] = useState<'outgoing' | 'incoming' | 'both'>('outgoing');
  const [relations, setRelations] = useState<string[]>([]);
  const [relationFilter, setRelationFilter] = useState('all');
  const ontology = useQuery({ queryKey: ['ontology'], queryFn: api.ontology });
  const stats = useQuery({ queryKey: ['graph-stats'], queryFn: api.stats });
  const legend = useMemo(() => {
    const types = new Set(cy.current?.nodes().map(node => String(node.data('type'))) ?? []);
    return [...types].slice(0, 10);
  }, [counts]);

  useEffect(() => {
    if (!host.current) return;
    cy.current = cytoscape({
      container: host.current,
      wheelSensitivity: 0.2,
      style: [
        { selector: 'node', style: { 'label': 'data(label)', 'background-color': 'data(color)', 'border-color': '#dffdfa', 'border-width': '1.5px', 'color': '#eaf7f7', 'font-size': '11px', 'font-weight': '600', 'text-wrap': 'wrap', 'text-max-width': '120px', 'text-valign': 'bottom', 'text-margin-y': '11px', 'text-background-color': '#071317', 'text-background-opacity': .88, 'text-background-padding': '4px', 'text-background-shape': 'roundrectangle', 'width': '42px', 'height': '42px', 'overlay-opacity': 0 } },
        { selector: 'node:selected', style: { 'border-width': '4px', 'border-color': '#ffffff', 'width': '50px', 'height': '50px', 'z-index': 20 } },
        { selector: 'edge', style: { 'label': '', 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#637f89', 'line-color': '#42606a', 'color': '#c1d1d4', 'font-size': '9px', 'text-background-color': '#071317', 'text-background-opacity': .95, 'text-background-padding': '4px', 'width': '1.5px', 'arrow-scale': .75 } },
        { selector: 'edge:selected', style: { 'label': 'data(label)', 'line-color': '#2dd4bf', 'target-arrow-color': '#2dd4bf', 'width': '3px', 'z-index': 15 } },
        { selector: '.outgoing-edge', style: { 'label': 'data(label)', 'line-color': '#fbbf24', 'target-arrow-color': '#fbbf24', 'color': '#ffe6a3', 'width': '3px', 'z-index': 18 } },
        { selector: '.outgoing-target', style: { 'border-color': '#fbbf24', 'border-width': '4px', 'z-index': 17 } },
        { selector: '.faded', style: { 'opacity': .16 } },
        { selector: '.ontology-edge', style: { 'line-style': 'dashed', 'line-color': '#c084fc', 'target-arrow-color': '#c084fc' } },
      ] as any,
    });
    cy.current.on('tap', 'node', event => {
      const node = event.target;
      setSelected(node.data('raw') as Node);
      focusOutgoing(node.id());
    });
    cy.current.on('tap', event => {
      if (event.target === cy.current) clearFocus();
    });
    const cached = sessionStorage.getItem('supportingGraph');
    if (cached) { try { renderGraph(JSON.parse(cached) as Graph, true); } catch { /* ignore stale data */ } }
    const requested = sessionStorage.getItem('graphSearch') || sessionStorage.getItem('ontologyClassSearch');
    if (requested) { sessionStorage.removeItem('graphSearch'); sessionStorage.removeItem('ontologyClassSearch'); setQuery(requested); void searchFor(requested); }
    return () => cy.current?.destroy();
  }, []);

  useEffect(() => { if (layer === 'ontology' && ontology.data) renderOntology(); }, [layer, ontology.data]);

  function addGraph(graph: Graph, replace = false) {
    if (!cy.current) return;
    if (replace) cy.current.elements().remove();
    const existing = new Set(cy.current.elements().map(element => element.id()));
    const elements = [
      ...graph.nodes.filter(node => !existing.has(node.id)).map(node => ({ data: { ...node, raw: node, type: localName(node.type), color: colorFor(node.type) } })),
      ...graph.edges.filter(edge => !existing.has(edge.id) && !existing.has(`${edge.source}-${edge.predicate}-${edge.target}`)).map(edge => ({ data: { ...edge, id: edge.id || `${edge.source}-${edge.predicate}-${edge.target}` } })),
    ];
    cy.current.add(elements); history.current.push(elements.map(element => String(element.data.id)));
    setRelations([...new Set(cy.current.edges().map(edge => String(edge.data('label'))))].sort());
    setCounts({ nodes: cy.current.nodes().length, edges: cy.current.edges().length });
    runLayout('cose');
  }
  function renderGraph(graph: Graph, replace = false) { setLayer('instances'); addGraph(graph, replace); }
  async function searchFor(text: string) { const hits = await api.search(text); if (hits[0]) await expand(hits[0].entity, true); }
  async function search() { await searchFor(query); }
  async function expand(uri: string, replace = false) { const graph = await api.neighbors(uri, depth); addGraph(graph, replace); setSelected(graph.nodes.find(node => node.id === uri)); }
  function renderOntology() {
    if (!cy.current || !ontology.data) return;
    cy.current.elements().remove();
    const ids = new Set(ontology.data.classes.map(item => item.class));
    cy.current.add([
      ...ontology.data.classes.map(item => ({ data: { id: item.class, label: item.label || localName(item.class), type: 'Ontology class', color: colorFor(item.class), raw: { id: item.class, label: item.label || localName(item.class), type: 'Ontology class', properties: { instances: Number(item.instances || 0) } } } })),
      ...ontology.data.classes.filter(item => item.parent && ids.has(item.parent)).map(item => ({ data: { id: `${item.class}-subclass-${item.parent}`, source: item.class, target: item.parent, label: 'subclass of' }, classes: 'ontology-edge' })),
    ]);
    setCounts({ nodes: cy.current.nodes().length, edges: cy.current.edges().length });
    cy.current.layout({ name: 'breadthfirst', directed: true, spacingFactor: 1.85, nodeDimensionsIncludeLabels: true, avoidOverlap: true, padding: 70 }).run();
  }
  function runLayout(name: 'cose' | 'circle' | 'grid') {
    if (!cy.current || cy.current.nodes().length === 0) return;
    if (name === 'cose') {
      cy.current.layout({ name: 'cose', animate: true, animationDuration: 700, nodeRepulsion: () => 22000, nodeOverlap: 50, idealEdgeLength: () => 185, edgeElasticity: () => 80, nestingFactor: 1.3, gravity: .18, numIter: 1500, initialTemp: 260, coolingFactor: .96, minTemp: 1, nodeDimensionsIncludeLabels: true, padding: 80 }).run();
      return;
    }
    cy.current.layout({ name, animate: true, animationDuration: 500, spacingFactor: name === 'circle' ? 1.55 : 1.35, nodeDimensionsIncludeLabels: true, avoidOverlap: true, avoidOverlapPadding: 35, padding: 80 }).run();
  }
  function reset() { cy.current?.elements().remove(); setSelected(undefined); setCounts({ nodes: 0, edges: 0 }); }
  function setGraphDirection(value: 'outgoing' | 'incoming' | 'both') { directionRef.current = value; setDirection(value); if (selected) focusOutgoing(selected.id); }
  function filterRelations(value: string) { setRelationFilter(value); const edges = cy.current?.edges(); edges?.style('display', 'element'); if (value !== 'all') edges?.filter((edge: EdgeSingular) => edge.data('label') !== value).style('display', 'none'); }
  function toggleClass(type: string) { const nodes = cy.current?.nodes().filter(node => String(node.data('type')) === type); if (!nodes) return; const hidden = nodes.first().style('display') === 'none'; nodes.style('display', hidden ? 'element' : 'none'); }
  function togglePin() { const node = cy.current?.nodes(':selected'); if (!node?.length) return; node.first().locked() ? node.unlock() : node.lock(); }
  function undoExpansion() { const ids = history.current.pop(); if (!ids || !cy.current) return; ids.forEach(id => cy.current?.getElementById(id).remove()); setCounts({ nodes: cy.current.nodes().length, edges: cy.current.edges().length }); }
  function download(name: string, href: string) { const anchor = document.createElement('a'); anchor.href = href; anchor.download = name; anchor.click(); }
  function exportJson() { if (cy.current) download('knowledge-graph.json', `data:application/json,${encodeURIComponent(JSON.stringify(cy.current.elements().jsons(), null, 2))}`); }
  function exportPng() { if (cy.current) download('knowledge-graph.png', cy.current.png({ full: true, scale: 2, bg: '#071317' })); }
  function clearFocus() {
    cy.current?.elements().removeClass('faded outgoing-edge outgoing-target');
  }
  function focusOutgoing(nodeId: string) {
    if (!cy.current) return;
    clearFocus();
    const source = cy.current.getElementById(nodeId);
    const edges = directionRef.current === 'outgoing' ? source.outgoers('edge') : directionRef.current === 'incoming' ? source.incomers('edge') : source.connectedEdges();
    const targets = edges.connectedNodes().difference(source);
    cy.current.elements().addClass('faded');
    source.removeClass('faded');
    edges.removeClass('faded').addClass('outgoing-edge');
    targets.removeClass('faded').addClass('outgoing-target');
  }

  return <section className="graph-page">
    <div className="page-heading"><div><span className="eyebrow">Visual investigation</span><h1>Knowledge graph</h1><p>Follow relationships, distinguish entity classes, and inspect the ontology that gives the data meaning.</p></div><div className="stat-pills"><span><b>{stats.data?.triple_count ?? '—'}</b> triples</span><span><b>{stats.data?.entity_count ?? '—'}</b> resources</span></div></div>
    <div className="layer-tabs"><button className={layer === 'instances' ? 'active' : ''} onClick={() => setLayer('instances')}>Instance graph</button><button className={layer === 'ontology' ? 'active' : ''} onClick={() => setLayer('ontology')}>Ontology layer <span>{ontology.data?.classes.length ?? 0}</span></button></div>
    <div className="graph-workspace">
      <div className="graph-main">
        <div className="graph-toolbar">
          <div className="search-box"><span>⌕</span><input value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void search(); }} placeholder="Find an entity…" /><button onClick={() => void search()}>Explore</button></div>
          <label>Depth <select value={depth} onChange={event => setDepth(Number(event.target.value))}><option value={1}>1 hop</option><option value={2}>2 hops</option><option value={3}>3 hops</option></select></label><label>Direction <select value={direction} onChange={event => setGraphDirection(event.target.value as typeof direction)}><option value="outgoing">Outgoing</option><option value="incoming">Incoming</option><option value="both">Both</option></select></label><label>Relation <select value={relationFilter} onChange={event => filterRelations(event.target.value)}><option value="all">All</option>{relations.map(value => <option key={value}>{value}</option>)}</select></label>
          <div className="layout-controls"><button onClick={() => runLayout('cose')} title="Spread relationship layout">Spread</button><button onClick={() => runLayout('circle')} title="Arrange in a circle">Circle</button><button onClick={() => runLayout('grid')} title="Arrange in a grid">Grid</button></div>
          <button className="icon-button" onClick={togglePin} title="Pin or unpin selected node">⌖</button><button className="icon-button" onClick={undoExpansion} title="Undo last expansion">↶</button><button className="icon-button" onClick={() => cy.current?.fit(undefined, 55)} title="Fit graph">⊙</button><button className="icon-button" onClick={reset} title="Reset graph">↺</button>
        </div>
        <div ref={host} className="graph" />
        <div className="graph-footer"><span>{counts.nodes} nodes · {counts.edges} relationships</span><div className="graph-exports"><button onClick={exportJson}>JSON</button><button onClick={exportPng}>PNG</button></div><div className="legend">{legend.map(type => <button onClick={() => toggleClass(type)} key={type}><i style={{ background: colorFor(type) }} />{localName(type)}</button>)}</div></div>
      </div>
      <aside className="inspector">
        <span className="eyebrow">Inspector</span>
        {selected ? <><div className="selected-icon" style={{ background: colorFor(selected.type) }}>{selected.label.slice(0, 1)}</div><h2>{selected.label}</h2><span className="class-tag">{localName(selected.type)}</span><dl><dt>Identifier</dt><dd title={selected.id}>{localName(selected.id)}</dd>{Object.entries(selected.properties).slice(0, 8).map(([key, value]) => <div key={key}><dt>{localName(key)}</dt><dd>{String(value)}</dd></div>)}</dl>{layer === 'instances' && <button className="wide-button" onClick={() => void expand(selected.id)}>Expand neighbors →</button>}</> : <div className="empty-inspector"><div>⌘</div><h2>Select a node</h2><p>Click any colored node to inspect its class, identifier, and properties.</p></div>}
        {layer === 'ontology' && <div className="ontology-summary"><h3>Ontology vocabulary</h3><p><b>{ontology.data?.classes.length ?? 0}</b> classes</p><p><b>{ontology.data?.properties.length ?? 0}</b> declared properties</p></div>}
      </aside>
    </div>
  </section>;
}
