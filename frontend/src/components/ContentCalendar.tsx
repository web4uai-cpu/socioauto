import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../api/client";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { CalendarIcon } from "./ui/Icon";

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
  draft: "bg-slate-100 text-slate-700",
  pending_moderation: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-200",
  approved: "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200",
  rejected: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-200",
  scheduled: "bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-200",
  published: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200",
  failed: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-200",
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
  const style = STATUS_STYLES[post.status] ?? "bg-slate-100 text-slate-700";
  return (
    <div
      className={`truncate rounded-md px-1.5 py-0.5 text-[11px] transition-transform duration-150
        hover:scale-[1.03] ${style}`}
      title={`${post.platform} — ${post.topic}\n${post.status}\n\n${post.body}`}
    >
      <span className="font-semibold uppercase">{post.platform}</span> {post.topic}
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

  if (loading) {
    return (
      <Card>
        <CardBody>
          <div className="skeleton h-72 w-full" />
        </CardBody>
      </Card>
    );
  }

  const navButton =
    "rounded-lg px-2.5 py-1.5 text-sm text-slate-600 ring-1 ring-inset ring-slate-200 " +
    "transition-all duration-150 hover:bg-slate-50 hover:ring-slate-300 active:scale-95";

  return (
    <Card>
      <CardHeader
        title="Content calendar"
        subtitle="Scheduled and published posts across every campaign"
        icon={<CalendarIcon className="h-5 w-5" />}
        action={
          <div className="flex items-center gap-2">
            <button type="button" aria-label="Previous month" onClick={() => shiftMonth(-1)} className={navButton}>
              ←
            </button>
            <span className="w-36 text-center text-sm font-semibold text-slate-700">{monthLabel}</span>
            <button type="button" aria-label="Next month" onClick={() => shiftMonth(1)} className={navButton}>
              →
            </button>
            <button
              type="button"
              onClick={() => setMonth(startOfMonth(new Date()))}
              className={`ml-1 ${navButton}`}
            >
              Today
            </button>
          </div>
        }
      />
      <CardBody className="space-y-4">
      {error && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="overflow-x-auto">
        <div className="min-w-[42rem]">
          <div className="grid grid-cols-7 gap-px text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            {WEEKDAYS.map((day) => (
              <div key={day} className="px-2 py-2">
                {day}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-px overflow-hidden rounded-xl bg-slate-200 ring-1 ring-slate-200">
            {days.map((day) => {
              const inMonth = day.getMonth() === month.getMonth();
              const isToday = sameDay(day, today);
              const dayPosts = posts.filter((p) => p.date && sameDay(p.date, day));
              return (
                <div
                  key={day.toISOString()}
                  className={`min-h-24 space-y-1 p-1.5 transition-colors duration-150 hover:bg-brand-50/50
                    ${inMonth ? "bg-white" : "bg-slate-50/80 text-slate-300"}`}
                >
                  <div
                    className={
                      isToday
                        ? "inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white"
                        : "text-xs font-medium text-slate-400"
                    }
                  >
                    {day.getDate()}
                  </div>
                  {dayPosts.slice(0, 3).map((post, i) => (
                    <PostChip key={`${post.campaignId}-${post.platform}-${i}`} post={post} />
                  ))}
                  {dayPosts.length > 3 && (
                    <div className="text-[11px] font-medium text-slate-400">
                      +{dayPosts.length - 3} more
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {unscheduled.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-700">
            Unscheduled ({unscheduled.length})
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {unscheduled.map((post, i) => (
              <div key={`${post.campaignId}-${i}`} className="max-w-xs">
                <PostChip post={post} />
              </div>
            ))}
          </div>
        </div>
      )}

      {posts.length === 0 && !error && (
        <p className="py-8 text-center text-sm text-slate-400">No content planned yet</p>
      )}
      </CardBody>
    </Card>
  );
}
