import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ThreadOut } from "../api";
import { Avatar, UserName } from "../components/Avatar";
import { formatDate, useResource } from "../hooks";

export function ThreadPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const detail = useResource<ThreadOut>(`/api/threads/${id}`);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const d = detail.data;
  if (detail.error) return <p className="error">{detail.error}</p>;
  if (!d) return <p className="muted">Chargement…</p>;
  const t = d.thread;

  const reply = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/api/threads/${t.id}/posts`, { body: draft });
      setDraft("");
      await detail.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };
  const moderate = async (patch: Record<string, boolean>) => {
    try {
      await api.patch(`/api/threads/${t.id}`, patch);
      await detail.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };
  const remove = async () => {
    if (!confirm("Supprimer ce sujet ?")) return;
    try {
      await api.del(`/api/threads/${t.id}`);
      navigate(-1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <>
      <h1>
        {t.pinned && "📌 "}
        {t.locked && "🔒 "}
        {t.title}
      </h1>
      <div className="muted small row">
        {t.category}
        <button className="link" onClick={() => moderate({ pinned: !t.pinned })}>
          {t.pinned ? "Désépingler" : "Épingler"}
        </button>
        <button className="link" onClick={() => moderate({ locked: !t.locked })}>
          {t.locked ? "Rouvrir" : "Verrouiller"}
        </button>
        <button className="link danger" onClick={remove}>
          Supprimer
        </button>
      </div>
      {d.posts.map((p) => (
        <article key={p.id} className="card forum-post">
          <header>
            <Avatar user={p.author} size={32} /> <UserName user={p.author} />
            <span className="muted small">{formatDate(p.created_at)}</span>
          </header>
          <div className="pre">{p.body}</div>
        </article>
      ))}
      {error && <p className="error">{error}</p>}
      {!t.locked && (
        <form className="card form" onSubmit={reply}>
          <textarea rows={4} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Répondre…" required />
          <button>Répondre</button>
        </form>
      )}
    </>
  );
}
