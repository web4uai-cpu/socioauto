import { useEffect, useState } from "react";
import { apiGet } from "../api/client";

interface Subscription {
  id: string;
  tier: "free" | "starter" | "pro" | "agency" | "enterprise";
  status: "active" | "past_due" | "canceled" | "trialing";
  current_period_end: string | null;
}

const TIER_PRICE: Record<Subscription["tier"], string> = {
  free: "$0",
  starter: "$49",
  pro: "$149",
  agency: "$499",
  enterprise: "Custom",
};

/** Admin: view/manage a brand's subscription tier and Stripe billing status. */
export function SubscriptionManagement() {
  const [subs, setSubs] = useState<Subscription[]>([]);

  useEffect(() => {
    apiGet<Subscription[]>("/admin/subscriptions").then(setSubs).catch(() => setSubs([]));
  }, []);

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <h2 className="text-lg font-semibold mb-3">Subscription Management</h2>
      <ul className="divide-y divide-gray-100">
        {subs.map((s) => (
          <li key={s.id} className="py-2 flex justify-between text-sm">
            <span className="capitalize">{s.tier} — {TIER_PRICE[s.tier]}/mo</span>
            <span className="capitalize text-gray-500">{s.status}</span>
          </li>
        ))}
        {subs.length === 0 && <li className="py-4 text-center text-gray-400">No subscriptions</li>}
      </ul>
    </div>
  );
}
