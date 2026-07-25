import { useState } from "react";
import { apiPost } from "../api/client";
import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Input, Textarea } from "./ui/Input";
import { MediaUploader, type MediaRef } from "./MediaUploader";

const PLATFORMS = ["instagram", "x", "linkedin", "facebook", "tiktok"];

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
  const [body, setBody] = useState("");
  const [cta, setCta] = useState("");
  const [media, setMedia] = useState<MediaRef[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      const campaign =
        mode === "manual"
          ? await apiPost<CampaignResponse>("/campaigns/manual", {
              platforms,
              body,
              cta: cta || null,
              media,
            })
          : await apiPost<CampaignResponse>("/campaigns", { prompt: body, platforms });
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

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">New post</h2>
        <div className="flex overflow-hidden rounded-lg border border-gray-300 text-sm">
          <button
            type="button"
            onClick={() => setMode("manual")}
            className={`px-3 py-1.5 ${mode === "manual" ? "bg-brand-600 text-white" : "bg-white text-gray-600"}`}
          >
            Write it myself
          </button>
          <button
            type="button"
            onClick={() => setMode("ai")}
            className={`px-3 py-1.5 ${mode === "ai" ? "bg-brand-600 text-white" : "bg-white text-gray-600"}`}
          >
            Generate with AI
          </button>
        </div>
      </CardHeader>

      <CardBody className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((platform) => (
            <button
              key={platform}
              type="button"
              onClick={() => togglePlatform(platform)}
              className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
                platforms.includes(platform)
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-gray-300 text-gray-500"
              }`}
            >
              {platform}
            </button>
          ))}
        </div>

        <Textarea
          rows={4}
          placeholder={mode === "manual" ? "What do you want to post?" : "Describe what to post about…"}
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />

        {mode === "manual" && (
          <>
            <Input placeholder="Call to action (optional)" value={cta} onChange={(e) => setCta(e.target.value)} />
            <MediaUploader media={media} onChange={setMedia} />
          </>
        )}

        {error && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <div className="flex justify-end">
          <Button onClick={submit} disabled={busy}>
            {busy ? "Submitting…" : mode === "manual" ? "Submit for review" : "Generate & review"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
