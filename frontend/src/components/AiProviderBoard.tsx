import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPut } from "../api/client";
import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Field, Input, Select } from "./ui/Input";
import { SparkleIcon } from "./ui/Icon";
import { SourceBadge, type Setting } from "./IntegrationSettings";

/** One selectable model within a provider, as described by GET /admin/settings/ai-catalog. */
interface CatalogModel {
  id: string;
  label: string;
  recommended: boolean;
}

interface CatalogProvider {
  id: string;
  label: string;
  key_setting: string;
  key_configured: boolean;
  models: CatalogModel[];
}

/** One workload slot: which providers can serve it, and with which models. */
interface CatalogRole {
  role: string;
  label: string;
  help_text: string;
  /** False while no client exists for this kind of generation yet (voice, video). */
  connected: boolean;
  default_provider: string;
  provider_setting: string;
  model_setting: string;
  providers: CatalogProvider[];
}

const CUSTOM = "__custom__";

/**
 * The AI Provider board: one API key per vendor, then one provider+model slot per workload.
 *
 * Each agent runs on the slot matching its job, so analysis, research, writing, voice, video
 * and image generation can each use the model that is strongest at that job. Model dropdowns
 * are curated per provider with a recommended default, plus a custom entry so a newly
 * released model id is never blocked on a deploy.
 *
 * Writes go through the same PUT /admin/settings the rest of the integrations page uses, so
 * values are encrypted at rest and audit-logged automatically.
 */
export function AiProviderBoard() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [roles, setRoles] = useState<CatalogRole[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [customOpen, setCustomOpen] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  async function load() {
    const [catalog, allSettings] = await Promise.all([
      apiGet<{ roles: CatalogRole[] }>("/admin/settings/ai-catalog"),
      apiGet<Setting[]>("/admin/settings"),
    ]);
    setRoles(catalog.roles);
    setSettings(allSettings);
  }

  useEffect(() => {
    let cancelled = false;
    load()
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

  const byKey = useMemo(() => {
    const map = new Map<string, Setting>();
    for (const setting of settings) map.set(setting.key, setting);
    return map;
  }, [settings]);

  /** Every provider key setting referenced by the catalog, in catalog order, deduplicated. */
  const keySettings = useMemo(() => {
    const seen = new Map<string, { label: string; setting: Setting }>();
    for (const role of roles) {
      for (const provider of role.providers) {
        const setting = byKey.get(provider.key_setting);
        if (setting && !seen.has(provider.key_setting)) {
          seen.set(provider.key_setting, { label: provider.label, setting });
        }
      }
    }
    return [...seen.values()];
  }, [roles, byKey]);

  /** The value currently shown for a key: a pending edit, else what the API returned. */
  function valueOf(key: string): string {
    return edits[key] ?? byKey.get(key)?.value ?? "";
  }

  function providerOf(role: CatalogRole): string {
    return valueOf(role.provider_setting) || role.default_provider;
  }

  function modelsFor(role: CatalogRole): CatalogModel[] {
    return role.providers.find((p) => p.id === providerOf(role))?.models ?? [];
  }

  function recommendedModel(role: CatalogRole): string {
    const models = modelsFor(role);
    return (models.find((m) => m.recommended) ?? models[0])?.id ?? "";
  }

  const dirty = Object.keys(edits).length > 0;

  function setValue(key: string, value: string) {
    setEdits((prev) => ({ ...prev, [key]: value }));
  }

  /** Switching provider must not leave the previous vendor's model id behind. */
  function changeProvider(role: CatalogRole, provider: string) {
    const next = { ...edits, [role.provider_setting]: provider };
    const models = role.providers.find((p) => p.id === provider)?.models ?? [];
    next[role.model_setting] = (models.find((m) => m.recommended) ?? models[0])?.id ?? "";
    setEdits(next);
    setCustomOpen((prev) => ({ ...prev, [role.role]: false }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await apiPut<Setting[]>("/admin/settings", { values: edits });
      // Reload the catalog too, so the "key set" markers reflect the keys just saved.
      await load();
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
          title="AI providers"
          subtitle="Give each job the model that is best at it. Keys are encrypted at rest and override the deployment environment."
          icon={<SparkleIcon className="h-5 w-5" />}
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
            <p
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              {error}
            </p>
          </CardBody>
        )}
      </Card>

      <Card accent="from-brand-400 to-brand-600">
        <CardHeader
          title="Provider keys"
          subtitle="Enter each vendor's key once — every slot pointing at that vendor reuses it."
        />
        <CardBody>
          <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
            {keySettings.map(({ label, setting }) => {
              const inputId = `ai-key-${setting.key}`;
              return (
                <Field
                  key={setting.key}
                  label={label}
                  htmlFor={inputId}
                  hint={setting.help_text}
                  action={<SourceBadge setting={setting} />}
                >
                  <Input
                    id={inputId}
                    type="password"
                    autoComplete="off"
                    className="font-mono"
                    // Secrets never round-trip: the mask is a placeholder, so an untouched
                    // key is left exactly as it is.
                    placeholder={setting.configured ? setting.value : "Not configured"}
                    value={edits[setting.key] ?? ""}
                    onChange={(e) => setValue(setting.key, e.target.value)}
                  />
                </Field>
              );
            })}
          </div>
        </CardBody>
      </Card>

      <Card accent="from-violet-400 to-violet-600">
        <CardHeader
          title="Model per job"
          subtitle="Every agent runs on the slot matching its work, so one campaign can span several vendors."
        />
        <CardBody>
          <div className="space-y-6">
            {roles.map((role) => {
              const provider = providerOf(role);
              const models = modelsFor(role);
              const modelValue = valueOf(role.model_setting) || recommendedModel(role);
              const isCustom =
                customOpen[role.role] ||
                (modelValue !== "" && !models.some((m) => m.id === modelValue));
              const activeProvider = role.providers.find((p) => p.id === provider);
              const keyMissing = provider !== "none" && !activeProvider?.key_configured;

              return (
                <div
                  key={role.role}
                  className="grid gap-4 border-t border-slate-100 pt-5 first:border-0 first:pt-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,14rem)_minmax(0,16rem)]"
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-sm font-semibold text-slate-800">{role.label}</h4>
                      {!role.connected && (
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500 ring-1 ring-inset ring-slate-200">
                          Not yet connected
                        </span>
                      )}
                      {role.connected && keyMissing && (
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
                          No key for this provider
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400">{role.help_text}</p>
                    {!role.connected && (
                      <p className="text-xs text-slate-400">
                        Saved and passed to the agent, but nothing is generated yet — the agent
                        still produces a spec.
                      </p>
                    )}
                  </div>

                  <Field label="Provider" htmlFor={`ai-provider-${role.role}`}>
                    <Select
                      id={`ai-provider-${role.role}`}
                      value={provider}
                      onChange={(e) => changeProvider(role, e.target.value)}
                    >
                      <option value="none">Off — use fallbacks</option>
                      {role.providers.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label}
                          {p.key_configured ? "" : " (no key)"}
                        </option>
                      ))}
                    </Select>
                  </Field>

                  <Field label="Model" htmlFor={`ai-model-${role.role}`}>
                    {provider === "none" ? (
                      <Select id={`ai-model-${role.role}`} value="" disabled>
                        <option value="">—</option>
                      </Select>
                    ) : (
                      <div className="space-y-2">
                        <Select
                          id={`ai-model-${role.role}`}
                          value={isCustom ? CUSTOM : modelValue}
                          onChange={(e) => {
                            if (e.target.value === CUSTOM) {
                              setCustomOpen((prev) => ({ ...prev, [role.role]: true }));
                              return;
                            }
                            setCustomOpen((prev) => ({ ...prev, [role.role]: false }));
                            setValue(role.model_setting, e.target.value);
                          }}
                        >
                          {models.map((model) => (
                            <option key={model.id} value={model.id}>
                              {model.label}
                              {model.recommended ? " — Recommended" : ""}
                            </option>
                          ))}
                          <option value={CUSTOM}>Custom…</option>
                        </Select>
                        {isCustom && (
                          <Input
                            aria-label={`${role.label} custom model id`}
                            className="font-mono"
                            placeholder="model id"
                            value={
                              models.some((m) => m.id === modelValue) ? "" : modelValue
                            }
                            onChange={(e) => setValue(role.model_setting, e.target.value)}
                          />
                        )}
                      </div>
                    )}
                  </Field>
                </div>
              );
            })}
          </div>
        </CardBody>
      </Card>

      <p className="px-1 text-xs text-slate-400">
        A slot with no provider or no key falls back to deterministic, rule-based output rather
        than failing the campaign — so one misconfigured slot never breaks a run.
      </p>
    </div>
  );
}
