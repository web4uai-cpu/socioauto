import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPut } from "../api/client";
import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Field, Input, Select } from "./ui/Input";
import { PlugIcon } from "./ui/Icon";

/** One dashboard-editable setting, as described by GET /admin/settings. */
interface Setting {
  key: string;
  label: string;
  group: string;
  is_secret: boolean;
  help_text: string;
  choices: string[];
  source: "database" | "environment" | "unset";
  configured: boolean;
  /** Plain value for non-secrets; a masked preview for secrets. */
  value: string;
}

const GROUP_LABELS: Record<string, string> = {
  ai: "AI provider",
  billing: "Billing (Stripe)",
  platforms: "Social platforms",
  general: "URLs",
};

const GROUP_ACCENTS: Record<string, string> = {
  ai: "from-brand-400 to-brand-600",
  billing: "from-series-3 to-emerald-700",
  platforms: "from-series-2 to-orange-600",
  general: "from-violet-400 to-violet-600",
};

const GROUP_ORDER = ["ai", "billing", "platforms", "general"];

function SourceBadge({ setting }: { setting: Setting }) {
  const styles: Record<Setting["source"], string> = {
    database: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    environment: "bg-brand-50 text-brand-700 ring-brand-200",
    unset: "bg-slate-100 text-slate-500 ring-slate-200",
  };
  const labels: Record<Setting["source"], string> = {
    database: "Set here",
    environment: "From environment",
    unset: "Not set",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${styles[setting.source]}`}
    >
      {labels[setting.source]}
    </span>
  );
}

/**
 * Configure every third-party integration key from the dashboard.
 *
 * Secrets are write-only: the API returns only a masked preview, so an existing key is
 * shown as a placeholder and is left untouched unless the admin types a replacement.
 * Only fields the admin actually edited are submitted.
 */
export function IntegrationSettings() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<Setting[]>("/admin/settings")
      .then((data) => {
        if (!cancelled) setSettings(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = useMemo(() => {
    const byGroup = new Map<string, Setting[]>();
    for (const setting of settings) {
      const bucket = byGroup.get(setting.group) ?? [];
      bucket.push(setting);
      byGroup.set(setting.group, bucket);
    }
    return GROUP_ORDER.filter((g) => byGroup.has(g)).map((g) => ({
      group: g,
      items: byGroup.get(g)!,
    }));
  }, [settings]);

  const dirty = Object.keys(edits).length > 0;

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const updated = await apiPut<Setting[]>("/admin/settings", { values: edits });
      setSettings(updated);
      setEdits({});
      setSavedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardBody className="space-y-3">
          <div className="skeleton h-8 w-48" />
          <div className="skeleton h-24 w-full" />
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Integrations"
          subtitle="Keys saved here are encrypted at rest and override the deployment environment."
          icon={<PlugIcon className="h-5 w-5" />}
          action={
            <div className="flex items-center gap-3">
              {savedAt && !dirty && (
                <span className="text-sm font-medium text-emerald-700">Saved {savedAt}</span>
              )}
              <Button onClick={handleSave} disabled={!dirty} loading={saving}>
                Save changes
              </Button>
            </div>
          }
        />
        {error && (
          <CardBody>
            <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          </CardBody>
        )}
      </Card>

      <div className="stagger space-y-6">
        {grouped.map(({ group, items }, i) => (
          <div key={group} style={{ ["--i" as string]: i }}>
            <Card accent={`${GROUP_ACCENTS[group] ?? "from-brand-400 to-brand-600"}`}>
              <CardHeader title={GROUP_LABELS[group] ?? group} />
              <CardBody>
                <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
                  {items.map((setting) => {
                    const inputId = `setting-${setting.key}`;
                    const edited = edits[setting.key];
                    return (
                      <Field
                        key={setting.key}
                        label={setting.label}
                        htmlFor={inputId}
                        hint={setting.help_text}
                        action={<SourceBadge setting={setting} />}
                      >
                        {setting.choices.length > 0 ? (
                          <Select
                            id={inputId}
                            value={edited ?? setting.value}
                            onChange={(e) => setEdits({ ...edits, [setting.key]: e.target.value })}
                          >
                            {setting.choices.map((choice) => (
                              <option key={choice} value={choice}>
                                {choice}
                              </option>
                            ))}
                          </Select>
                        ) : (
                          <Input
                            id={inputId}
                            type={setting.is_secret ? "password" : "text"}
                            autoComplete="off"
                            className="font-mono"
                            // Secrets never round-trip: show the mask as a placeholder and keep
                            // the field empty so an untouched key is not overwritten.
                            placeholder={
                              setting.is_secret && setting.configured ? setting.value : "Not configured"
                            }
                            value={edited ?? (setting.is_secret ? "" : setting.value)}
                            onChange={(e) => setEdits({ ...edits, [setting.key]: e.target.value })}
                          />
                        )}
                      </Field>
                    );
                  })}
                </div>
              </CardBody>
            </Card>
          </div>
        ))}
      </div>

      <p className="px-1 text-xs text-slate-400">
        Clear a field and save to remove the stored value and fall back to the environment. The
        encryption key, JWT secret, and database URL are intentionally not editable here.
      </p>
    </div>
  );
}
