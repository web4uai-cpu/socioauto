import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPost, API_ORIGIN } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { PostStatusBadge } from "../../components/PostStatusBadge";
import type { Campaign } from "../../types/content";

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

  async function approveAndPublish() {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/campaigns/${id}/approve`);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function scheduleForLater() {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/campaigns/${id}/schedule`);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error)
    return (
      <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
        {error}
      </p>
    );
  if (!campaign) return <p className="text-sm text-gray-500">Loading…</p>;

  const anyApproved = campaign.calendar.some((item) => item.status === "approved");
  const anyRejected = campaign.calendar.some((item) => item.status === "rejected");

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={() => navigate("/app/posts")}
        className="text-sm text-gray-500 hover:text-gray-800"
      >
        ← Back to my posts
      </button>

      {campaign.calendar.map((item, i) => (
        <Card key={i}>
          <CardBody className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium capitalize">{item.platform}</span>
              <PostStatusBadge status={item.status} />
            </div>
            <p className="whitespace-pre-wrap text-sm text-gray-800">{item.body}</p>

            {item.media.length > 0 && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {item.media.map((m) => (
                  <div key={m.id} className="rounded-lg border border-gray-200 p-1">
                    {m.kind === "image" && (
                      <img src={`${API_ORIGIN}${m.url}`} alt="" className="h-24 w-full rounded object-cover" />
                    )}
                    {m.kind === "audio" && <audio src={`${API_ORIGIN}${m.url}`} controls className="w-full" />}
                    {m.kind === "video" && (
                      <video src={`${API_ORIGIN}${m.url}`} controls className="h-24 w-full rounded object-cover" />
                    )}
                  </div>
                ))}
              </div>
            )}

            {item.status === "rejected" && item.moderation_reasons.length > 0 && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
                Rejected: {item.moderation_reasons.join(", ")}
              </div>
            )}
          </CardBody>
        </Card>
      ))}

      <div className="flex justify-end gap-2">
        {anyRejected && (
          <Button variant="secondary" onClick={() => navigate("/app/compose")}>
            Edit & resubmit
          </Button>
        )}
        {anyApproved && (
          <>
            <Button variant="secondary" onClick={scheduleForLater} disabled={busy}>
              Schedule for later
            </Button>
            <Button onClick={approveAndPublish} disabled={busy}>
              Publish now
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
