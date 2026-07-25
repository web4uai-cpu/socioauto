import { Link } from "react-router-dom";
import { Card, CardBody } from "./ui/Card";
import { PostStatusBadge } from "./PostStatusBadge";
import { StackIcon } from "./ui/Icon";
import type { Campaign } from "../types/content";

export function PostList({ campaigns }: { campaigns: Campaign[] }) {
  if (campaigns.length === 0) {
    return (
      <Card>
        <CardBody className="py-16 text-center">
          <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-500">
            <StackIcon className="h-6 w-6" />
          </span>
          <p className="text-sm font-semibold text-slate-700">No posts yet</p>
          <p className="mt-1 text-sm text-slate-400">
            Head to Compose to create your first one.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="stagger grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
      {campaigns.map((campaign, i) => {
        const statuses = [...new Set(campaign.calendar.map((item) => item.status))];
        const mediaCount = campaign.calendar.reduce((n, item) => n + item.media.length, 0);
        return (
          <div key={campaign.id} style={{ ["--i" as string]: i }}>
            <Link to={`/app/posts/${campaign.id}`} className="block h-full">
              <Card interactive className="h-full">
                <CardBody className="flex h-full flex-col gap-3">
                  <p className="line-clamp-2 text-sm font-semibold leading-relaxed text-slate-900">
                    {campaign.prompt}
                  </p>

                  <div className="mt-auto flex flex-wrap items-center gap-1.5">
                    {statuses.map((status) => (
                      <PostStatusBadge key={status} status={status} />
                    ))}
                  </div>

                  <div className="flex items-center gap-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
                    <span className="capitalize">{campaign.platforms.join(", ")}</span>
                    <span>·</span>
                    <span>
                      {campaign.calendar.length} item{campaign.calendar.length === 1 ? "" : "s"}
                    </span>
                    {mediaCount > 0 && (
                      <>
                        <span>·</span>
                        <span>
                          {mediaCount} media file{mediaCount === 1 ? "" : "s"}
                        </span>
                      </>
                    )}
                  </div>
                </CardBody>
              </Card>
            </Link>
          </div>
        );
      })}
    </div>
  );
}
