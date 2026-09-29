import type { Post } from "../api";
import { PostList } from "../components/PostCard";
import { useResource } from "../hooks";

export function FeedPage() {
  const { data, reload } = useResource<Post[]>("/api/feed");
  return (
    <>
      <h1>Fil d'actualité</h1>
      <p className="muted">Vos publications, celles de vos amis et de votre guilde.</p>
      <PostList posts={data} reload={reload} />
    </>
  );
}

export function ExplorePage() {
  const { data, reload } = useResource<Post[]>("/api/explore");
  return (
    <>
      <h1>Découvrir</h1>
      <p className="muted">Les dernières vitrines, clips et succès publics.</p>
      <PostList posts={data} reload={reload} />
    </>
  );
}
