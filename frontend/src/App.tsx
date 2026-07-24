import { useState } from 'react';
import { NavLink, Route, Routes } from 'react-router-dom';
import ChatPage from './pages/ChatPage';
import EvaluationPage from './pages/EvaluationPage';
import GraphPage from './pages/GraphPage';
import LoginPage from './pages/LoginPage';
import ModelingPage from './pages/ModelingPage';
import StatusPage from './pages/StatusPage';
import type { User } from './types/api';

const icon = (name: string) => <span className="nav-icon" aria-hidden="true">{name}</span>;

export default function App() {
  const [user, setUser] = useState<User | null>(() => { try { return JSON.parse(localStorage.getItem('ontology-user') || 'null'); } catch { return null; } });
  const [showGuide, setShowGuide] = useState(() => !localStorage.getItem('ontology-onboarded'));
  if (!user) return <LoginPage onLogin={setUser} />;
  function logout() { localStorage.removeItem('ontology-token'); localStorage.removeItem('ontology-user'); setUser(null); }
  return <div className="app-shell">
    <header className="topbar"><div className="brand-mark">O</div><div className="brand-copy"><strong>Ontology Studio</strong><span>Explainable knowledge intelligence</span></div><nav><NavLink to="/">{icon('✦')} Chat</NavLink><NavLink to="/graph">{icon('⌘')} Graph</NavLink><NavLink to="/status">{icon('◫')} Operations</NavLink><NavLink to="/modeling">{icon('⬡')} Modeling</NavLink><NavLink to="/evaluation">{icon('✓')} Evaluation</NavLink></nav><button className="user-pill" onClick={logout}><span>{user.username.slice(0, 1).toUpperCase()}</span>{user.username}<small>{user.role}</small></button></header>
    {showGuide && <div className="onboarding"><div><span className="eyebrow">First-run guide</span><h2>Build knowledge without technical modeling</h2><ol><li>Add a CSV file</li><li>Check the sample rows</li><li>Say what one row represents</li><li>Describe each useful column</li><li>Check and save your work</li><li>Ask an administrator to publish</li></ol><NavLink className="button" to="/modeling" onClick={() => { localStorage.setItem('ontology-onboarded', 'true'); setShowGuide(false); }}>Open guided modeling →</NavLink><button className="guide-close" aria-label="Close guide" onClick={() => { localStorage.setItem('ontology-onboarded', 'true'); setShowGuide(false); }}>×</button></div></div>}
    <main><Routes><Route path="/" element={<ChatPage />} /><Route path="/graph" element={<GraphPage />} /><Route path="/status" element={<StatusPage />} /><Route path="/modeling" element={<ModelingPage role={user.role} />} /><Route path="/evaluation" element={<EvaluationPage />} /></Routes></main>
  </div>;
}
