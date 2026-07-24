import { useEffect, useState } from "react";
import { apiGet } from "../api/client";

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

  useEffect(() => {
    apiGet<Invoice[]>("/admin/invoices").then(setInvoices).catch(() => setInvoices([]));
  }, []);

  const totalDue = invoices
    .filter((i) => i.status === "open")
    .reduce((sum, i) => sum + i.amount_due, 0);

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <h2 className="text-lg font-semibold mb-3">Financial Management</h2>
      <p className="text-sm text-gray-600 mb-3">Outstanding balance: ${totalDue.toFixed(2)}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b border-gray-200">
            <th className="py-2">Invoice</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Issued</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr key={inv.id} className="border-b border-gray-100">
              <td className="py-2">{inv.id.slice(0, 8)}</td>
              <td>
                {inv.amount_due.toFixed(2)} {inv.currency.toUpperCase()}
              </td>
              <td className="capitalize">{inv.status}</td>
              <td>{new Date(inv.issued_at).toLocaleDateString()}</td>
            </tr>
          ))}
          {invoices.length === 0 && (
            <tr>
              <td colSpan={4} className="py-4 text-center text-gray-400">
                No invoices
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
