import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api, type Notification } from "../api";
import { formatDate, useResource } from "../hooks";

function describe(n: Notification) {
  const p = n.payload as Record<string, string>;
  const from = p.username ? <Link to={`/u/${p.username}`}>{p.username}</Link> : null;
  switch (n.kind) {
    case "friend_request":
      return <>{from} vous a envoyé une demande d'ami. <Link to="/friends">Répondre</Link></>;
    case "friend_accepted":
      return <>{from} a accepté votre demande d'ami.</>;
    case "post_liked":
      return <>{from} a aimé votre publication.</>;
    case "post_commented":
      return <>{from} a commenté votre publication.</>;
    case "guild_join_request":
      return <>{from} demande à rejoindre <Link to={`/g/${p.guild}`}>[{p.guild}]</Link>.</>;
    case "guild_accepted":
      return <>Bienvenue dans <Link to={`/g/${p.guild}`}>[{p.guild}]</Link> !</>;
    case "guild_kicked":
      return <>Vous avez été retiré de [{p.guild}].</>;
    default:
      return <>{n.kind}</>;
  }
}

export function NotificationsPage() {
  const { data } = useResource<Notification[]>("/api/notifications");
  useEffect(() => {
    if (data?.some((n) => !n.read)) void api.post("/api/notifications/read");
  }, [data]);
  return (
    <>
      <h1>Notifications</h1>
      {data?.length === 0 && <p className="muted">Aucune notification.</p>}
      {data?.map((n) => (
        <div key={n.id} className={`card notif ${n.read ? "" : "unread"}`}>
          {describe(n)} <span className="muted small">{formatDate(n.created_at)}</span>
        </div>
      ))}
    </>
  );
}
