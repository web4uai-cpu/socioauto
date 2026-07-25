import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { SparkleIcon } from "./ui/Icon";

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

const TIER_TONE: Record<Subscription["tier"], string> = {
  free: "from-slate-400 to-slate-600",
  starter: "from-brand-300 to-brand-500",
  pro: "from-brand-400 to-brand-600",
  agency: "from-violet-400 to-violet-600",
  enterprise: "from-series-2 to-orange-600",
};

/** Admin: view/manage a brand's subscription tier and Stripe billing status. */
export function SubscriptionManagement() {
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Subscription[]>("/admin/subscriptions")
      .then(setSubs)
      .catch(() => setSubs([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card>
      <CardHeader
        title="Subscriptions"
        subtitle="Active plans and their billing state"
        icon={<SparkleIcon className="h-5 w-5" />}
      />
      <CardBody className="space-y-3">
        {loading && <div className="skeleton h-16 w-full" />}

        {!loading &&
          subs.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 p-4
                transition-all duration-200 hover:border-brand-200 hover:shadow-card"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br
                    ${TIER_TONE[s.tier]} text-xs font-bold uppercase text-white`}
                >
                  {s.tier.slice(0, 2)}
                </span>
                <div>
                  <p className="font-semibold capitalize text-slate-900">{s.tier}</p>
                  <p className="text-xs text-slate-500">{TIER_PRICE[s.tier]} / month</p>
                </div>
              </div>
              <div className="text-right">
                <Badge tone={s.status}>{s.status.replace(/_/g, " ")}</Badge>
                {s.current_period_end && (
                  <p className="mt-1 text-xs text-slate-400">
                    Renews {new Date(s.current_period_end).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
          ))}

        {!loading && subs.length === 0 && (
          <p className="py-10 text-center text-sm text-slate-400">No subscriptions yet</p>
        )}
      </CardBody>
    </Card>
  );
}
