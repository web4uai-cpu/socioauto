import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPut } from "../api/client";

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

const GROUP_ORDER = ["ai", "billing", "platforms", "general"];

function SourceBadge({ setting }: { setting: Setting }) {
  const styles: Record<Setting["source"], string> = {
    database: "bg-green-100 text-green-800",
    environment: "bg-blue-100 text-blue-800",
    unset: "bg-gray-100 text-gray-600",
  };
  const labels: Record<Setting["source"], string> = {
    database: "Set here",
    environment: "From environment",
    unset: "Not set",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${styles[setting.source]}`}>
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

  if (loading) return <section className="border rounded p-4">Loading settings…</section>;

  return (
    <section className="border rounded p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Integrations</h2>
          <p className="text-sm text-gray-600">
            Keys saved here are encrypted at rest and override the deployment environment.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {savedAt && !dirty && (
            <span className="text-sm text-green-700">Saved at {savedAt}</span>
          )}
          <button
            type="button"
            onClick={handleSave}
            disabled={!dirty || saving}
            className="px-4 py-2 rounded bg-blue-600 text-white disabled:bg-gray-300"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {error}
        </p>
      )}

      {grouped.map(({ group, items }) => (
        <fieldset key={group} className="border rounded p-3">
          <legend className="px-1 text-sm font-semibold">
            {GROUP_LABELS[group] ?? group}
          </legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {items.map((setting) => {
              const inputId = `setting-${setting.key}`;
              const edited = edits[setting.key];
              return (
                <div key={setting.key} className="space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <label htmlFor={inputId} className="text-sm font-medium">
                      {setting.label}
                    </label>
                    <SourceBadge setting={setting} />
                  </div>

                  {setting.choices.length > 0 ? (
                    <select
                      id={inputId}
                      className="w-full border rounded px-2 py-1 text-sm"
                      value={edited ?? setting.value}
                      onChange={(e) =>
                        setEdits({ ...edits, [setting.key]: e.target.value })
                      }
                    >
                      {setting.choices.map((choice) => (
                        <option key={choice} value={choice}>
                          {choice}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={inputId}
                      type={setting.is_secret ? "password" : "text"}
                      autoComplete="off"
                      className="w-full border rounded px-2 py-1 text-sm font-mono"
                      // Secrets never round-trip: show the mask as a placeholder and keep
                      // the field empty so an untouched key is not overwritten.
                      placeholder={
                        setting.is_secret && setting.configured
                          ? setting.value
                          : "Not configured"
                      }
                      value={edited ?? (setting.is_secret ? "" : setting.value)}
                      onChange={(e) =>
                        setEdits({ ...edits, [setting.key]: e.target.value })
                      }
                    />
                  )}

                  {setting.help_text && (
                    <p className="text-xs text-gray-500">{setting.help_text}</p>
                  )}
                </div>
              );
            })}
          </div>
        </fieldset>
      ))}

      <p className="text-xs text-gray-500">
        Clear a field and save to remove the stored value and fall back to the environment.
        The encryption key, JWT secret, and database URL are intentionally not editable here.
      </p>
    </section>
  );
}
