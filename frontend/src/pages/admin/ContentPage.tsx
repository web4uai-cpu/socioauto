import { CampaignReviewQueue } from "../../components/CampaignReviewQueue";
import { ContentCalendar } from "../../components/ContentCalendar";

export function ContentPage() {
  return (
    <div className="space-y-6">
      <ContentCalendar />
      <CampaignReviewQueue />
    </div>
  );
}
