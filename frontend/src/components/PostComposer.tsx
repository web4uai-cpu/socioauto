import { useState } from "react";
import { apiPost } from "../api/client";
import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Field, Input, Textarea } from "./ui/Input";
import { MediaUploader, type MediaRef } from "./MediaUploader";
import { PipelineProgress } from "./PipelineProgress";
import { PenIcon, SparkleIcon } from "./ui/Icon";
import type { PostKind } from "../types/content";

const PLATFORMS = [
  { id: "instagram", label: "Instagram", tone: "from-pink-500 to-orange-400" },
  { id: "x", label: "X", tone: "from-slate-700 to-slate-900" },
  { id: "linkedin", label: "LinkedIn", tone: "from-brand-500 to-brand-700" },
  { id: "facebook", label: "Facebook", tone: "from-brand-400 to-brand-600" },
  { id: "tiktok", label: "TikTok", tone: "from-teal-400 to-slate-800" },
  { id: "youtube", label: "YouTube", tone: "from-red-500 to-red-700" },
  { id: "youtube_shorts", label: "YouTube Shorts", tone: "from-rose-400 to-red-600" },
];

/** What gets generated for each kind — mirrors the agent gating in the backend. */
const POST_KINDS: { id: PostKind | ""; label: string; icon: string; hint: string }[] = [
  { id: "", label: "Auto", icon: "✨", hint: "Let the agents pick per platform" },
  { id: "text", label: "Text only", icon: "✍️", hint: "Just copy — no media" },
  { id: "image", label: "Image", icon: "🖼️", hint: "Copy plus an image" },
  { id: "audio", label: "Audio only", icon: "🎙️", hint: "Voiceover and cover art — no video" },
  { id: "video", label: "Video", icon: "🎬", hint: "Script, thumbnail and voiceover" },
  {
    id: "faceless_video",
    label: "Faceless video",
    icon: "🥷",
    hint: "B-roll and voiceover — nobody on camera",
  },
];

const MAX_BODY = 4000;

interface CampaignResponse {
  id: string;
  status: string;
}

interface PostComposerProps {
  onCreated: (campaign: CampaignResponse) => void;
}

/** Compose a post: write it yourself and attach media, or have the AI generate it from a prompt. */
export function PostComposer({ onCreated }: PostComposerProps) {
  const [mode, setMode] = useState<"manual" | "ai">("manual");
  const [platforms, setPlatforms] = useState<string[]>(["instagram"]);
  const [postKind, setPostKind] = useState<PostKind | "">("");
  const [body, setBody] = useState("");
  const [cta, setCta] = useState("");
  const [media, setMedia] = useState<MediaRef[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Set once an AI run is generating in the background; swaps the form for the progress view. */
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  function togglePlatform(platform: string) {
    setPlatforms((prev) =>
      prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform],
    );
  }

  async function submit() {
    if (platforms.length === 0 || !body.trim()) {
      setError("Pick at least one platform and write something to post.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (mode === "ai") {
        // The AI pipeline is slow, so run it in the background and show live progress.
        const started = await apiPost<{ campaign_id: string }>("/campaigns/start", {
          prompt: body,
          platforms,
          post_kind: postKind,
        });
        setGeneratingId(started.campaign_id);
        return;
      }
      const campaign = await apiPost<CampaignResponse>("/campaigns/manual", {
        platforms,
        body,
        cta: cta || null,
        media,
        post_kind: postKind,
      });
      setBody("");
      setCta("");
      setMedia([]);
      onCreated(campaign);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (generatingId) {
    return (
      <PipelineProgress
        campaignId={generatingId}
        onComplete={(id) => onCreated({ id, status: "pending_review" })}
        onRetry={() => setGeneratingId(null)}
      />
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card accent="from-brand-400 via-series-3 to-series-2">
        <CardHeader
          title="Create a post"
          subtitle="Everything goes through brand-safety review before it publishes"
          icon={mode === "manual" ? <PenIcon className="h-5 w-5" /> : <SparkleIcon className="h-5 w-5" />}
          action={
            <div className="flex rounded-xl bg-slate-100 p-1">
              {(["manual", "ai"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-200 ${
                    mode === m
                      ? "bg-white text-brand-700 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {m === "manual" ? "Write it myself" : "Generate with AI"}
                </button>
              ))}
            </div>
          }
        />

        <CardBody className="space-y-6">
          <Field label="Platforms" hint="Each selected platform gets its own reviewed post.">
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map((platform) => {
                const on = platforms.includes(platform.id);
                return (
                  <button
                    key={platform.id}
                    type="button"
                    onClick={() => togglePlatform(platform.id)}
                    className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium
                      transition-all duration-200 hover:-translate-y-0.5 active:scale-95 ${
                        on
                          ? "bg-brand-50 text-brand-700 ring-2 ring-inset ring-brand-500"
                          : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:ring-slate-300"
                      }`}
                  >
                    <span
                      className={`h-2.5 w-2.5 rounded-full bg-gradient-to-br ${platform.tone} ${
                        on ? "" : "opacity-40"
                      }`}
                    />
                    {platform.label}
                  </button>
                );
              })}
            </div>
          </Field>

          <Field
            label="Kind of post"
            hint={POST_KINDS.find((k) => k.id === postKind)?.hint}
          >
            <div className="flex flex-wrap gap-2">
              {POST_KINDS.map((kind) => {
                const on = postKind === kind.id;
                return (
                  <button
                    key={kind.id || "auto"}
                    type="button"
                    onClick={() => setPostKind(kind.id)}
                    aria-pressed={on}
                    className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium
                      transition-all duration-200 hover:-translate-y-0.5 active:scale-95 ${
                        on
                          ? "bg-brand-50 text-brand-700 ring-2 ring-inset ring-brand-500"
                          : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:ring-slate-300"
                      }`}
                  >
                    <span aria-hidden>{kind.icon}</span>
                    {kind.label}
                  </button>
                );
              })}
            </div>
          </Field>

          <Field
            label={mode === "manual" ? "Your post" : "What should it be about?"}
            htmlFor="composer-body"
            action={
              <span
                className={`text-xs tabular-nums ${
                  body.length > MAX_BODY ? "text-status-critical" : "text-slate-400"
                }`}
              >
                {body.length}/{MAX_BODY}
              </span>
            }
          >
            <Textarea
              id="composer-body"
              rows={7}
              maxLength={MAX_BODY}
              placeholder={
                mode === "manual"
                  ? "Share what's new…"
                  : "e.g. Announce our new AI feature to enterprise buyers"
              }
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </Field>

          {mode === "manual" && (
            <>
              <Field label="Call to action" htmlFor="composer-cta" hint="Optional.">
                <Input
                  id="composer-cta"
                  placeholder="e.g. Book a demo"
                  value={cta}
                  onChange={(e) => setCta(e.target.value)}
                />
              </Field>

              <Field label="Media" hint="Photo, audio, or video — attach as many as you need.">
                <MediaUploader media={media} onChange={setMedia} />
              </Field>
            </>
          )}

          {error && (
            <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
            <Button
              size="lg"
              onClick={submit}
              loading={busy}
              icon={mode === "ai" ? <SparkleIcon className="h-4 w-4" /> : undefined}
            >
              {mode === "manual" ? "Submit for review" : "Generate & review"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Live preview */}
      <div className="xl:sticky xl:top-24 xl:self-start">
        <Card>
          <CardHeader title="Preview" subtitle="Roughly how it will read" />
          <CardBody>
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-sm font-semibold text-white">
                  A
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-900">Your brand</p>
                  <p className="text-xs text-slate-400">
                    {platforms.length > 0 ? platforms.join(" · ") : "No platform selected"}
                  </p>
                </div>
              </div>

              <p className="mt-3 whitespace-pre-wrap break-words text-sm text-slate-700">
                {body || (
                  <span className="text-slate-400">Your post text will appear here…</span>
                )}
              </p>

              {cta && (
                <p className="mt-3 inline-block rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white">
                  {cta}
                </p>
              )}

              {media.length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {media.slice(0, 4).map((m) => (
                    <div
                      key={m.id}
                      className="flex h-16 items-center justify-center rounded-lg bg-slate-200 text-[11px]
                        font-medium uppercase tracking-wide text-slate-500"
                    >
                      {m.kind}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
