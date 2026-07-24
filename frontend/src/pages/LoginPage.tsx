import { FormEvent, useState } from 'react';
import { api } from '../api/client';
import type { User } from '../types/api';

export default function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const user = await api.login(username, password);
      localStorage.setItem('ontology-token', user.token);
      localStorage.setItem('ontology-user', JSON.stringify(user));
      onLogin(user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  }
  return <main className="login-page"><form className="login-card" onSubmit={submit}><div className="brand-mark">O</div><span className="eyebrow">Ontology Studio</span><h1>Welcome back</h1><p>Sign in to explore data, describe knowledge, and ask evidence-grounded questions.</p><label>Username<input value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" /></label><label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" /></label>{error && <div className="error">{error}</div>}<button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button><small>Use your assigned viewer, labeler, analyst, or administrator account.</small></form></main>;
}
