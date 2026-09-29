import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";

function useSubmit(action: () => Promise<void>) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };
  return { error, busy, onSubmit };
}

export function LoginPage() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const { error, busy, onSubmit } = useSubmit(async () => {
    await api.post("/api/auth/login", { login, password });
    await refresh();
    navigate("/");
  });
  return (
    <form className="card form narrow" onSubmit={onSubmit}>
      <h1>Connexion</h1>
      <label>
        Pseudo ou e-mail
        <input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" required />
      </label>
      <label>
        Mot de passe
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
      </label>
      {error && <p className="error">{error}</p>}
      <button disabled={busy}>Se connecter</button>
      <p className="muted">
        Pas encore de compte ? <Link to="/register">Inscription</Link>
      </p>
    </form>
  );
}

export function RegisterPage() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "", display_name: "" });
  const [accept, setAccept] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const { error, busy, onSubmit } = useSubmit(async () => {
    await api.post("/api/auth/register", form);
    await refresh();
    navigate("/settings");
  });
  return (
    <form className="card form narrow" onSubmit={onSubmit}>
      <h1>Créer un compte</h1>
      <label>
        Identifiant (lettres, chiffres, _)
        <input value={form.username} onChange={set("username")} autoComplete="username" required />
      </label>
      <label>
        Pseudo en jeu
        <input value={form.display_name} onChange={set("display_name")} />
      </label>
      <label>
        E-mail
        <input type="email" value={form.email} onChange={set("email")} autoComplete="email" required />
      </label>
      <label>
        Mot de passe (10 caractères min., une lettre et un chiffre)
        <input type="password" value={form.password} onChange={set("password")} autoComplete="new-password" required />
      </label>
      <label className="check">
        <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
        J'accepte les règles de la communauté et la politique de confidentialité.
      </label>
      {error && <p className="error">{error}</p>}
      <button disabled={busy || !accept}>S'inscrire</button>
    </form>
  );
}
