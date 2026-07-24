import { AnalyticsBoard } from "../components/AnalyticsBoard";
import { CampaignReviewQueue } from "../components/CampaignReviewQueue";
import { FinancialManagement } from "../components/FinancialManagement";
import { SubscriptionManagement } from "../components/SubscriptionManagement";
import { UserManagementTable } from "../components/UserManagementTable";

/** Top-level admin dashboard composing all management panels. */
export function AdminDashboard() {
  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">SocialMediaAI — Admin Dashboard</h1>
      <AnalyticsBoard />
      <CampaignReviewQueue />
      <UserManagementTable />
      <SubscriptionManagement />
      <FinancialManagement />
    </div>
  );
}
