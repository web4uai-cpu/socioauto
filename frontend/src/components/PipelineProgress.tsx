import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { SparkleIcon } from "./ui/Icon";
import type { CampaignProgress } from "../types/content";

const POLL_MS = 800;
/** Stop polling eventually so a stuck run cannot poll forever. */
const TIMEOUT_MS = 3 * 60 * 1000;

interface PipelineProgressProps {
  campaignId: string;
  onComplete: (campaignId: string) => void;
  onRetry: () => void;
}

/** Live per-agent progress for a generating campaign, polled from the API. */
export function PipelineProgress({ campaignId, onComplete, onRetry }: PipelineProgressProps) {
  const [progress, setProgress] = useState<CampaignProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function poll() {
      if (cancelled) return;
      try {
        const next = await apiGet<CampaignProgress>(`/campaigns/${campaignId}/progress`);
        if (cancelled) return;
        setProgress(next);

        if (next.status === "complete") {
          onComplete(campaignId);
          return;
        }
        if (next.status === "error") {
          setError(next.error ?? "Generation failed.");
          return;
        }
        if (Date.now() - startedAt.current > TIMEOUT_MS) {
          setError("This is taking longer than expected. Check My posts in a moment.");
          return;
        }
        timer = window.setTimeout(poll, POLL_MS);
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [campaignId, onComplete]);

  const stages = progress?.stages ?? [];
  const completed = new Set(progress?.completed ?? []);
  const percent = progress?.percent ?? 0;

  return (
    <Card accent="from-brand-400 via-series-3 to-series-2">
      <CardHeader
        title="Creating your post"
        subtitle={
          error
            ? "Something went wrong"
            : progress?.current_label
              ? `${progress.current_label}…`
              : "Starting the agents…"
        }
        icon={<SparkleIcon className="h-5 w-5" />}
      />
      <CardBody className="space-y-6">
        {/* Overall bar */}
        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-sm font-medium text-slate-600">
              {completed.size} of {stages.length || "…"} steps
            </span>
            <span className="text-sm font-semibold tabular-nums text-brand-700">{percent}%</span>
          </div>
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-slate-100"
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600 transition-all duration-500 ease-out"
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>

        {/* Per-agent stepper */}
        <ol className="space-y-1">
          {stages.map((stage) => {
            const done = completed.has(stage.name);
            const active = !done && progress?.current_agent === stage.name;
            const running = !done && !active;
            return (
              <li
                key={stage.name}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-300 ${
                  active ? "bg-brand-50" : ""
                }`}
              >
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all duration-300 ${
                    done
                      ? "bg-status-good text-white"
                      : active
                        ? "bg-brand-600 text-white"
                        : "bg-slate-200 text-slate-400"
                  }`}
                >
                  {done ? (
                    "✓"
                  ) : active ? (
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    ""
                  )}
                </span>
                <span
                  className={`text-sm transition-colors duration-300 ${
                    done
                      ? "text-slate-500"
                      : active
                        ? "font-semibold text-brand-800"
                        : "text-slate-400"
                  }`}
                >
                  {stage.label}
                </span>
                {running && <span className="sr-only">pending</span>}
              </li>
            );
          })}
          {stages.length === 0 && !error && (
            <li className="skeleton h-10 w-full" aria-hidden />
          )}
        </ol>

        {error && (
          <div className="space-y-3">
            <p
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              {error}
            </p>
            <Button variant="secondary" onClick={onRetry}>
              Back to composer
            </Button>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
