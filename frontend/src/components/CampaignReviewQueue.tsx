import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";

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

  const load = () => apiGet<Campaign[]>("/campaigns").then(setCampaigns).catch(() => setCampaigns([]));

  useEffect(() => {
    load();
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

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <h2 className="text-lg font-semibold mb-3">Campaign Review Queue</h2>
      <ul className="space-y-3">
        {campaigns.map((c) => (
          <li key={c.id} className="rounded border border-gray-100 p-3">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium">{c.prompt}</p>
                <p className="text-xs text-gray-500 capitalize">{c.status}</p>
              </div>
              <button
                type="button"
                disabled={busyId === c.id || c.status === "published"}
                onClick={() => approve(c.id)}
                className="px-3 py-1 text-sm rounded bg-indigo-600 text-white disabled:opacity-50"
              >
                {c.status === "published" ? "Published" : busyId === c.id ? "Approving…" : "Approve"}
              </button>
            </div>
          </li>
        ))}
        {campaigns.length === 0 && (
          <li className="py-4 text-center text-gray-400">No campaigns pending review</li>
        )}
      </ul>
    </div>
  );
}
