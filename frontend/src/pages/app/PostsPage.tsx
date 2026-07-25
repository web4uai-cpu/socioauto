import { useEffect, useState } from "react";
import { apiGet } from "../../api/client";
import { PostList } from "../../components/PostList";
import type { Campaign } from "../../types/content";

export function PostsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<Campaign[]>("/campaigns")
      .then((data) => {
        if (!cancelled) setCampaigns(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <p className="text-sm text-gray-500">Loading your posts…</p>;
  if (error)
    return (
      <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
        {error}
      </p>
    );

  return <PostList campaigns={campaigns} />;
}
