import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { ExplorePage, FeedPage } from "./pages/Feed";
import { FriendsPage } from "./pages/Friends";
import { GuildPage } from "./pages/Guild";
import { GuildsPage } from "./pages/Guilds";
import { NotificationsPage } from "./pages/Notifications";
import { ProfilePage } from "./pages/Profile";
import { PublishPage } from "./pages/Publish";
import { SettingsPage } from "./pages/Settings";
import { ThreadPage } from "./pages/Thread";
import "./styles.css";

function Private({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <p className="muted">Chargement…</p>;
  return me ? <>{children}</> : <Navigate to="/login" replace />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Private><FeedPage /></Private>} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/u/:username" element={<ProfilePage />} />
            <Route path="/publish" element={<Private><PublishPage /></Private>} />
            <Route path="/friends" element={<Private><FriendsPage /></Private>} />
            <Route path="/notifications" element={<Private><NotificationsPage /></Private>} />
            <Route path="/settings" element={<Private><SettingsPage /></Private>} />
            <Route path="/guilds" element={<Private><GuildsPage /></Private>} />
            <Route path="/g/:tag" element={<GuildPage />} />
            <Route path="/threads/:id" element={<Private><ThreadPage /></Private>} />
            <Route path="*" element={<p>Page introuvable.</p>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
