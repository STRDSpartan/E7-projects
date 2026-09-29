import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, channelSocket, type Channel, type Guild, type JoinRequest, type Member, type Message, type Thread } from "../api";
import { useAuth } from "../auth";
import { Avatar, UserName } from "../components/Avatar";
import { formatDate, useResource } from "../hooks";

const RANK: Record<string, number> = { leader: 3, officer: 2, member: 1 };
const ROLE_FR: Record<string, string> = { leader: "Chef", officer: "Officier", member: "Membre" };

function Chat({ guild }: { guild: Guild }) {
  const channels = useResource<Channel[]>(`/api/guilds/${guild.tag}/channels`);
  const [active, setActive] = useState<Channel | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active && channels.data?.length) setActive(channels.data[0]);
  }, [channels.data, active]);

  useEffect(() => {
    if (!active) return;
    let closed = false;
    void api.get<Message[]>(`/api/channels/${active.id}/messages`).then((m) => !closed && setMessages(m));
    const ws = channelSocket(active.id);
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data as string) as { type: string; message: Message };
      if (data.type === "message") setMessages((prev) => (prev.some((m) => m.id === data.message.id) ? prev : [...prev, data.message]));
    };
    return () => {
      closed = true;
      ws.close();
    };
  }, [active]);

  useEffect(() => bottom.current?.scrollIntoView({ block: "end" }), [messages]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    if (!active || !draft.trim()) return;
    const m = await api.post<Message>(`/api/channels/${active.id}/messages`, { body: draft });
    setDraft("");
    setMessages((prev) => (prev.some((x) => x.id === m.id) ? prev : [...prev, m]));
  };
  const createChannel = async () => {
    const name = prompt("Nom du canal (minuscules, sans espace)");
    if (!name) return;
    await api.post(`/api/guilds/${guild.tag}/channels`, { name });
    await channels.reload();
  };

  return (
    <div className="chat">
      <aside>
        {channels.data?.map((c) => (
          <button key={c.id} className={c.id === active?.id ? "channel active" : "channel"} onClick={() => setActive(c)}>
            # {c.name} {c.officers_only && "🔒"}
          </button>
        ))}
        {RANK[guild.my_role ?? ""] >= 2 && (
          <button className="link" onClick={createChannel}>
            + canal
          </button>
        )}
      </aside>
      <section>
        {active?.topic && <div className="muted small">{active.topic}</div>}
        <div className="messages">
          {messages.map((m) => (
            <div key={m.id} className="message">
              <Avatar user={m.author} size={28} />
              <div>
                <UserName user={m.author} /> <span className="muted small">{formatDate(m.created_at)}</span>
                <div className="pre">{m.body}</div>
              </div>
            </div>
          ))}
          <div ref={bottom} />
        </div>
        <form className="row" onSubmit={send}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={active ? `Message dans #${active.name}` : ""} maxLength={2000} />
          <button>Envoyer</button>
        </form>
      </section>
    </div>
  );
}

function Forum({ guild }: { guild: Guild }) {
  const threads = useResource<Thread[]>(`/api/guilds/${guild.tag}/threads`);
  const navigate = useNavigate();
  const [form, setForm] = useState({ title: "", category: "général", body: "" });
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const categories = ["général", "gvg", "builds", "événements", ...(RANK[guild.my_role ?? ""] >= 2 ? ["annonces"] : [])];

  const create = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const t = await api.post<Thread>(`/api/guilds/${guild.tag}/threads`, form);
      navigate(`/threads/${t.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <>
      <button onClick={() => setOpen(!open)}>{open ? "Annuler" : "Nouveau sujet"}</button>
      {open && (
        <form className="card form" onSubmit={create}>
          <input placeholder="Titre" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required minLength={3} />
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <textarea rows={5} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} required />
          {error && <p className="error">{error}</p>}
          <button>Publier</button>
        </form>
      )}
      <table className="threads">
        <tbody>
          {threads.data?.map((t) => (
            <tr key={t.id}>
              <td>
                {t.pinned && "📌 "}
                {t.locked && "🔒 "}
                <Link to={`/threads/${t.id}`}>{t.title}</Link>
                <div className="muted small">
                  {t.category} · <UserName user={t.author} />
                </div>
              </td>
              <td className="muted small">{t.replies} réponses</td>
              <td className="muted small">{formatDate(t.last_post_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Members({ guild, reload }: { guild: Guild; reload: () => void }) {
  const { me } = useAuth();
  const members = useResource<Member[]>(`/api/guilds/${guild.tag}/members`);
  const myRank = RANK[guild.my_role ?? ""] ?? 0;
  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
    await members.reload();
    reload();
  };
  return (
    <>
      {members.data?.map((m) => (
        <div key={m.user.username} className="user-row">
          <Avatar user={m.user} size={32} /> <UserName user={m.user} />
          <span className="pill">{ROLE_FR[m.role]}</span>
          {guild.my_role === "leader" && m.user.username !== me?.username && (
            <select
              value={m.role}
              onChange={(e) => {
                const role = e.target.value;
                if (role === "leader" && !confirm(`Transmettre la direction à ${m.user.username} ?`)) return;
                void run(() => api.patch(`/api/guilds/${guild.tag}/members/${m.user.username}`, { role }));
              }}
            >
              <option value="member">Membre</option>
              <option value="officer">Officier</option>
              <option value="leader">Chef</option>
            </select>
          )}
          {myRank > RANK[m.role] && (
            <button className="link danger" onClick={() => confirm("Exclure ce membre ?") && void run(() => api.del(`/api/guilds/${guild.tag}/members/${m.user.username}`))}>
              Exclure
            </button>
          )}
        </div>
      ))}
    </>
  );
}

function Requests({ guild, reload }: { guild: Guild; reload: () => void }) {
  const requests = useResource<JoinRequest[]>(`/api/guilds/${guild.tag}/requests`);
  const respond = async (r: JoinRequest, accept: boolean) => {
    await api.post(`/api/guilds/${guild.tag}/requests/${r.id}/${accept ? "accept" : "decline"}`);
    await requests.reload();
    reload();
  };
  if (requests.data?.length === 0) return <p className="muted">Aucune demande en attente.</p>;
  return (
    <>
      {requests.data?.map((r) => (
        <div key={r.id} className="user-row">
          <Avatar user={r.user} size={32} /> <UserName user={r.user} />
          <span className="muted">{r.message}</span>
          <button onClick={() => respond(r, true)}>Accepter</button>
          <button className="secondary" onClick={() => respond(r, false)}>
            Refuser
          </button>
        </div>
      ))}
    </>
  );
}

export function GuildPage() {
  const { tag = "" } = useParams();
  const navigate = useNavigate();
  const { me } = useAuth();
  const guild = useResource<Guild>(`/api/guilds/${tag}`);
  const [tab, setTab] = useState("chat");
  const [info, setInfo] = useState<string | null>(null);
  const g = guild.data;
  if (guild.error) return <p className="error">{guild.error}</p>;
  if (!g) return <p className="muted">Chargement…</p>;

  const join = async () => {
    try {
      const r = await api.post<{ status: string }>(`/api/guilds/${g.tag}/join`, { message: "" });
      setInfo(r.status === "member" ? "Bienvenue !" : "Demande envoyée aux officiers.");
      await guild.reload();
    } catch (e) {
      setInfo(e instanceof Error ? e.message : String(e));
    }
  };
  const leave = async () => {
    if (!confirm("Quitter la guilde ?")) return;
    try {
      await api.post(`/api/guilds/${g.tag}/leave`);
      navigate("/guilds");
    } catch (e) {
      setInfo(e instanceof Error ? e.message : String(e));
    }
  };
  const tabs: [string, string][] = [
    ["chat", "Discussion"],
    ["forum", "Forum"],
    ["members", `Membres (${g.members_count})`],
    ...(RANK[g.my_role ?? ""] >= 2 ? ([["requests", "Candidatures"]] as [string, string][]) : []),
  ];

  return (
    <>
      <section className="card guild-head">
        {g.emblem_url && <img src={g.emblem_url} alt="" width={64} height={64} />}
        <div>
          <h1>
            [{g.tag}] {g.name}
          </h1>
          <p className="pre">{g.description}</p>
          <span className="muted small">
            {g.members_count} membres · {g.is_open ? "recrutement ouvert" : "sur candidature"}
          </span>
        </div>
        <div className="actions">
          {me && !g.my_role && <button onClick={join}>Rejoindre</button>}
          {g.my_role && (
            <button className="secondary" onClick={leave}>
              Quitter
            </button>
          )}
        </div>
      </section>
      {info && <p className="muted">{info}</p>}
      {g.my_role ? (
        <>
          <div className="tabs">
            {tabs.map(([key, label]) => (
              <button key={key} className={key === tab ? "active" : ""} onClick={() => setTab(key)}>
                {label}
              </button>
            ))}
          </div>
          {tab === "chat" && <Chat guild={g} />}
          {tab === "forum" && <Forum guild={g} />}
          {tab === "members" && <Members guild={g} reload={guild.reload} />}
          {tab === "requests" && <Requests guild={g} reload={guild.reload} />}
        </>
      ) : (
        <p className="muted">La discussion et le forum sont réservés aux membres.</p>
      )}
    </>
  );
}
