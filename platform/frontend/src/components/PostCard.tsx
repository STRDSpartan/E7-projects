import { useState } from "react";
import { api, KIND_LABELS, type Comment, type Post } from "../api";
import { useAuth } from "../auth";
import { formatDate } from "../hooks";
import { Avatar, UserName } from "./Avatar";

interface RosterHero {
  name?: string;
  stars?: number;
}

function Vitrine({ roster }: { roster: Record<string, unknown> }) {
  const heroes = (Array.isArray(roster.heroes) ? roster.heroes : []) as RosterHero[];
  return (
    <div className="vitrine">
      <strong>{heroes.length} héros</strong>
      <ul>
        {heroes.slice(0, 12).map((h, i) => (
          <li key={i}>
            {h.name ?? "?"} {h.stars ? "★".repeat(h.stars) : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PostCard({ post, onDeleted }: { post: Post; onDeleted?: () => void }) {
  const { me } = useAuth();
  const [current, setCurrent] = useState(post);
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [draft, setDraft] = useState("");

  const toggleLike = async () => {
    const path = `/api/posts/${current.id}/like`;
    setCurrent(await (current.liked_by_me ? api.del<Post>(path) : api.post<Post>(path)));
  };
  const loadComments = async () => setComments(await api.get<Comment[]>(`/api/posts/${current.id}/comments`));
  const sendComment = async () => {
    if (!draft.trim()) return;
    await api.post(`/api/posts/${current.id}/comments`, { body: draft });
    setDraft("");
    setCurrent({ ...current, comments: current.comments + 1 });
    await loadComments();
  };
  const remove = async () => {
    if (!confirm("Supprimer cette publication ?")) return;
    await api.del(`/api/posts/${current.id}`);
    onDeleted?.();
  };

  return (
    <article className="card post">
      <header>
        <Avatar user={current.author} />
        <div>
          <UserName user={current.author} />
          <div className="muted small">
            {formatDate(current.created_at)} · <span className={`kind kind-${current.kind}`}>{KIND_LABELS[current.kind]}</span>
          </div>
        </div>
        {me?.username === current.author.username && (
          <button className="link danger" onClick={remove}>
            Supprimer
          </button>
        )}
      </header>
      {current.title && <h3>{current.title}</h3>}
      {current.body && <p className="pre">{current.body}</p>}
      {current.media_url && current.media_type === "video" && <video src={current.media_url} controls />}
      {current.media_url && current.media_type !== "video" && <img src={current.media_url} alt={current.title} />}
      {current.roster && <Vitrine roster={current.roster} />}
      <footer>
        <button className="link" onClick={toggleLike} disabled={!me}>
          {current.liked_by_me ? "♥" : "♡"} {current.likes}
        </button>
        <button className="link" onClick={loadComments}>
          💬 {current.comments}
        </button>
      </footer>
      {comments && (
        <div className="comments">
          {comments.map((c) => (
            <div key={c.id} className="comment">
              <UserName user={c.author} /> <span className="pre">{c.body}</span>
            </div>
          ))}
          {me && (
            <div className="row">
              <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Commenter…" />
              <button onClick={sendComment}>Envoyer</button>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export function PostList({ posts, reload }: { posts: Post[] | null; reload: () => void }) {
  if (!posts) return <p className="muted">Chargement…</p>;
  if (!posts.length) return <p className="muted">Rien à afficher pour l'instant.</p>;
  return (
    <>
      {posts.map((p) => (
        <PostCard key={p.id} post={p} onDeleted={reload} />
      ))}
    </>
  );
}
