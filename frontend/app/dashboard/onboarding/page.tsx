/**
 * Onboarding Wizard Page
 * P5-07: 3-step post-registration wizard for new tenants
 *
 * Step 1 — Company Info   (mission, description, team size, founded year)
 * Step 2 — Industry       (auto-detected with polling + manual pick + "Other")
 * Step 3 — Glossary       (key terms used internally)
 *
 * On completion → PATCH /tenants/me/settings { onboarding_complete: true }
 *              → redirect to /dashboard
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  Building2,
  Briefcase,
  BookOpen,
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  Loader2,
  Plus,
  X,
  Sparkles,
  Globe,
} from "lucide-react";

// ─── Industry catalogue ───────────────────────────────────────────────────────

interface IndustryOption {
  slug: string;
  label: string;
  description: string;
}

const INDUSTRY_OPTIONS: IndustryOption[] = [
  { slug: "fintech/payments",  label: "FinTech / Payments",   description: "Payment processing, wallets, remittances" },
  { slug: "fintech/lending",   label: "FinTech / Lending",    description: "Digital lending, BNPL, credit platforms" },
  { slug: "banking",           label: "Banking",              description: "Retail and commercial banking" },
  { slug: "healthcare",        label: "Healthcare",           description: "Health tech, EMRs, medical devices" },
  { slug: "saas",              label: "SaaS",                 description: "B2B / B2C software-as-a-service" },
  { slug: "ecommerce",         label: "E-Commerce",           description: "Online retail, marketplaces" },
  { slug: "logistics",         label: "Logistics",            description: "Supply chain, last-mile, warehousing" },
  { slug: "devtools",          label: "Developer Tools",      description: "SDKs, APIs, developer productivity" },
  { slug: "other",             label: "Other",                description: "My industry isn't listed above" },
];

// ─── Types ────────────────────────────────────────────────────────────────────

interface GlossaryEntry { term: string; definition: string }

interface TenantSettings {
  onboarding_complete?: boolean;
  industry?: string;
  industry_display_name?: string;
  industry_confidence?: number;
  [key: string]: unknown;
}

// ─── Step components ──────────────────────────────────────────────────────────

function StepIndicator({ step, total }: { step: number; total: number }) {
  const labels = ["Company Info", "Industry", "Glossary"];
  return (
    <div className="flex items-center justify-center space-x-4 mb-8">
      {Array.from({ length: total }, (_, i) => i + 1).map((s) => (
        <div key={s} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold transition-colors ${
                s === step
                  ? "bg-blue-600 text-white shadow-md"
                  : s < step
                  ? "bg-green-600 text-white"
                  : "bg-gray-100 text-gray-400"
              }`}
            >
              {s < step ? <CheckCircle2 className="h-5 w-5" /> : s}
            </div>
            <span
              className={`mt-1 text-xs font-medium ${
                s === step ? "text-blue-600" : s < step ? "text-green-600" : "text-gray-400"
              }`}
            >
              {labels[s - 1]}
            </span>
          </div>
          {s < total && (
            <div className={`mx-3 h-0.5 w-16 mt-[-14px] ${s < step ? "bg-green-600" : "bg-gray-200"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Step 1: Company Info ─────────────────────────────────────────────────────

function Step1CompanyInfo({
  mission, setMission,
  description, setDescription,
  teamSize, setTeamSize,
  foundedYear, setFoundedYear,
}: {
  mission: string; setMission: (v: string) => void;
  description: string; setDescription: (v: string) => void;
  teamSize: string; setTeamSize: (v: string) => void;
  foundedYear: string; setFoundedYear: (v: string) => void;
}) {
  const TEAM_SIZES = ["1-10", "11-50", "51-200", "201-500", "500+"];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Tell us about your company</h2>
        <p className="mt-1 text-sm text-gray-500">
          This helps DokyDoc give you industry-aware documentation insights
        </p>
      </div>

      {/* Mission */}
      <div className="space-y-2">
        <Label htmlFor="mission">Mission Statement <span className="text-gray-400">(optional)</span></Label>
        <textarea
          id="mission"
          rows={2}
          placeholder="e.g. Empowering teams to ship better software faster"
          value={mission}
          onChange={(e) => setMission(e.target.value)}
          maxLength={1000}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
        />
        <p className="text-xs text-gray-400">{mission.length}/1000</p>
      </div>

      {/* Company Description */}
      <div className="space-y-2">
        <Label htmlFor="description">Company Description <span className="text-gray-400">(optional)</span></Label>
        <textarea
          id="description"
          rows={3}
          placeholder="Brief description of what your company does and who it serves"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
        />
        <p className="text-xs text-gray-400">{description.length}/2000</p>
      </div>

      {/* Team Size */}
      <div className="space-y-2">
        <Label>Team Size <span className="text-gray-400">(optional)</span></Label>
        <div className="flex flex-wrap gap-2">
          {TEAM_SIZES.map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => setTeamSize(teamSize === size ? "" : size)}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
                teamSize === size
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-gray-300 bg-white text-gray-700 hover:border-blue-400"
              }`}
            >
              {size}
            </button>
          ))}
        </div>
      </div>

      {/* Founded Year */}
      <div className="space-y-2">
        <Label htmlFor="foundedYear">Founded Year <span className="text-gray-400">(optional)</span></Label>
        <Input
          id="foundedYear"
          type="number"
          min={1800}
          max={new Date().getFullYear()}
          placeholder={`e.g. ${new Date().getFullYear() - 5}`}
          value={foundedYear}
          onChange={(e) => setFoundedYear(e.target.value)}
          className="w-40"
        />
      </div>
    </div>
  );
}

// ─── Step 2: Industry ─────────────────────────────────────────────────────────

function Step2Industry({
  selectedIndustry,
  setSelectedIndustry,
  customIndustry,
  setCustomIndustry,
  autoDetected,
  autoDetectedName,
  autoDetectedConfidence,
  polling,
}: {
  selectedIndustry: string;
  setSelectedIndustry: (v: string) => void;
  customIndustry: string;
  setCustomIndustry: (v: string) => void;
  autoDetected: string | null;
  autoDetectedName: string | null;
  autoDetectedConfidence: number | null;
  polling: boolean;
}) {
  const isOther = selectedIndustry === "other";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">What industry are you in?</h2>
        <p className="mt-1 text-sm text-gray-500">
          DokyDoc tailors validation prompts and glossary suggestions to your industry
        </p>
      </div>

      {/* Auto-detection banner */}
      {polling && !autoDetected && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600 flex-shrink-0" />
          <p className="text-sm text-blue-700">
            Detecting your industry from your website...
          </p>
        </div>
      )}

      {autoDetected && (
        <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <Sparkles className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-green-800">
              Auto-detected: {autoDetectedName || autoDetected}
            </p>
            {autoDetectedConfidence !== null && (
              <p className="text-xs text-green-600 mt-0.5">
                Confidence: {Math.round(autoDetectedConfidence * 100)}%
              </p>
            )}
            <p className="text-xs text-green-700 mt-1">
              We&apos;ve pre-selected this below. You can change it.
            </p>
          </div>
        </div>
      )}

      {/* Industry grid */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {INDUSTRY_OPTIONS.map((opt) => {
          const isAutoDetectedOption = autoDetected === opt.slug;
          return (
            <button
              key={opt.slug}
              type="button"
              onClick={() => setSelectedIndustry(opt.slug)}
              className={`relative flex flex-col items-start rounded-lg border-2 p-4 text-left transition-all ${
                selectedIndustry === opt.slug
                  ? "border-blue-600 bg-blue-50"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              {isAutoDetectedOption && (
                <span className="absolute -top-2 right-3 rounded-full bg-green-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                  Auto-detected
                </span>
              )}
              <span className="font-semibold text-sm text-gray-900">{opt.label}</span>
              <span className="mt-1 text-xs text-gray-500 leading-relaxed">{opt.description}</span>
              {selectedIndustry === opt.slug && (
                <CheckCircle2 className="absolute right-3 top-3 h-4 w-4 text-blue-600" />
              )}
            </button>
          );
        })}
      </div>

      {/* P5-11: "Other" custom input */}
      {isOther && (
        <div className="rounded-lg border border-dashed border-gray-300 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-gray-500" />
            <Label htmlFor="customIndustry" className="text-sm font-medium">
              Describe your industry
            </Label>
          </div>
          <Input
            id="customIndustry"
            type="text"
            placeholder="e.g. InsurTech, AgriTech, GovTech"
            value={customIndustry}
            onChange={(e) => setCustomIndustry(e.target.value)}
            maxLength={200}
          />
          <p className="text-xs text-gray-400">
            DokyDoc will generate a custom industry profile for you in the background.
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Step 3: Glossary ─────────────────────────────────────────────────────────

function Step3Glossary({
  entries,
  setEntries,
}: {
  entries: GlossaryEntry[];
  setEntries: (v: GlossaryEntry[]) => void;
}) {
  const addEntry = () => setEntries([...entries, { term: "", definition: "" }]);

  const removeEntry = (i: number) =>
    setEntries(entries.filter((_, idx) => idx !== i));

  const updateEntry = (i: number, field: keyof GlossaryEntry, value: string) => {
    const updated = entries.map((e, idx) =>
      idx === i ? { ...e, [field]: value } : e
    );
    setEntries(updated);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Internal Glossary</h2>
        <p className="mt-1 text-sm text-gray-500">
          Add company-specific terms so DokyDoc understands your vocabulary (optional)
        </p>
      </div>

      <div className="space-y-3">
        {entries.map((entry, i) => (
          <div key={i} className="flex gap-3 items-start">
            <div className="flex-1 grid grid-cols-2 gap-2">
              <Input
                placeholder="Term (e.g. CAR)"
                value={entry.term}
                onChange={(e) => updateEntry(i, "term", e.target.value)}
                maxLength={100}
              />
              <Input
                placeholder="Definition (e.g. Capital Adequacy Ratio)"
                value={entry.definition}
                onChange={(e) => updateEntry(i, "definition", e.target.value)}
                maxLength={500}
              />
            </div>
            <button
              type="button"
              onClick={() => removeEntry(i)}
              className="mt-2 rounded p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      {entries.length < 20 && (
        <Button type="button" variant="outline" onClick={addEntry} className="gap-2">
          <Plus className="h-4 w-4" />
          Add Term
        </Button>
      )}

      {entries.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-300 py-8 text-center">
          <BookOpen className="mx-auto h-8 w-8 text-gray-300" />
          <p className="mt-2 text-sm text-gray-500">No terms added yet</p>
          <p className="text-xs text-gray-400">You can skip this — add terms later in Settings</p>
        </div>
      )}
    </div>
  );
}

// ─── Main Wizard ──────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1 state
  const [mission, setMission] = useState("");
  const [description, setDescription] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [foundedYear, setFoundedYear] = useState("");

  // Step 2 state
  const [selectedIndustry, setSelectedIndustry] = useState("");
  const [customIndustry, setCustomIndustry] = useState("");
  const [autoDetected, setAutoDetected] = useState<string | null>(null);
  const [autoDetectedName, setAutoDetectedName] = useState<string | null>(null);
  const [autoDetectedConfidence, setAutoDetectedConfidence] = useState<number | null>(null);
  const [polling, setPolling] = useState(false);

  // Step 3 state
  const [glossaryEntries, setGlossaryEntries] = useState<GlossaryEntry[]>([]);

  // ── Bootstrap: check if onboarding already complete ────────────────────────
  useEffect(() => {
    if (authLoading || !user) return;

    api.get<{ settings: TenantSettings }>("/tenants/me/settings")
      .then(({ settings }) => {
        if (settings?.onboarding_complete) {
          router.replace("/dashboard");
          return;
        }
        // Pre-select auto-detected industry if already available
        if (settings?.industry) {
          setAutoDetected(settings.industry);
          setAutoDetectedName(settings.industry_display_name as string || null);
          setAutoDetectedConfidence(
            typeof settings.industry_confidence === "number"
              ? settings.industry_confidence
              : null
          );
          setSelectedIndustry(settings.industry);
        } else {
          // Start polling — background task may still be running
          setPolling(true);
        }
      })
      .catch(() => {/* non-fatal */});
  }, [authLoading, user, router]);

  // ── Poll for auto-detected industry (max 30 s, every 4 s) ─────────────────
  useEffect(() => {
    if (!polling) return;

    let attempts = 0;
    const MAX_ATTEMPTS = 8; // 8 × 4 s = 32 s

    const poll = async () => {
      try {
        const { settings } = await api.get<{ settings: TenantSettings }>("/tenants/me/settings");
        if (settings?.industry) {
          setAutoDetected(settings.industry);
          setAutoDetectedName(settings.industry_display_name as string || null);
          setAutoDetectedConfidence(
            typeof settings.industry_confidence === "number"
              ? settings.industry_confidence
              : null
          );
          setSelectedIndustry(settings.industry);
          setPolling(false);
          return;
        }
      } catch {/* ignore */}

      attempts++;
      if (attempts < MAX_ATTEMPTS) {
        setTimeout(poll, 4000);
      } else {
        setPolling(false);
      }
    };

    const timerId = setTimeout(poll, 4000);
    return () => clearTimeout(timerId);
  }, [polling]);

  // ── Navigation ─────────────────────────────────────────────────────────────
  const canProceed = useCallback((): boolean => {
    if (step === 1) return true; // All step-1 fields are optional
    if (step === 2) {
      if (!selectedIndustry) return false;
      if (selectedIndustry === "other" && !customIndustry.trim()) return false;
      return true;
    }
    if (step === 3) return true; // Glossary is optional
    return false;
  }, [step, selectedIndustry, customIndustry]);

  // ── Complete onboarding ────────────────────────────────────────────────────
  const handleComplete = async () => {
    setSaving(true);
    setError(null);

    try {
      // Build glossary dict from non-empty entries
      const glossary: Record<string, string> = {};
      glossaryEntries.forEach(({ term, definition }) => {
        if (term.trim() && definition.trim()) {
          glossary[term.trim()] = definition.trim();
        }
      });

      // Determine final industry slug
      const finalIndustrySlug =
        selectedIndustry === "other"
          ? customIndustry.trim().toLowerCase().replace(/\s+/g, "-")
          : selectedIndustry;

      // Build settings patch
      const settingsPatch: Record<string, unknown> = {
        onboarding_complete: true,
        ...(finalIndustrySlug && { industry: finalIndustrySlug }),
        ...(selectedIndustry === "other" &&
          customIndustry.trim() && { industry_display_name: customIndustry.trim() }),
        ...(Object.keys(glossary).length > 0 && { glossary }),
        org_profile: {
          ...(mission.trim() && { mission: mission.trim() }),
          ...(description.trim() && { company_description: description.trim() }),
          ...(teamSize && { team_size: teamSize }),
          ...(foundedYear && { founded_year: parseInt(foundedYear) }),
        },
      };

      // Also save org profile through the dedicated endpoint
      const orgPayload: Record<string, unknown> = {};
      if (mission.trim()) orgPayload.mission = mission.trim();
      if (description.trim()) orgPayload.company_description = description.trim();
      if (teamSize) orgPayload.team_size = teamSize;
      if (foundedYear) orgPayload.founded_year = parseInt(foundedYear);

      const requests: Promise<unknown>[] = [
        api.patch("/tenants/me/settings", settingsPatch),
      ];

      if (Object.keys(orgPayload).length > 0) {
        requests.push(api.put("/tenants/org-profile", orgPayload).catch(() => {}));
      }

      await Promise.all(requests);

      router.replace("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save settings";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (authLoading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto py-8 px-4">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-100 mb-3">
            <Building2 className="h-6 w-6 text-blue-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Welcome to DokyDoc!</h1>
          <p className="mt-1 text-gray-500">
            Let&apos;s personalize your workspace in a few quick steps
          </p>
        </div>

        {/* Step Indicator */}
        <StepIndicator step={step} total={3} />

        {/* Card */}
        <div className="rounded-xl border bg-white p-8 shadow-sm min-h-[360px]">
          {step === 1 && (
            <Step1CompanyInfo
              mission={mission} setMission={setMission}
              description={description} setDescription={setDescription}
              teamSize={teamSize} setTeamSize={setTeamSize}
              foundedYear={foundedYear} setFoundedYear={setFoundedYear}
            />
          )}

          {step === 2 && (
            <Step2Industry
              selectedIndustry={selectedIndustry}
              setSelectedIndustry={setSelectedIndustry}
              customIndustry={customIndustry}
              setCustomIndustry={setCustomIndustry}
              autoDetected={autoDetected}
              autoDetectedName={autoDetectedName}
              autoDetectedConfidence={autoDetectedConfidence}
              polling={polling}
            />
          )}

          {step === 3 && (
            <Step3Glossary entries={glossaryEntries} setEntries={setGlossaryEntries} />
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 rounded-md bg-red-50 border border-red-200 p-3">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Navigation */}
        <div className="mt-6 flex items-center justify-between">
          <div>
            {step > 1 && (
              <Button
                variant="outline"
                onClick={() => setStep(step - 1)}
                disabled={saving}
                className="gap-2"
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </Button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {step < 3 ? (
              <>
                <button
                  type="button"
                  onClick={() => setStep(step + 1)}
                  className="text-sm text-gray-500 hover:text-gray-700 underline"
                >
                  Skip for now
                </button>
                <Button
                  onClick={() => setStep(step + 1)}
                  disabled={!canProceed()}
                  className="gap-2"
                >
                  Continue
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={handleComplete}
                  className="text-sm text-gray-500 hover:text-gray-700 underline"
                  disabled={saving}
                >
                  Skip and finish
                </button>
                <Button
                  onClick={handleComplete}
                  disabled={saving}
                  className="gap-2"
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-4 w-4" />
                      Finish Setup
                    </>
                  )}
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Footer note */}
        <p className="mt-4 text-center text-xs text-gray-400">
          You can update all these settings later in{" "}
          <span className="underline">Settings &rarr; Organization</span>
        </p>
      </div>
    </AppLayout>
  );
}
