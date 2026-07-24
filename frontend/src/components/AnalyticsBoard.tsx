import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet } from "../api/client";

interface DashboardMetrics {
  total_campaigns: number;
  total_posts: number;
  published_posts: number;
  pending_moderation: number;
  rejected_posts: number;
}

/** Analytics overview backed by GET /api/v1/analytics/dashboard. */
export function AnalyticsBoard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);

  useEffect(() => {
    apiGet<DashboardMetrics>("/analytics/dashboard").then(setMetrics).catch(() => setMetrics(null));
  }, []);

  const chartData = metrics
    ? [
        { name: "Published", value: metrics.published_posts },
        { name: "Pending Review", value: metrics.pending_moderation },
        { name: "Rejected", value: metrics.rejected_posts },
      ]
    : [];

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <h2 className="text-lg font-semibold mb-3">Analytics Overview</h2>
      <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
        <Stat label="Campaigns" value={metrics?.total_campaigns ?? 0} />
        <Stat label="Total Posts" value={metrics?.total_posts ?? 0} />
        <Stat label="Published" value={metrics?.published_posts ?? 0} />
      </div>
      <div style={{ width: "100%", height: 240 }}>
        <ResponsiveContainer>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" fill="#4f46e5" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-gray-100 p-3 text-center">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-gray-500">{label}</div>
    </div>
  );
}
