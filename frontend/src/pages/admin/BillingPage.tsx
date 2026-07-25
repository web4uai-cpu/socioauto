import { FinancialManagement } from "../../components/FinancialManagement";
import { SubscriptionManagement } from "../../components/SubscriptionManagement";

export function BillingPage() {
  return (
    <div className="space-y-6">
      <SubscriptionManagement />
      <FinancialManagement />
    </div>
  );
}
