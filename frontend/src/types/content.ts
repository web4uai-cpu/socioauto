import type { MediaRef } from "../components/MediaUploader";

/** What medium a post is. Decides which generation agents run for it. */
export type PostKind = "text" | "image" | "video" | "audio" | "faceless_video";

/** Visual Agent output: an image generation spec, not a rendered file. */
export interface VisualSpec {
  prompt?: string;
  alt_text?: string;
  overlay_text?: string;
  style?: string;
  aspect_ratio?: string;
  size?: string;
  purpose?: string;
  status?: string;
}

export interface VideoScene {
  narration: string;
  visual: string;
  seconds: number;
}

/** Video Agent output: a script and thumbnail spec. */
export interface VideoSpec {
  hook?: string;
  scenes?: VideoScene[];
  call_to_action?: string;
  thumbnail_prompt?: string;
  thumbnail_text?: string;
  target_seconds?: number;
  faceless?: boolean;
  status?: string;
}

/** Audio Agent output: a voiceover script and voice spec. */
export interface AudioSpec {
  script?: string;
  transcript?: string;
  hook_line?: string;
  audio_type?: string;
  estimated_seconds?: number;
  music_bed?: string;
  voice?: { style?: string; pace?: string; words_per_minute?: number };
  status?: string;
}

/** SEO Agent output, including the locally-computed readability and on-page score. */
export interface SeoSpec {
  primary_keyword?: string;
  keywords?: string[];
  meta_description?: string;
  slug?: string;
  lead_magnet?: string;
  lead_form_fields?: string[];
  lead_cta?: string;
  /** Flesch Reading Ease, 0-100 (higher is easier). */
  readability?: number;
  readability_label?: string;
  /** Heuristic 0-100 across five checks — a drafting aid, not a ranking prediction. */
  score?: number;
  passed_checks?: string[];
  suggestions?: string[];
}

export interface ContentItem {
  platform: string;
  topic: string;
  body: string;
  status: string;
  kind: PostKind;
  goal: string;
  /** Follow-up parts on threaded platforms; empty for a single post. */
  thread: string[];
  hashtags: string[];
  media: MediaRef[];
  visual: VisualSpec;
  video: VideoSpec;
  audio: AudioSpec;
  seo: SeoSpec;
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

/** One stage of the generation pipeline, as reported by the progress endpoint. */
export interface PipelineStage {
  name: string;
  label: string;
}

export interface CampaignProgress {
  campaign_id: string;
  status: "running" | "complete" | "error";
  current_agent: string | null;
  current_label: string | null;
  completed: string[];
  stages: PipelineStage[];
  total: number;
  percent: number;
  error: string | null;
}
