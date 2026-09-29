import type { User } from "../api";

export function Avatar({ user, size = 40 }: { user: User | null; size?: number }) {
  const label = user ? (user.display_name || user.username) : "?";
  return user?.avatar_url ? (
    <img className="avatar" src={user.avatar_url} alt="" width={size} height={size} />
  ) : (
    <span className="avatar avatar-fallback" style={{ width: size, height: size }} aria-hidden>
      {label.slice(0, 1).toUpperCase()}
    </span>
  );
}

export function UserName({ user }: { user: User | null }) {
  if (!user) return <span className="muted">Compte supprimé</span>;
  return (
    <a href={`/u/${user.username}`} className="username">
      {user.display_name || user.username} <span className="muted">@{user.username}</span>
    </a>
  );
}
