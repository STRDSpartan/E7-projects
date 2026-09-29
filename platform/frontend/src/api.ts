// Client HTTP minimal : cookies de session (same-origin), erreurs FastAPI remontées en français.

export interface User {
  username: string;
  display_name: string;
  avatar_url: string | null;
  banner_url: string | null;
  bio: string;
  server: string | null;
  favorite_hero: string | null;
  created_at: string;
}
export interface Me extends User {
  email: string;
}
export interface Profile {
  user: User;
  friends_count: number;
  posts_count: number;
  guild: { tag: string; name: string; role: string } | null;
  relationship: "none" | "self" | "friends" | "request_sent" | "request_received";
}
export type PostKind = "text" | "vitrine" | "clip" | "achievement";
export interface Post {
  id: number;
  author: User;
  kind: PostKind;
  title: string;
  body: string;
  media_url: string | null;
  media_type: string | null;
  roster: Record<string, unknown> | null;
  achievement: Record<string, unknown> | null;
  visibility: string;
  created_at: string;
  likes: number;
  liked_by_me: boolean;
  comments: number;
}
export interface Comment {
  id: number;
  author: User;
  body: string;
  created_at: string;
}
export interface FriendRequest {
  id: number;
  user: User;
  direction: "incoming" | "outgoing";
  created_at: string;
}
export interface Notification {
  id: number;
  kind: string;
  payload: Record<string, unknown>;
  read: boolean;
  created_at: string;
}
export interface Guild {
  tag: string;
  name: string;
  description: string;
  server: string | null;
  emblem_url: string | null;
  is_open: boolean;
  members_count: number;
  created_at: string;
  my_role: string | null;
}
export interface Member {
  user: User;
  role: string;
  joined_at: string;
}
export interface JoinRequest {
  id: number;
  user: User;
  message: string;
  created_at: string;
}
export interface Channel {
  id: number;
  name: string;
  topic: string;
  officers_only: boolean;
}
export interface Message {
  id: number;
  channel_id: number;
  author: User | null;
  body: string;
  created_at: string;
}
export interface Thread {
  id: number;
  title: string;
  category: string;
  author: User | null;
  pinned: boolean;
  locked: boolean;
  created_at: string;
  last_post_at: string;
  replies: number;
}
export interface ForumPost {
  id: number;
  author: User | null;
  body: string;
  created_at: string;
  edited_at: string | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: "same-origin", headers: {} };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { "Content-Type": "application/json" };
  }
  const res = await fetch(path, init);
  if (!res.ok) {
    let message = `Erreur ${res.status}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = "Champs invalides.";
    } catch {
      /* réponse sans JSON */
    }
    throw new ApiError(res.status, message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T = void>(path: string, body?: unknown) => request<T>("DELETE", path, body),
};

export function channelSocket(channelId: number): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${proto}://${location.host}/api/ws/channels/${channelId}`);
}

export const KIND_LABELS: Record<PostKind, string> = {
  text: "Message",
  vitrine: "Vitrine",
  clip: "Clip",
  achievement: "Succès",
};

export interface ThreadOut {
  thread: Thread;
  posts: ForumPost[];
}
