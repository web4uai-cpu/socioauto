import type { MediaRef } from "../components/MediaUploader";

export interface ContentItem {
  platform: string;
  topic: string;
  body: string;
  status: string;
  media: MediaRef[];
  moderation_reasons: string[];
  scheduled_at: string | null;
  published_at: string | null;
  external_post_id: string | null;
}

export interface Campaign {
  id: string;
  prompt: string;
  platforms: string[];
  tone: string;
  cta: string | null;
  target_audience: string | null;
  status: string;
  calendar: ContentItem[];
}
