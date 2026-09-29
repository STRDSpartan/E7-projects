import { useState } from "react";
import { api, type FriendRequest, type User } from "../api";
import { Avatar, UserName } from "../components/Avatar";
import { useResource } from "../hooks";

export function FriendsPage() {
  const friends = useResource<User[]>("/api/friends");
  const requests = useResource<FriendRequest[]>("/api/friends/requests");
  const [q, setQ] = useState("");
  const [results, setResults] = useState<User[] | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const search = async () => {
    if (q.trim().length < 2) return;
    setResults(await api.get<User[]>(`/api/users/search?q=${encodeURIComponent(q)}`));
  };
  const add = async (username: string) => {
    try {
      await api.post("/api/friends/requests", { username });
      setInfo(`Demande envoyée à ${username}.`);
    } catch (e) {
      setInfo(e instanceof Error ? e.message : String(e));
    }
    await Promise.all([requests.reload(), friends.reload()]);
  };
  const respond = async (r: FriendRequest, accept: boolean) => {
    await api.post(`/api/friends/requests/${r.id}/${accept ? "accept" : "decline"}`);
    await Promise.all([requests.reload(), friends.reload()]);
  };

  return (
    <>
      <h1>Amis</h1>
      <section className="card">
        <h2>Rechercher un joueur</h2>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            void search();
          }}
        >
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Pseudo en jeu ou identifiant" />
          <button>Rechercher</button>
        </form>
        {info && <p className="muted">{info}</p>}
        {results?.map((u) => (
          <div key={u.username} className="user-row">
            <Avatar user={u} size={32} /> <UserName user={u} />
            <button onClick={() => add(u.username)}>Ajouter</button>
          </div>
        ))}
        {results && !results.length && <p className="muted">Aucun joueur trouvé.</p>}
      </section>
      {!!requests.data?.length && (
        <section className="card">
          <h2>Demandes</h2>
          {requests.data.map((r) => (
            <div key={r.id} className="user-row">
              <Avatar user={r.user} size={32} /> <UserName user={r.user} />
              {r.direction === "incoming" ? (
                <>
                  <button onClick={() => respond(r, true)}>Accepter</button>
                  <button className="secondary" onClick={() => respond(r, false)}>
                    Refuser
                  </button>
                </>
              ) : (
                <span className="muted">en attente</span>
              )}
            </div>
          ))}
        </section>
      )}
      <section className="card">
        <h2>Mes amis ({friends.data?.length ?? 0})</h2>
        {friends.data?.map((u) => (
          <div key={u.username} className="user-row">
            <Avatar user={u} size={32} /> <UserName user={u} />
          </div>
        ))}
      </section>
    </>
  );
}
