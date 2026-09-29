import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import type { Notification } from "../api";
import { useAuth } from "../auth";
import { useResource } from "../hooks";
import { Avatar } from "./Avatar";

export function Layout() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const notifs = useResource<Notification[]>(me ? "/api/notifications" : null);
  const unread = notifs.data?.filter((n) => !n.read).length ?? 0;

  return (
    <>
      <nav className="topbar">
        <Link to="/" className="brand">
          E7 Social
        </Link>
        {me ? (
          <>
            <NavLink to="/">Fil</NavLink>
            <NavLink to="/explore">Découvrir</NavLink>
            <NavLink to="/publish">Publier</NavLink>
            <NavLink to="/friends">Amis</NavLink>
            <NavLink to="/guilds">Guilde</NavLink>
            <NavLink to="/notifications">Notifications{unread ? ` (${unread})` : ""}</NavLink>
            <span className="spacer" />
            <NavLink to={`/u/${me.username}`} className="me">
              <Avatar user={me} size={28} /> {me.display_name || me.username}
            </NavLink>
            <NavLink to="/settings">Réglages</NavLink>
            <button
              className="link"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
            >
              Déconnexion
            </button>
          </>
        ) : (
          <>
            <NavLink to="/explore">Découvrir</NavLink>
            <span className="spacer" />
            <NavLink to="/login">Connexion</NavLink>
            <NavLink to="/register">Inscription</NavLink>
          </>
        )}
      </nav>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}
