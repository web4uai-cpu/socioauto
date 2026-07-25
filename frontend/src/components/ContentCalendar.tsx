import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../api/client";

interface ContentItem {
  platform: string;
  topic: string;
  body: string;
  status: string;
  scheduled_at: string | null;
  published_at: string | null;
}

interface Campaign {
  id: string;
  prompt: string;
  status: string;
  calendar: ContentItem[];
}

/** A calendar item flattened out of its parent campaign. */
interface PlannedPost extends ContentItem {
  campaignId: string;
  /** Effective date this post sits on: published date if published, else scheduled. */
  date: Date | null;
}

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  pending_moderation: "bg-amber-100 text-amber-800",
  approved: "bg-blue-100 text-blue-800",
  rejected: "bg-red-100 text-red-800",
  scheduled: "bg-indigo-100 text-indigo-800",
  published: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** Days to render for a month, padded to whole Monday-start weeks. */
function monthGrid(month: Date): Date[] {
  const first = startOfMonth(month);
  // getDay() is Sunday-based; shift so Monday is column 0.
  const leading = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - leading);

  const days: Date[] = [];
  for (let i = 0; i < 42; i++) {
    const day = new Date(start);
    day.setDate(start.getDate() + i);
    days.push(day);
  }
  // Trim a trailing all-next-month week so short months don't render a dead row.
  return days.slice(0, days[35].getMonth() === month.getMonth() ? 42 : 35);
}

function PostChip({ post }: { post: PlannedPost }) {
  const style = STATUS_STYLES[post.status] ?? "bg-gray-100 text-gray-700";
  return (
    <div
      className={`truncate rounded px-1 py-0.5 text-xs ${style}`}
      title={`${post.platform} — ${post.topic}\n${post.status}\n\n${post.body}`}
    >
      <span className="font-medium uppercase">{post.platform}</span> {post.topic}
    </div>
  );
}

/**
 * Month view of every scheduled and published post across the user's campaigns.
 *
 * Backed by GET /api/v1/campaigns — each campaign's calendar items are flattened and placed
 * on their published date (if published) or scheduled date. Items with neither are shown in
 * an "unscheduled" backlog beneath the grid, since they have no cell to occupy.
 */
export function ContentCalendar() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [month, setMonth] = useState<Date>(startOfMonth(new Date()));
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

  const posts = useMemo<PlannedPost[]>(
    () =>
      campaigns.flatMap((campaign) =>
        campaign.calendar.map((item) => {
          const raw = item.published_at ?? item.scheduled_at;
          return { ...item, campaignId: campaign.id, date: raw ? new Date(raw) : null };
        }),
      ),
    [campaigns],
  );

  const days = useMemo(() => monthGrid(month), [month]);
  const unscheduled = posts.filter((p) => p.date === null);
  const today = new Date();

  const monthLabel = month.toLocaleString(undefined, { month: "long", year: "numeric" });

  function shiftMonth(delta: number) {
    setMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1));
  }

  if (loading) return <section className="rounded-lg border border-gray-200 p-4">Loading calendar…</section>;

  return (
    <section className="rounded-lg border border-gray-200 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Content Calendar</h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Previous month"
            onClick={() => shiftMonth(-1)}
            className="px-2 py-1 text-sm rounded border border-gray-200"
          >
            ←
          </button>
          <span className="text-sm font-medium w-40 text-center">{monthLabel}</span>
          <button
            type="button"
            aria-label="Next month"
            onClick={() => shiftMonth(1)}
            className="px-2 py-1 text-sm rounded border border-gray-200"
          >
            →
          </button>
          <button
            type="button"
            onClick={() => setMonth(startOfMonth(new Date()))}
            className="ml-2 px-2 py-1 text-sm rounded border border-gray-200"
          >
            Today
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {error}
        </p>
      )}

      <div className="overflow-x-auto">
        <div className="min-w-[42rem]">
          <div className="grid grid-cols-7 gap-px text-xs font-medium text-gray-500">
            {WEEKDAYS.map((day) => (
              <div key={day} className="px-1 py-1">
                {day}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-px bg-gray-200">
            {days.map((day) => {
              const inMonth = day.getMonth() === month.getMonth();
              const dayPosts = posts.filter((p) => p.date && sameDay(p.date, day));
              return (
                <div
                  key={day.toISOString()}
                  className={`min-h-24 bg-white p-1 space-y-1 ${inMonth ? "" : "opacity-40"}`}
                >
                  <div
                    className={`text-xs ${
                      sameDay(day, today)
                        ? "font-bold text-indigo-600"
                        : "text-gray-500"
                    }`}
                  >
                    {day.getDate()}
                  </div>
                  {dayPosts.slice(0, 3).map((post, i) => (
                    <PostChip key={`${post.campaignId}-${post.platform}-${i}`} post={post} />
                  ))}
                  {dayPosts.length > 3 && (
                    <div className="text-xs text-gray-500">+{dayPosts.length - 3} more</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {unscheduled.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-1">
            Unscheduled ({unscheduled.length})
          </h3>
          <div className="flex flex-wrap gap-1">
            {unscheduled.map((post, i) => (
              <div key={`${post.campaignId}-${i}`} className="max-w-xs">
                <PostChip post={post} />
              </div>
            ))}
          </div>
        </div>
      )}

      {posts.length === 0 && !error && (
        <p className="py-4 text-center text-gray-400">No content planned yet</p>
      )}
    </section>
  );
}
