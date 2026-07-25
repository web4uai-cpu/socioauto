import { Link } from "react-router-dom";
import { Card, CardBody } from "./ui/Card";
import { PostStatusBadge } from "./PostStatusBadge";
import type { Campaign } from "../types/content";

export function PostList({ campaigns }: { campaigns: Campaign[] }) {
  if (campaigns.length === 0) {
    return (
      <Card>
        <CardBody className="py-10 text-center text-sm text-gray-500">
          You haven't created any posts yet.
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {campaigns.map((campaign) => (
        <Link key={campaign.id} to={`/app/posts/${campaign.id}`}>
          <Card className="transition-shadow hover:shadow-md">
            <CardBody className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900">{campaign.prompt}</p>
                <p className="mt-1 text-xs text-gray-500">
                  {campaign.platforms.join(", ")} · {campaign.calendar.length} item
                  {campaign.calendar.length === 1 ? "" : "s"}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap justify-end gap-1">
                {[...new Set(campaign.calendar.map((item) => item.status))].map((status) => (
                  <PostStatusBadge key={status} status={status} />
                ))}
              </div>
            </CardBody>
          </Card>
        </Link>
      ))}
    </div>
  );
}
