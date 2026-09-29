import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";

const SERVERS = ["Global", "Europe", "Asia", "Korea", "Japan"];

export function SettingsPage() {
  const { me, refresh } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ display_name: "", bio: "", server: "", favorite_hero: "", avatar_url: "", banner_url: "" });
  const [info, setInfo] = useState<string | null>(null);
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (me)
      setForm({
        display_name: me.display_name,
        bio: me.bio,
        server: me.server ?? "",
        favorite_hero: me.favorite_hero ?? "",
        avatar_url: me.avatar_url ?? "",
        banner_url: me.banner_url ?? "",
      });
  }, [me]);

  const upload = async (key: "avatar_url" | "banner_url", file: File | undefined) => {
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    const media = await api.post<{ url: string }>("/api/media", data);
    setForm((f) => ({ ...f, [key]: media.url }));
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.patch("/api/users/me", {
        ...form,
        server: form.server || null,
        avatar_url: form.avatar_url || null,
        banner_url: form.banner_url || null,
      });
      await refresh();
      setInfo("Profil enregistré.");
    } catch (err) {
      setInfo(err instanceof Error ? err.message : String(err));
    }
  };

  const deleteAccount = async () => {
    if (!confirm("Supprimer définitivement votre compte et vos publications ?")) return;
    try {
      await api.del("/api/users/me", { password });
      await refresh();
      navigate("/register");
    } catch (err) {
      setInfo(err instanceof Error ? err.message : String(err));
    }
  };

  if (!me) return null;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <form className="card form" onSubmit={save}>
        <h1>Mon profil</h1>
        <label>
          Pseudo en jeu
          <input value={form.display_name} onChange={set("display_name")} maxLength={40} />
        </label>
        <label>
          Présentation
          <textarea value={form.bio} onChange={set("bio")} rows={4} maxLength={1000} />
        </label>
        <label>
          Serveur
          <select value={form.server} onChange={set("server")}>
            <option value="">—</option>
            {SERVERS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Héros favori
          <input value={form.favorite_hero} onChange={set("favorite_hero")} maxLength={60} />
        </label>
        <label>
          Avatar
          <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(e) => upload("avatar_url", e.target.files?.[0])} />
        </label>
        <label>
          Bannière
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => upload("banner_url", e.target.files?.[0])} />
        </label>
        {info && <p className="muted">{info}</p>}
        <button>Enregistrer</button>
      </form>
      <section className="card form">
        <h2>Mes données</h2>
        <a href="/api/users/me/export" download="e7social-export.json">
          Télécharger toutes mes données (JSON)
        </a>
        <label>
          Mot de passe (pour supprimer le compte)
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        <button className="danger" onClick={deleteAccount} disabled={!password}>
          Supprimer mon compte
        </button>
      </section>
    </>
  );
}
