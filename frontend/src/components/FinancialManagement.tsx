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

/** Admin: revenue tracking — invoices, MRR/ARR rollups. See REVENUE_MODEL.md for targets. */
export function FinancialManagement() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Invoice[]>("/admin/invoices")
      .then(setInvoices)
      .catch(() => setInvoices([]))
      .finally(() => setLoading(false));
  }, []);

  const totalDue = invoices
    .filter((i) => i.status === "open")
    .reduce((sum, i) => sum + i.amount_due, 0);
  const collected = invoices
    .filter((i) => i.status === "paid")
    .reduce((sum, i) => sum + i.amount_due, 0);

  return (
    <div className="space-y-6">
      <div className="stagger grid grid-cols-1 gap-4 sm:grid-cols-3">
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
            label="Collected"
            value={`$${collected.toFixed(2)}`}
            hint="Paid invoices"
            tone="from-series-3 to-emerald-700"
            loading={loading}
          />
        </div>
        <div style={{ ["--i" as string]: 2 }}>
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
