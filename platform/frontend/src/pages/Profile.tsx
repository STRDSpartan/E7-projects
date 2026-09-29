import { Link, useParams } from "react-router-dom";
import { api, type FriendRequest, type Post, type Profile } from "../api";
import { Avatar } from "../components/Avatar";
import { PostList } from "../components/PostCard";
import { useResource } from "../hooks";

export function ProfilePage() {
  const { username = "" } = useParams();
  const profile = useResource<Profile>(`/api/users/${username}`);
  const posts = useResource<Post[]>(`/api/users/${username}/posts`);
  if (profile.error) return <p className="error">{profile.error}</p>;
  const p = profile.data;
  if (!p) return <p className="muted">Chargement…</p>;

  const addFriend = async () => {
    await api.post("/api/friends/requests", { username });
    await profile.reload();
  };
  const accept = async () => {
    const reqs = await api.get<FriendRequest[]>("/api/friends/requests");
    const r = reqs.find((x) => x.user.username === username && x.direction === "incoming");
    if (r) await api.post(`/api/friends/requests/${r.id}/accept`);
    await profile.reload();
  };
  const removeFriend = async () => {
    if (!confirm("Retirer de vos amis ?")) return;
    await api.del(`/api/friends/${username}`);
    await profile.reload();
  };

  return (
    <>
      <section className="card profile">
        <div className="banner" style={p.user.banner_url ? { backgroundImage: `url(${p.user.banner_url})` } : undefined} />
        <div className="profile-head">
          <Avatar user={p.user} size={96} />
          <div>
            <h1>{p.user.display_name || p.user.username}</h1>
            <div className="muted">@{p.user.username}</div>
            <div className="small">
              {p.user.server && <span className="pill">Serveur {p.user.server}</span>}
              {p.user.favorite_hero && <span className="pill">Héros favori : {p.user.favorite_hero}</span>}
              {p.guild && (
                <Link className="pill" to={`/g/${p.guild.tag}`}>
                  [{p.guild.tag}] {p.guild.name}
                </Link>
              )}
            </div>
          </div>
          <div className="actions">
            {p.relationship === "none" && <button onClick={addFriend}>Ajouter en ami</button>}
            {p.relationship === "request_sent" && <button disabled>Demande envoyée</button>}
            {p.relationship === "request_received" && <button onClick={accept}>Accepter la demande</button>}
            {p.relationship === "friends" && (
              <button className="secondary" onClick={removeFriend}>
                Amis ✓
              </button>
            )}
            {p.relationship === "self" && <Link to="/settings">Modifier le profil</Link>}
          </div>
        </div>
        {p.user.bio && <p className="pre">{p.user.bio}</p>}
        <div className="stats">
          <span>
            <strong>{p.posts_count}</strong> publications
          </span>
          <span>
            <strong>{p.friends_count}</strong> amis
          </span>
        </div>
      </section>
      <h2>Publications</h2>
      <PostList posts={posts.data} reload={posts.reload} />
    </>
  );
}
