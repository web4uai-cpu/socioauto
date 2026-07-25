import { Badge } from "./ui/Badge";

const LABELS: Record<string, string> = {
  draft: "Draft",
  pending_moderation: "In review",
  approved: "Approved",
  rejected: "Rejected",
  scheduled: "Scheduled",
  published: "Published",
  failed: "Failed",
};

export function PostStatusBadge({ status }: { status: string }) {
  return <Badge tone={status}>{LABELS[status] ?? status}</Badge>;
}
