import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet } from "../api/client";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { StatCard } from "./ui/StatCard";
import { ChartIcon, StackIcon, SparkleIcon, CalendarIcon } from "./ui/Icon";

interface DashboardMetrics {
  total_campaigns: number;
  total_posts: number;
  published_posts: number;
  pending_moderation: number;
  rejected_posts: number;
}

/**
 * Pipeline outcome is a *status* encoding, not a series encoding — so each bar wears a
 * reserved status color and is always accompanied by its axis label and a direct value
 * label. Status never travels by color alone.
 */
const OUTCOMES = [
  { key: "published_posts", name: "Published", color: "#0ca30c" },
  { key: "pending_moderation", name: "In review", color: "#fab219" },
  { key: "rejected_posts", name: "Rejected", color: "#d03b3b" },
] as const;

// Recessive chart chrome — gridlines and axes must never compete with the marks.
const GRID = "#e1e0d9";
const AXIS_INK = "#898781";

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl bg-white px-3 py-2 text-sm shadow-lift ring-1 ring-slate-900/10">
      <div className="flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: payload[0].payload.color }}
        />
        <span className="text-slate-500">{label}</span>
        <span className="font-semibold tabular-nums text-slate-900">{payload[0].value}</span>
      </div>
    </div>
  );
}

/** Analytics overview backed by GET /api/v1/analytics/dashboard. */
export function AnalyticsBoard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<DashboardMetrics>("/analytics/dashboard")
      .then(setMetrics)
      .catch(() => setMetrics(null))
      .finally(() => setLoading(false));
  }, []);

  const chartData = OUTCOMES.map((outcome) => ({
    name: outcome.name,
    value: metrics?.[outcome.key] ?? 0,
    color: outcome.color,
  }));

  const publishRate =
    metrics && metrics.total_posts > 0
      ? `${Math.round((metrics.published_posts / metrics.total_posts) * 100)}%`
      : "—";

  return (
    <div className="space-y-6">
      <div className="stagger grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div style={{ ["--i" as string]: 0 }}>
          <StatCard
            label="Campaigns"
            value={metrics?.total_campaigns ?? 0}
            icon={<SparkleIcon className="h-4 w-4" />}
            tone="from-brand-400 to-brand-600"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 1 }}>
          <StatCard
            label="Total posts"
            value={metrics?.total_posts ?? 0}
            icon={<StackIcon className="h-4 w-4" />}
            tone="from-series-2 to-orange-600"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 2 }}>
          <StatCard
            label="Published"
            value={metrics?.published_posts ?? 0}
            icon={<CalendarIcon className="h-4 w-4" />}
            tone="from-series-3 to-emerald-700"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 3 }}>
          <StatCard
            label="Publish rate"
            value={publishRate}
            hint="Published ÷ total posts"
            icon={<ChartIcon className="h-4 w-4" />}
            tone="from-violet-400 to-violet-600"
            loading={loading}
          />
        </div>
      </div>

      <Card>
        <CardHeader
          title="Pipeline outcomes"
          subtitle="Where every generated post ended up"
          icon={<ChartIcon className="h-5 w-5" />}
        />
        <CardBody>
          {loading ? (
            <div className="skeleton h-64 w-full" />
          ) : (
            <div style={{ width: "100%", height: 280 }}>
              <ResponsiveContainer>
                <BarChart data={chartData} margin={{ top: 24, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="name"
                    tickLine={false}
                    axisLine={{ stroke: GRID }}
                    tick={{ fill: AXIS_INK, fontSize: 12 }}
                  />
                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    width={36}
                    tick={{ fill: AXIS_INK, fontSize: 12 }}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgb(15 23 42 / 0.04)" }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={72}>
                    {chartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                    <LabelList
                      dataKey="value"
                      position="top"
                      offset={10}
                      style={{ fill: "#0b0b0b", fontSize: 13, fontWeight: 600 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
