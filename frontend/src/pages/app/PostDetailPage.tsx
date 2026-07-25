import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPost, API_ORIGIN } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { PostStatusBadge } from "../../components/PostStatusBadge";
import type { Campaign, ContentItem } from "../../types/content";

export function PostDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    if (!id) return;
    apiGet<Campaign>(`/campaigns/${id}`)
      .then(setCampaign)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(load, [id]);

  async function act(path: string) {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/campaigns/${id}/${path}`);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !campaign) {
    return (
      <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {error}
      </p>
    );
  }
  if (!campaign) {
    return (
      <Card>
        <CardBody className="space-y-3">
          <div className="skeleton h-6 w-40" />
          <div className="skeleton h-24 w-full" />
        </CardBody>
      </Card>
    );
  }

  const anyApproved = campaign.calendar.some((item) => item.status === "approved");
  const anyRejected = campaign.calendar.some((item) => item.status === "rejected");

  return (
    <div className="space-y-5">
      <button
        type="button"
        onClick={() => navigate("/app/posts")}
        className="text-sm font-medium text-slate-500 transition-colors hover:text-brand-600"
      >
        ← Back to my posts
      </button>

      {error && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="stagger grid gap-5 lg:grid-cols-2">
        {campaign.calendar.map((item, i) => (
          <div key={i} style={{ ["--i" as string]: i }}>
            <PostCard item={item} />
          </div>
        ))}
      </div>

      <div className="flex flex-wrap justify-end gap-3">
        {anyRejected && (
          <Button variant="secondary" onClick={() => navigate("/app/compose")}>
            Edit & resubmit
          </Button>
        )}
        {anyApproved && (
          <>
            <Button variant="secondary" onClick={() => act("schedule")} disabled={busy}>
              Schedule for later
            </Button>
            <Button onClick={() => act("approve")} loading={busy}>
              Publish now
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function PostCard({ item }: { item: ContentItem }) {
  return (
    <Card className="h-full">
      <CardHeader
        title={<span className="capitalize">{item.platform}</span>}
        action={<PostStatusBadge status={item.status} />}
      />
      <CardBody className="space-y-4">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{item.body}</p>

        {item.media.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {item.media.map((m) => (
              <div key={m.id} className="overflow-hidden rounded-xl ring-1 ring-slate-200">
                {m.kind === "image" && (
                  <img src={`${API_ORIGIN}${m.url}`} alt="" className="h-28 w-full object-cover" />
                )}
                {m.kind === "audio" && (
                  <div className="flex h-28 items-center bg-slate-50 px-2">
                    <audio src={`${API_ORIGIN}${m.url}`} controls className="w-full" />
                  </div>
                )}
                {m.kind === "video" && (
                  <video
                    src={`${API_ORIGIN}${m.url}`}
                    controls
                    className="h-28 w-full bg-slate-900 object-cover"
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {item.status === "rejected" && item.moderation_reasons.length > 0 && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <p className="font-semibold">Rejected by brand-safety review</p>
            <p className="mt-1">{item.moderation_reasons.join(", ")}</p>
          </div>
        )}

        {(item.scheduled_at || item.published_at) && (
          <p className="border-t border-slate-100 pt-3 text-xs text-slate-400">
            {item.published_at
              ? `Published ${new Date(item.published_at).toLocaleString()}`
              : `Scheduled for ${new Date(item.scheduled_at!).toLocaleString()}`}
          </p>
        )}
      </CardBody>
    </Card>
  );
}
