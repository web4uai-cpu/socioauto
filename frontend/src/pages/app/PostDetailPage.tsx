import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPatch, apiPost, API_ORIGIN } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Input, Textarea } from "../../components/ui/Input";
import { PostStatusBadge } from "../../components/PostStatusBadge";
import type { Campaign, ContentItem } from "../../types/content";

export function PostDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    if (!id) return;
    apiGet<Campaign>(`/campaigns/${id}`)
      .then(setCampaign)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(load, [id]);

  async function act(path: string) {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/campaigns/${id}/${path}`);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !campaign) {
    return (
      <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {error}
      </p>
    );
  }
  if (!campaign) {
    return (
      <Card>
        <CardBody className="space-y-3">
          <div className="skeleton h-6 w-40" />
          <div className="skeleton h-24 w-full" />
        </CardBody>
      </Card>
    );
  }

  const anyApproved = campaign.calendar.some((item) => item.status === "approved");
  const anyRejected = campaign.calendar.some((item) => item.status === "rejected");

  return (
    <div className="space-y-5">
      <button
        type="button"
        onClick={() => navigate("/app/posts")}
        className="text-sm font-medium text-slate-500 transition-colors hover:text-brand-600"
      >
        ← Back to my posts
      </button>

      {error && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="stagger grid gap-5 lg:grid-cols-2">
        {campaign.calendar.map((item, i) => (
          <div key={i} style={{ ["--i" as string]: i }}>
            <PostCard
              item={item}
              index={i}
              campaignId={campaign.id}
              onChanged={load}
              disabled={busy}
            />
          </div>
        ))}
      </div>

      <div className="flex flex-wrap justify-end gap-3">
        {anyRejected && (
          <Button variant="secondary" onClick={() => navigate("/app/compose")}>
            Edit & resubmit
          </Button>
        )}
        {anyApproved && (
          <>
            <Button variant="secondary" onClick={() => act("schedule")} disabled={busy}>
              Schedule for later
            </Button>
            <Button onClick={() => act("approve")} loading={busy}>
              Publish now
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  text: "Text only",
  image: "Image",
  video: "Video",
  audio: "Audio only",
  faceless_video: "Faceless video",
};

/** Collapsible block for one agent's output — collapsed by default to keep the card scannable. */
function Detail({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: (string | null | undefined)[];
  children: React.ReactNode;
}) {
  const parts = (meta ?? []).filter(Boolean);
  return (
    <details className="group rounded-xl border border-slate-200 open:bg-slate-50/60">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2.5 text-sm font-medium text-slate-700">
        <span className="flex items-center gap-2">
          {title}
          {parts.length > 0 && (
            <span className="text-xs font-normal text-slate-400">{parts.join(" · ")}</span>
          )}
        </span>
        <span className="text-slate-400 transition-transform duration-200 group-open:rotate-90">
          ›
        </span>
      </summary>
      <div className="border-t border-slate-200 px-3 py-2.5 text-sm text-slate-600">
        {children}
      </div>
    </details>
  );
}

interface PostCardProps {
  item: ContentItem;
  index: number;
  campaignId: string;
  onChanged: () => void;
  disabled: boolean;
}

function PostCard({ item, index, campaignId, onChanged, disabled }: PostCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.body);
  const [feedback, setFeedback] = useState("");
  const [working, setWorking] = useState<null | "save" | "regen">(null);
  const [error, setError] = useState<string | null>(null);
  const published = item.status === "published";

  async function save() {
    setWorking("save");
    setError(null);
    try {
      await apiPatch(`/campaigns/${campaignId}/items/${index}`, { body: draft });
      setEditing(false);
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setWorking(null);
    }
  }

  async function regenerate() {
    setWorking("regen");
    setError(null);
    try {
      await apiPost(`/campaigns/${campaignId}/regenerate`, {
        item_index: index,
        feedback: feedback || null,
      });
      setFeedback("");
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setWorking(null);
    }
  }

  return (
    <Card className="h-full">
      <CardHeader
        title={<span className="capitalize">{item.platform}</span>}
        subtitle={KIND_LABEL[item.kind] ?? item.kind}
        action={<PostStatusBadge status={item.status} />}
      />
      <CardBody className="space-y-4">
        {editing ? (
          <div className="space-y-2">
            <Textarea rows={6} value={draft} onChange={(e) => setDraft(e.target.value)} />
            <p className="text-xs text-slate-400">
              Editing re-runs the safety review, so the status may change when you save.
            </p>
            <div className="flex gap-2">
              <Button size="sm" onClick={save} loading={working === "save"}>
                Save & re-review
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setDraft(item.body);
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{item.body}</p>
        )}

        {item.thread?.length > 0 && (
          <div className="space-y-2 border-l-2 border-brand-200 pl-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
              Thread · {item.thread.length + 1} posts
            </p>
            {item.thread.map((part, i) => (
              <p key={i} className="whitespace-pre-wrap text-sm leading-relaxed text-slate-600">
                {part}
              </p>
            ))}
          </div>
        )}

        {item.media.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {item.media.map((m) => (
              <div key={m.id} className="overflow-hidden rounded-xl ring-1 ring-slate-200">
                {m.kind === "image" && (
                  <img src={`${API_ORIGIN}${m.url}`} alt="" className="h-28 w-full object-cover" />
                )}
                {m.kind === "audio" && (
                  <div className="flex h-28 items-center bg-slate-50 px-2">
                    <audio src={`${API_ORIGIN}${m.url}`} controls className="w-full" />
                  </div>
                )}
                {m.kind === "video" && (
                  <video
                    src={`${API_ORIGIN}${m.url}`}
                    controls
                    className="h-28 w-full bg-slate-900 object-cover"
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {item.hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {item.hashtags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}

        {/* What the generation agents produced for this item. */}
        {item.audio?.script && (
          <Detail
            title="Voiceover"
            meta={[
              item.audio.audio_type?.replace(/_/g, " "),
              item.audio.estimated_seconds ? `~${item.audio.estimated_seconds}s` : null,
              item.audio.voice?.style,
            ]}
          >
            <p className="whitespace-pre-wrap">{item.audio.script}</p>
            {item.audio.music_bed && (
              <p className="mt-2 text-slate-500">Music: {item.audio.music_bed}</p>
            )}
          </Detail>
        )}

        {item.video?.scenes?.length ? (
          <Detail
            title="Video script"
            meta={[
              item.video.target_seconds ? `~${item.video.target_seconds}s` : null,
              item.video.faceless ? "faceless" : null,
            ]}
          >
            {item.video.hook && <p className="mb-2 font-medium">Hook: {item.video.hook}</p>}
            <ol className="space-y-1.5">
              {item.video.scenes.map((scene, i) => (
                <li key={i} className="flex gap-2">
                  <span className="shrink-0 tabular-nums text-slate-400">{scene.seconds}s</span>
                  <span>
                    {scene.narration}
                    <span className="block text-slate-400">{scene.visual}</span>
                  </span>
                </li>
              ))}
            </ol>
          </Detail>
        ) : null}

        {item.visual?.prompt && (
          <Detail
            title="Visual"
            meta={[item.visual.purpose, item.visual.aspect_ratio, item.visual.size]}
          >
            <p>{item.visual.prompt}</p>
            {item.visual.alt_text && (
              <p className="mt-2 text-slate-500">Alt text: {item.visual.alt_text}</p>
            )}
          </Detail>
        )}

        {item.seo?.primary_keyword && (
          <Detail
            title="SEO"
            meta={[
              typeof item.seo.score === "number" ? `score ${item.seo.score}/100` : null,
              item.seo.readability_label,
            ]}
          >
            {typeof item.seo.score === "number" && (
              <div className="mb-3">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      item.seo.score >= 80
                        ? "bg-status-good"
                        : item.seo.score >= 50
                          ? "bg-status-warning"
                          : "bg-status-critical"
                    }`}
                    style={{ width: `${item.seo.score}%` }}
                  />
                </div>
              </div>
            )}
            <p>
              <span className="text-slate-400">Keyword:</span> {item.seo.primary_keyword}
            </p>
            {item.seo.keywords?.length ? (
              <p className="mt-1 text-slate-500">{item.seo.keywords.join(" · ")}</p>
            ) : null}
            {item.seo.suggestions?.length ? (
              <ul className="mt-2 space-y-1">
                {item.seo.suggestions.map((s, i) => (
                  <li key={i} className="flex gap-2 text-amber-700">
                    <span aria-hidden>→</span>
                    {s}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-emerald-700">All checks passed.</p>
            )}
            {item.seo.lead_magnet && (
              <p className="mt-2 text-slate-500">Lead capture: {item.seo.lead_magnet}</p>
            )}
          </Detail>
        )}

        {item.status === "rejected" && item.moderation_reasons.length > 0 && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <p className="font-semibold">Rejected by brand-safety review</p>
            <p className="mt-1">{item.moderation_reasons.join(", ")}</p>
          </div>
        )}

        {(item.scheduled_at || item.published_at) && (
          <p className="border-t border-slate-100 pt-3 text-xs text-slate-400">
            {item.published_at
              ? `Published ${new Date(item.published_at).toLocaleString()}`
              : `Scheduled for ${new Date(item.scheduled_at!).toLocaleString()}`}
          </p>
        )}

        {error && (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-2 text-sm text-red-700">
            {error}
          </p>
        )}

        {/* Reviewer actions. Published posts are final — neither edit nor regenerate applies. */}
        {!published && !editing && (
          <div className="space-y-2 border-t border-slate-100 pt-3">
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)} disabled={disabled}>
                Edit
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={regenerate}
                loading={working === "regen"}
                disabled={disabled}
              >
                Regenerate
              </Button>
            </div>
            <Input
              placeholder="Optional: what should change when regenerating?"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
          </div>
        )}
      </CardBody>
    </Card>
  );
}
