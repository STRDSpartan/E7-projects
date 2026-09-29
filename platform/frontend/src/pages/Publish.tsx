import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, KIND_LABELS, type PostKind } from "../api";

const HINTS: Record<PostKind, string> = {
  text: "Un message libre.",
  vitrine: "Importez le roster.json exporté par e7showcase (scan ou import Fribbels).",
  clip: "Une vidéo MP4/WebM (60 Mo max.) : combat, invocation, arène…",
  achievement: "Une capture de votre succès : rang Légende, abîme, 6★…",
};

export function PublishPage() {
  const navigate = useNavigate();
  const [kind, setKind] = useState<PostKind>("vitrine");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { kind, title, body, visibility };
      if (kind === "vitrine") {
        if (!file) throw new Error("Choisissez votre roster.json.");
        payload.roster = JSON.parse(await file.text()) as unknown;
      } else if (file) {
        const form = new FormData();
        form.append("file", file);
        const media = await api.post<{ url: string }>("/api/media", form);
        payload.media_url = media.url;
      }
      if (kind === "achievement") payload.achievement = { label: title };
      await api.post("/api/posts", payload);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const accept = kind === "vitrine" ? "application/json" : kind === "clip" ? "video/mp4,video/webm" : "image/png,image/jpeg,image/webp,image/gif";

  return (
    <form className="card form" onSubmit={submit}>
      <h1>Publier</h1>
      <div className="tabs">
        {(Object.keys(KIND_LABELS) as PostKind[]).map((k) => (
          <button type="button" key={k} className={k === kind ? "active" : ""} onClick={() => { setKind(k); setFile(null); }}>
            {KIND_LABELS[k]}
          </button>
        ))}
      </div>
      <p className="muted">{HINTS[kind]}</p>
      <label>
        Titre
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
      </label>
      <label>
        Texte
        <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4} maxLength={5000} />
      </label>
      {kind !== "text" && (
        <label>
          Fichier
          <input type="file" accept={accept} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
      )}
      <label>
        Visibilité
        <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
          <option value="public">Public</option>
          <option value="friends">Amis</option>
          <option value="guild">Guilde</option>
        </select>
      </label>
      <p className="muted small">N'utilisez que vos propres captures et clips. Pas d'illustrations officielles redistribuées.</p>
      {error && <p className="error">{error}</p>}
      <button disabled={busy}>Publier</button>
    </form>
  );
}
