import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Guild, type Profile } from "../api";
import { useAuth } from "../auth";

export function GuildsPage() {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [guilds, setGuilds] = useState<Guild[] | null>(null);
  const [form, setForm] = useState({ name: "", tag: "", description: "", is_open: false });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!me) return;
    void api.get<Profile>(`/api/users/${me.username}`).then((p) => {
      if (p.guild) navigate(`/g/${p.guild.tag}`, { replace: true });
    });
    void api.get<Guild[]>("/api/guilds").then(setGuilds);
  }, [me, navigate]);

  const search = async (e: FormEvent) => {
    e.preventDefault();
    setGuilds(await api.get<Guild[]>(`/api/guilds?q=${encodeURIComponent(q)}`));
  };
  const create = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const g = await api.post<Guild>("/api/guilds", form);
      navigate(`/g/${g.tag}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <>
      <h1>Guildes</h1>
      <section className="card">
        <form className="row" onSubmit={search}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nom ou tag de guilde" />
          <button>Rechercher</button>
        </form>
        {guilds?.map((g) => (
          <div key={g.tag} className="user-row">
            <Link to={`/g/${g.tag}`}>
              [{g.tag}] {g.name}
            </Link>
            <span className="muted small">
              {g.members_count} membres · {g.is_open ? "ouverte" : "sur demande"}
            </span>
          </div>
        ))}
      </section>
      <form className="card form" onSubmit={create}>
        <h2>Fonder une guilde</h2>
        <label>
          Nom
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required minLength={3} maxLength={40} />
        </label>
        <label>
          Tag (2 à 6 caractères)
          <input value={form.tag} onChange={(e) => setForm({ ...form, tag: e.target.value })} required minLength={2} maxLength={6} pattern="[A-Za-z0-9]+" />
        </label>
        <label>
          Description
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} />
        </label>
        <label className="check">
          <input type="checkbox" checked={form.is_open} onChange={(e) => setForm({ ...form, is_open: e.target.checked })} />
          Recrutement ouvert (sans validation)
        </label>
        {error && <p className="error">{error}</p>}
        <button>Créer</button>
      </form>
    </>
  );
}
