import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { StatCard } from "./ui/StatCard";
import { CardIcon } from "./ui/Icon";

interface Invoice {
  id: string;
  amount_due: number;
  currency: string;
  status: "draft" | "open" | "paid" | "void" | "uncollectible";
  issued_at: string;
}

interface UnavailableMetric {
  metric: string;
  reason: string;
  needs: string;
}

interface RevenueReport {
  revenue: { mrr: number; arr: number; paying_accounts: number };
  invoices: { collected: number; outstanding: number };
  generation_cost: {
    total_tokens: number;
    estimated_cost_usd: number | null;
    priced: boolean;
    note: string;
  };
  growth_insights: string[];
  unavailable: UnavailableMetric[];
}

const METRIC_LABEL: Record<string, string> = {
  campaign_roi: "Campaign ROI",
  cost_per_lead: "Cost per lead",
  revenue_attribution: "Revenue attribution",
};

/** Admin: revenue tracking — invoices, MRR/ARR rollups. See REVENUE_MODEL.md for targets. */
export function FinancialManagement() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [report, setReport] = useState<RevenueReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<Invoice[]>("/admin/invoices").catch(() => [] as Invoice[]),
      apiGet<RevenueReport>("/admin/revenue-report").catch(() => null),
    ])
      .then(([inv, rep]) => {
        setInvoices(inv);
        setReport(rep);
      })
      .finally(() => setLoading(false));
  }, []);

  const totalDue = invoices
    .filter((i) => i.status === "open")
    .reduce((sum, i) => sum + i.amount_due, 0);

  return (
    <div className="space-y-6">
      <div className="stagger grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div style={{ ["--i" as string]: 0 }}>
          <StatCard
            label="MRR"
            value={`$${(report?.revenue.mrr ?? 0).toFixed(2)}`}
            hint={`${report?.revenue.paying_accounts ?? 0} paying accounts`}
            tone="from-brand-400 to-brand-600"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 1 }}>
          <StatCard
            label="ARR"
            value={`$${(report?.revenue.arr ?? 0).toFixed(2)}`}
            hint="MRR × 12"
            tone="from-violet-400 to-violet-600"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 2 }}>
          <StatCard
            label="Generation cost"
            value={
              report?.generation_cost.priced
                ? `$${(report.generation_cost.estimated_cost_usd ?? 0).toFixed(4)}`
                : "—"
            }
            hint={`${(report?.generation_cost.total_tokens ?? 0).toLocaleString()} tokens`}
            tone="from-series-2 to-orange-600"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 3 }}>
          <StatCard
            label="Collected"
            value={`$${(report?.invoices.collected ?? 0).toFixed(2)}`}
            hint="Paid invoices"
            tone="from-series-3 to-emerald-700"
            loading={loading}
          />
        </div>
      </div>

      {report && (
        <Card>
          <CardHeader title="Growth insights" subtitle="From subscription and invoice activity" />
          <CardBody className="space-y-4">
            <ul className="space-y-2">
              {report.growth_insights.map((line, i) => (
                <li key={i} className="rounded-xl bg-brand-50 p-3 text-sm text-brand-900">
                  {line}
                </li>
              ))}
            </ul>

            {!report.generation_cost.priced && (
              <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-500">
                {report.generation_cost.note}
              </p>
            )}

            {report.unavailable.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">
                  Not available yet
                </h3>
                <ul className="space-y-2">
                  {report.unavailable.map((u) => (
                    <li key={u.metric} className="rounded-xl bg-slate-50 p-3 text-sm">
                      <p className="font-medium text-slate-700">
                        {METRIC_LABEL[u.metric] ?? u.metric}
                      </p>
                      <p className="mt-0.5 text-slate-500">{u.reason}</p>
                      <p className="mt-1 text-xs text-slate-400">Needs: {u.needs}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      <div className="stagger grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div style={{ ["--i" as string]: 0 }}>
          <StatCard
            label="Outstanding"
            value={`$${totalDue.toFixed(2)}`}
            hint="Open invoices"
            tone="from-status-warning to-amber-600"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 1 }}>
          <StatCard
            label="Invoices"
            value={invoices.length}
            tone="from-brand-400 to-brand-600"
            loading={loading}
          />
        </div>
      </div>

      <Card>
        <CardHeader
          title="Invoices"
          subtitle="Every invoice issued through Stripe"
          icon={<CardIcon className="h-5 w-5" />}
        />
        <CardBody className="p-0">
          {loading ? (
            <div className="space-y-2 p-5">
              <div className="skeleton h-10 w-full" />
              <div className="skeleton h-10 w-full" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/60 text-left">
                    <th className="px-6 py-3 font-semibold text-slate-500">Invoice</th>
                    <th className="px-6 py-3 font-semibold text-slate-500">Amount</th>
                    <th className="px-6 py-3 font-semibold text-slate-500">Status</th>
                    <th className="px-6 py-3 font-semibold text-slate-500">Issued</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr
                      key={inv.id}
                      className="border-b border-slate-50 transition-colors last:border-0 hover:bg-brand-50/40"
                    >
                      <td className="px-6 py-3.5 font-mono text-xs text-slate-500">
                        {inv.id.slice(0, 8)}
                      </td>
                      <td className="px-6 py-3.5 font-semibold tabular-nums text-slate-900">
                        {inv.amount_due.toFixed(2)} {inv.currency.toUpperCase()}
                      </td>
                      <td className="px-6 py-3.5">
                        <Badge tone={inv.status}>{inv.status}</Badge>
                      </td>
                      <td className="px-6 py-3.5 text-slate-600">
                        {new Date(inv.issued_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                  {invoices.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-6 py-12 text-center text-sm text-slate-400">
                        No invoices yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
