import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { CalendarIcon } from "./ui/Icon";

interface ContentItem {
  platform: string;
  topic: string;
  body: string;
  status: string;
}

interface Campaign {
  id: string;
  prompt: string;
  status: string;
  calendar: ContentItem[];
}

/**
 * Human-in-the-loop review queue: campaigns awaiting approval before Scheduling/Publishing run.
 * Backed by GET /api/v1/campaigns and POST /api/v1/campaigns/{id}/approve.
 */
export function CampaignReviewQueue() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () =>
    apiGet<Campaign[]>("/campaigns")
      .then(setCampaigns)
      .catch(() => setCampaigns([]));

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  const approve = async (id: string) => {
    setBusyId(id);
    try {
      await apiPost(`/campaigns/${id}/approve`);
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const pending = campaigns.filter((c) => c.status !== "published").length;

  return (
    <Card>
      <CardHeader
        title="Review queue"
        subtitle="Approve before scheduling and publishing run"
        icon={<CalendarIcon className="h-5 w-5" />}
        action={
          pending > 0 ? (
            <Badge tone="pending_moderation">{pending} awaiting</Badge>
          ) : (
            <Badge tone="published">All clear</Badge>
          )
        }
      />
      <CardBody className="space-y-3">
        {loading && <div className="skeleton h-20 w-full" />}

        {!loading &&
          campaigns.map((c) => (
            <div
              key={c.id}
              className="flex items-start justify-between gap-4 rounded-xl border border-slate-100 bg-white p-4
                transition-all duration-200 hover:border-brand-200 hover:shadow-card"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-slate-900">{c.prompt}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Badge tone={c.status}>{c.status.replace(/_/g, " ")}</Badge>
                  <span className="text-xs text-slate-400">
                    {c.calendar.length} item{c.calendar.length === 1 ? "" : "s"}
                  </span>
                </div>
              </div>
              <Button
                size="sm"
                variant={c.status === "published" ? "secondary" : "primary"}
                disabled={busyId === c.id || c.status === "published"}
                loading={busyId === c.id}
                onClick={() => approve(c.id)}
              >
                {c.status === "published" ? "Published" : "Approve"}
              </Button>
            </div>
          ))}

        {!loading && campaigns.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-sm font-medium text-slate-500">Nothing to review</p>
            <p className="mt-1 text-xs text-slate-400">
              New campaigns appear here once they clear moderation.
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
