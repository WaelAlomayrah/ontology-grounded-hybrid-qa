import { useEffect, useState } from 'react';
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import type { User } from './types/api';
import { LanguageToggle } from './i18n';
import ChatPage from './pages/ChatPage';
import EvaluationPage from './pages/EvaluationPage';
import GraphPage from './pages/GraphPage';
import LoginPage from './pages/LoginPage';
import ModelingPage from './pages/ModelingPage';
import StatusPage from './pages/StatusPage';

const navItems = [
  { path: '/chat', label: 'Ask', icon: '✦' },
  { path: '/modeling', label: 'Modeling', icon: '⌘' },
  { path: '/graph', label: 'Graph', icon: '◫' },
  { path: '/evaluation', label: 'Evaluation', icon: '⬡' },
  { path: '/operations', label: 'Operations', icon: '✓' },
];

function App() {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem('ontology-user');
    return raw ? (JSON.parse(raw) as User) : null;
  });
  const location = useLocation();
  const [onboardingOpen, setOnboardingOpen] = useState(() => !localStorage.getItem('ontology-onboarding-seen'));

  useEffect(() => {
    if (user) {
      localStorage.setItem('ontology-user', JSON.stringify(user));
    }
  }, [user]);

  if (!user) {
    return (
      <>
        <div className="login-language">
          <LanguageToggle />
        </div>
        <LoginPage onLogin={setUser} />
      </>
    );
  }

  const closeOnboarding = () => {
    localStorage.setItem('ontology-onboarding-seen', 'true');
    setOnboardingOpen(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('ontology-token');
    localStorage.removeItem('ontology-user');
    setUser(null);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark">◫</div>
        <div className="brand-copy">
          <strong>Ontology QA Workbench</strong>
          <span>Research pilot</span>
        </div>
        <nav>
          {navItems.map((item) => (
            <NavLink key={item.path} to={item.path}>
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="header-actions">
          <LanguageToggle />
          <button className="user-pill" onClick={handleLogout} title="Sign out">
            <b>{user.username.slice(0, 1).toUpperCase()}</b>
            <span>
              {user.username}
              <small>{user.role}</small>
            </span>
          </button>
        </div>
      </header>

      <main>
        <Routes location={location}>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/modeling" element={<ModelingPage role={user.role} />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="/operations" element={<StatusPage role={user.role} />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </main>

      {onboardingOpen && (
        <div className="onboarding-backdrop" role="dialog" aria-modal="true">
          <section className="onboarding-card">
            <button className="onboarding-close" onClick={closeOnboarding} aria-label="Close">
              ×
            </button>
            <p className="eyebrow">Welcome</p>
            <h2>Build trusted answers from connected knowledge</h2>
            <p className="muted">
              The workbench combines ontology guidance, graph evidence, and semantic retrieval in one explainable
              workflow.
            </p>
            <div className="onboarding-grid">
              <article>
                <b>1</b>
                <h3>Model</h3>
                <p>Create classes, properties, mappings, and validation rules without writing RDF.</p>
              </article>
              <article>
                <b>2</b>
                <h3>Ingest</h3>
                <p>Load curated datasets into Fuseki and Milvus with repeatable ingestion jobs.</p>
              </article>
              <article>
                <b>3</b>
                <h3>Ask & inspect</h3>
                <p>Ask questions, compare retrieval strategies, and inspect the supporting graph path.</p>
              </article>
            </div>
            <button className="primary-button" onClick={closeOnboarding}>
              Start exploring <span>→</span>
            </button>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
