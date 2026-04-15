/**
 * Onboarding Wizard — Phase 6
 *
 * Step 1 — Company Info   (auto-filled from website research, user can edit)
 * Step 2 — Industry       (searchable catalogue + auto-detected)
 * Step 3 — Compliance     (framework library, pre-suggested by industry)
 * Step 4 — Glossary       (internal terminology)
 *
 * On completion → PATCH /tenants/me/settings + PUT /tenants/me/compliance
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, API_BASE_URL } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  Building2,
  BookOpen,
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  Loader2,
  Plus,
  X,
  Sparkles,
  Globe,
  Search,
  ShieldCheck,
  Info,
} from "lucide-react";

// ─── Industry catalogue (searchable) ─────────────────────────────────────────

interface IndustryOption {
  slug: string;
  label: string;
  description: string;
  tags: string[];   // keywords for search
}

const INDUSTRY_OPTIONS: IndustryOption[] = [
  { slug: "fintech/payments",  label: "FinTech / Payments",    description: "Payment processing, wallets, remittances, B2B payments APIs", tags: ["fintech","payment","wallet","remittance","bank","api","b2b","global"] },
  { slug: "fintech/lending",   label: "FinTech / Lending",     description: "Digital lending, BNPL, credit platforms, loan origination",    tags: ["fintech","lending","credit","bnpl","loan","neobank"] },
  { slug: "fintech/wealthtech",label: "WealthTech",            description: "Investment platforms, robo-advisory, portfolio management",     tags: ["fintech","wealth","investment","robo","portfolio","trading"] },
  { slug: "fintech/insurtech", label: "InsurTech",             description: "Insurance platforms, claims automation, policy management",     tags: ["fintech","insurance","insure","policy","claims","underwriting"] },
  { slug: "fintech/regtech",   label: "RegTech",               description: "Regulatory compliance tech, KYC/AML, reporting automation",    tags: ["fintech","regtech","compliance","kyc","aml","regulatory"] },
  { slug: "banking",           label: "Banking",               description: "Retail and commercial banking, core banking systems",           tags: ["bank","retail","commercial","deposit","core","swift"] },
  { slug: "capital_markets",   label: "Capital Markets",       description: "Trading, securities, derivatives, hedge funds",                 tags: ["capital","trading","securities","derivatives","hedge","exchange"] },
  { slug: "healthcare",        label: "Healthcare / HealthTech",description: "Health tech, EHR/EMR, medical devices, clinical systems",     tags: ["health","medical","ehr","emr","hospital","clinical","hipaa","phi"] },
  { slug: "pharma",            label: "Pharma / Life Sciences", description: "Drug discovery, clinical trials, regulatory submissions",     tags: ["pharma","drug","clinical","trial","fda","biotech","life","science"] },
  { slug: "saas",              label: "SaaS",                  description: "B2B / B2C software-as-a-service, subscription platforms",      tags: ["saas","software","b2b","subscription","platform","cloud"] },
  { slug: "devtools",          label: "Developer Tools",       description: "SDKs, APIs, developer productivity, infrastructure",           tags: ["developer","sdk","api","devtools","platform","cli","open source"] },
  { slug: "cybersecurity",     label: "Cybersecurity",         description: "Security products, IAM, threat detection, SOC platforms",      tags: ["security","cyber","iam","soc","threat","zero trust"] },
  { slug: "ecommerce",         label: "E-Commerce",            description: "Online retail, marketplaces, D2C platforms",                   tags: ["ecommerce","retail","marketplace","shop","d2c","commerce"] },
  { slug: "logistics",         label: "Logistics / Supply Chain",description: "Supply chain, last-mile delivery, warehousing, fleet",      tags: ["logistics","supply chain","warehouse","shipping","fleet","delivery"] },
  { slug: "edtech",            label: "EdTech",                description: "Learning management, online education, certification platforms",tags: ["education","edtech","learning","lms","elearning","course"] },
  { slug: "proptech",          label: "PropTech",              description: "Real estate technology, rent platforms, mortgage tech",        tags: ["property","real estate","proptech","rent","mortgage","realty"] },
  { slug: "govtech",           label: "GovTech",               description: "Government / public sector digital services",                  tags: ["government","public sector","civic","govtech","e-gov"] },
  { slug: "other",             label: "Other",                 description: "My industry isn't listed above",                               tags: ["other","custom"] },
];

// ─── Types ────────────────────────────────────────────────────────────────────

interface GlossaryEntry { term: string; definition: string }

interface CompanyProfileDraft {
  mission?: string | null;
  description?: string | null;
  team_size?: string | null;
  founded_year?: string | null;
  headquarters?: string | null;
  source?: string;
}

interface ComplianceFramework {
  id: number;
  code: string;
  name: string;
  category: string;
  geography?: string;
  description?: string;
  applicable_industries?: string[];
  is_selected: boolean;
}

interface TenantSettings {
  onboarding_complete?: boolean;
  industry?: string;
  industry_display_name?: string;
  industry_confidence?: number;
  company_profile_draft?: CompanyProfileDraft;
  company_profile?: CompanyProfileDraft;
  [key: string]: unknown;
}

// ─── Step components ──────────────────────────────────────────────────────────

function StepIndicator({ step, total }: { step: number; total: number }) {
  const labels = ["Company Info", "Industry", "Compliance", "Glossary"];
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

function AutoFilledBadge() {
  return (
    <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-green-50 border border-green-200 px-2 py-0.5 text-[10px] font-semibold text-green-700">
      <Sparkles className="h-2.5 w-2.5" /> AI-filled
    </span>
  );
}

function Step1CompanyInfo({
  mission, setMission,
  description, setDescription,
  teamSize, setTeamSize,
  foundedYear, setFoundedYear,
  autoFilledFields,
  profileResearching,
}: {
  mission: string; setMission: (v: string) => void;
  description: string; setDescription: (v: string) => void;
  teamSize: string; setTeamSize: (v: string) => void;
  foundedYear: string; setFoundedYear: (v: string) => void;
  autoFilledFields: Set<string>;
  profileResearching: boolean;
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

      {profileResearching && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600 flex-shrink-0" />
          <p className="text-sm text-blue-700">Researching your company from your website…</p>
        </div>
      )}

      {autoFilledFields.size > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <Sparkles className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-green-800">
            We&apos;ve pre-filled some fields from your company website. Review and edit anything that&apos;s wrong.
          </p>
        </div>
      )}

      {/* Mission */}
      <div className="space-y-2">
        <Label htmlFor="mission">
          Mission Statement <span className="text-gray-400">(optional)</span>
          {autoFilledFields.has("mission") && <AutoFilledBadge />}
        </Label>
        <textarea
          id="mission"
          rows={2}
          placeholder="e.g. Empowering teams to ship better software faster"
          value={mission}
          onChange={(e) => setMission(e.target.value)}
          maxLength={1000}
          className={`w-full rounded-md border px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none ${autoFilledFields.has("mission") ? "border-green-300 bg-green-50/40" : "border-gray-300"}`}
        />
        <p className="text-xs text-gray-400">{mission.length}/1000</p>
      </div>

      {/* Company Description */}
      <div className="space-y-2">
        <Label htmlFor="description">
          Company Description <span className="text-gray-400">(optional)</span>
          {autoFilledFields.has("description") && <AutoFilledBadge />}
        </Label>
        <textarea
          id="description"
          rows={3}
          placeholder="Brief description of what your company does and who it serves"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
          className={`w-full rounded-md border px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none ${autoFilledFields.has("description") ? "border-green-300 bg-green-50/40" : "border-gray-300"}`}
        />
        <p className="text-xs text-gray-400">{description.length}/2000</p>
      </div>

      {/* Team Size */}
      <div className="space-y-2">
        <Label>
          Team Size <span className="text-gray-400">(optional)</span>
          {autoFilledFields.has("teamSize") && <AutoFilledBadge />}
        </Label>
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
        <Label htmlFor="foundedYear">
          Founded Year <span className="text-gray-400">(optional)</span>
          {autoFilledFields.has("foundedYear") && <AutoFilledBadge />}
        </Label>
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
  const [search, setSearch] = useState("");
  const isOther = selectedIndustry === "other";

  const filteredOptions = search.trim()
    ? INDUSTRY_OPTIONS.filter((opt) => {
        const q = search.toLowerCase();
        return (
          opt.label.toLowerCase().includes(q) ||
          opt.description.toLowerCase().includes(q) ||
          opt.tags.some((t) => t.includes(q))
        );
      })
    : INDUSTRY_OPTIONS;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">What industry are you in?</h2>
        <p className="mt-1 text-sm text-gray-500">
          DokyDoc tailors validation prompts and compliance suggestions to your industry
        </p>
      </div>

      {/* Auto-detection banner */}
      {polling && !autoDetected && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600 flex-shrink-0" />
          <p className="text-sm text-blue-700">Detecting your industry from your website…</p>
        </div>
      )}
      {autoDetected && (
        <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <Sparkles className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-green-800">Auto-detected: {autoDetectedName || autoDetected}</p>
            {autoDetectedConfidence !== null && (
              <p className="text-xs text-green-600 mt-0.5">Confidence: {Math.round(autoDetectedConfidence * 100)}%</p>
            )}
            <p className="text-xs text-green-700 mt-1">We&apos;ve pre-selected this. You can change it.</p>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        <Input
          placeholder="Search — try 'bank', 'health', 'payment'…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
        {search && (
          <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Industry grid */}
      {filteredOptions.length === 0 ? (
        <div className="rounded-lg border border-dashed py-8 text-center text-sm text-gray-500">
          No results for &ldquo;{search}&rdquo;.{" "}
          <button className="text-blue-600 underline" onClick={() => { setSearch(""); setSelectedIndustry("other"); }}>
            Select &ldquo;Other&rdquo; and describe your industry.
          </button>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 max-h-72 overflow-y-auto pr-1">
          {filteredOptions.map((opt) => {
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
                  <span className="absolute -top-2 right-3 rounded-full bg-green-600 px-2 py-0.5 text-[10px] font-semibold text-white">Auto-detected</span>
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
      )}

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

// ─── Step 3: Compliance ───────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  "Financial Security":    "bg-blue-50 border-blue-200 text-blue-700",
  "Data Privacy":          "bg-purple-50 border-purple-200 text-purple-700",
  "Healthcare Compliance": "bg-green-50 border-green-200 text-green-700",
  "Security & Trust":      "bg-slate-50 border-slate-200 text-slate-700",
  "Financial Reporting":   "bg-amber-50 border-amber-200 text-amber-700",
  "Financial Regulation":  "bg-orange-50 border-orange-200 text-orange-700",
};

function Step3Compliance({
  selectedFrameworkIds,
  setSelectedFrameworkIds,
  industry,
}: {
  selectedFrameworkIds: Set<number>;
  setSelectedFrameworkIds: (v: Set<number>) => void;
  industry: string;
}) {
  const [frameworks, setFrameworks] = useState<ComplianceFramework[]>([]);
  const [loading, setLoading] = useState(true);
  const [customCode, setCustomCode] = useState("");
  const [customName, setCustomName] = useState("");
  const [customCategory, setCustomCategory] = useState("Other");
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [addingCustom, setAddingCustom] = useState(false);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    const token = localStorage.getItem("accessToken");
    if (!token) { setLoading(false); return; }
    const params = industry && industry !== "other" ? `?industry=${encodeURIComponent(industry)}` : "";
    fetch(`${API_BASE_URL}/compliance/library${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.frameworks) {
          setFrameworks(data.frameworks);
          // Pre-select already-saved selections
          const alreadySelected = new Set(
            (data.frameworks as ComplianceFramework[])
              .filter((f) => f.is_selected)
              .map((f) => f.id)
          );
          if (alreadySelected.size > 0) setSelectedFrameworkIds(alreadySelected);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [industry, setSelectedFrameworkIds]);

  const toggle = (id: number) => {
    const next = new Set(selectedFrameworkIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedFrameworkIds(next);
  };

  const addCustom = async () => {
    if (!customCode.trim() || !customName.trim()) return;
    setAddingCustom(true);
    const token = localStorage.getItem("accessToken");
    try {
      const res = await fetch(`${API_BASE_URL}/compliance/library`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ code: customCode.toUpperCase(), name: customName, category: customCategory }),
      });
      if (res.ok) {
        const fw: ComplianceFramework = await res.json();
        setFrameworks((prev) => [...prev, fw]);
        const next = new Set(selectedFrameworkIds);
        next.add(fw.id);
        setSelectedFrameworkIds(next);
        setCustomCode(""); setCustomName(""); setShowCustomForm(false);
      }
    } catch {} finally { setAddingCustom(false); }
  };

  // Group frameworks by category
  const grouped = frameworks.reduce<Record<string, ComplianceFramework[]>>((acc, fw) => {
    (acc[fw.category] = acc[fw.category] || []).push(fw);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Compliance Frameworks</h2>
        <p className="mt-1 text-sm text-gray-500">
          Select the regulatory frameworks your organisation follows.
          DokyDoc will flag relevant compliance gaps during validation.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
        </div>
      ) : (
        <>
          {Object.entries(grouped).map(([category, items]) => (
            <div key={category}>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{category}</p>
              <div className="flex flex-wrap gap-2">
                {items.map((fw) => {
                  const active = selectedFrameworkIds.has(fw.id);
                  const colorClass = CATEGORY_COLORS[fw.category] ?? "bg-gray-50 border-gray-200 text-gray-600";
                  return (
                    <button
                      key={fw.id}
                      type="button"
                      onClick={() => toggle(fw.id)}
                      title={fw.description ?? ""}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-all ${
                        active
                          ? "ring-2 ring-blue-500 ring-offset-1 " + colorClass
                          : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                      }`}
                    >
                      {active && <CheckCircle2 className="h-3 w-3" />}
                      {fw.code}
                      <span className="font-normal text-gray-400">·</span>
                      <span className="font-normal max-w-[140px] truncate">{fw.name}</span>
                      {fw.geography && (
                        <span className="ml-0.5 rounded bg-gray-100 px-1 text-[9px] text-gray-500">{fw.geography}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {selectedFrameworkIds.size > 0 && (
            <p className="text-xs text-blue-600 font-medium">{selectedFrameworkIds.size} framework{selectedFrameworkIds.size !== 1 ? "s" : ""} selected</p>
          )}

          {/* Add custom */}
          {!showCustomForm ? (
            <button
              type="button"
              onClick={() => setShowCustomForm(true)}
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-blue-600 mt-1"
            >
              <Plus className="h-4 w-4" /> Add custom framework
            </button>
          ) : (
            <div className="rounded-lg border border-dashed border-blue-300 bg-blue-50/40 p-4 space-y-3">
              <p className="text-xs font-semibold text-blue-700">Custom Compliance Framework</p>
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="Code (e.g. ISO9001)" value={customCode} onChange={(e) => setCustomCode(e.target.value)} maxLength={30} />
                <Input placeholder="Name (e.g. Quality Management)" value={customName} onChange={(e) => setCustomName(e.target.value)} maxLength={100} />
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={addCustom} disabled={addingCustom || !customCode.trim() || !customName.trim()} className="h-7 text-xs">
                  {addingCustom ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Plus className="h-3 w-3 mr-1" />} Add
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setShowCustomForm(false)} className="h-7 text-xs">Cancel</Button>
              </div>
            </div>
          )}

          <div className="flex items-start gap-2 rounded-md bg-gray-50 p-3 text-xs text-gray-500">
            <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>You can update your compliance selections anytime from the Admin dashboard.</span>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Step 4: Glossary ─────────────────────────────────────────────────────────

function Step4Glossary({
  entries,
  setEntries,
}: {
  entries: GlossaryEntry[];
  setEntries: (v: GlossaryEntry[]) => void;
})
 {
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
  const [autoFilledFields, setAutoFilledFields] = useState<Set<string>>(new Set());
  const [profileResearching, setProfileResearching] = useState(false);

  // Step 2 state
  const [selectedIndustry, setSelectedIndustry] = useState("");
  const [customIndustry, setCustomIndustry] = useState("");
  const [autoDetected, setAutoDetected] = useState<string | null>(null);
  const [autoDetectedName, setAutoDetectedName] = useState<string | null>(null);
  const [autoDetectedConfidence, setAutoDetectedConfidence] = useState<number | null>(null);
  const [polling, setPolling] = useState(false);

  // Step 3 state (compliance)
  const [selectedFrameworkIds, setSelectedFrameworkIds] = useState<Set<number>>(new Set());

  // Step 4 state
  const [glossaryEntries, setGlossaryEntries] = useState<GlossaryEntry[]>([]);

  // ── Bootstrap: load settings, pre-fill company profile draft ─────────────
  useEffect(() => {
    if (authLoading || !user) return;

    api.get<{ settings: TenantSettings }>("/tenants/me/settings")
      .then(({ settings }) => {
        if (settings?.onboarding_complete) {
          router.replace("/dashboard");
          return;
        }

        // Apply company profile draft (from website research task)
        const draft = settings?.company_profile_draft ?? settings?.company_profile;
        if (draft) {
          const filled = new Set<string>();
          if (draft.mission)      { setMission(draft.mission);           filled.add("mission"); }
          if (draft.description)  { setDescription(draft.description);   filled.add("description"); }
          if (draft.team_size)    { setTeamSize(draft.team_size);         filled.add("teamSize"); }
          if (draft.founded_year) { setFoundedYear(draft.founded_year);  filled.add("foundedYear"); }
          setAutoFilledFields(filled);
        } else {
          // No draft yet — show "researching" if website was provided (task running)
          setProfileResearching(true);
        }

        // Pre-select auto-detected industry
        if (settings?.industry) {
          setAutoDetected(settings.industry);
          setAutoDetectedName((settings.industry_display_name as string) || null);
          setAutoDetectedConfidence(
            typeof settings.industry_confidence === "number" ? settings.industry_confidence : null
          );
          setSelectedIndustry(settings.industry);
        } else {
          setPolling(true);
        }
      })
      .catch(() => {});
  }, [authLoading, user, router]);

  // ── Poll for profile draft (fires alongside industry poll) ────────────────
  useEffect(() => {
    if (!profileResearching) return;
    let attempts = 0;
    const poll = async () => {
      try {
        const { settings } = await api.get<{ settings: TenantSettings }>("/tenants/me/settings");
        const draft = settings?.company_profile_draft ?? settings?.company_profile;
        if (draft) {
          const filled = new Set<string>();
          if (draft.mission)      { setMission(draft.mission);          filled.add("mission"); }
          if (draft.description)  { setDescription(draft.description);  filled.add("description"); }
          if (draft.team_size)    { setTeamSize(draft.team_size);        filled.add("teamSize"); }
          if (draft.founded_year) { setFoundedYear(draft.founded_year); filled.add("foundedYear"); }
          setAutoFilledFields(filled);
          setProfileResearching(false);
          return;
        }
      } catch {}
      attempts++;
      if (attempts < 8) setTimeout(poll, 4000);
      else setProfileResearching(false);
    };
    const t = setTimeout(poll, 4000);
    return () => clearTimeout(t);
  }, [profileResearching]);

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

  // ── Navigation ────────────────────────────────────────────────────────────
  const canProceed = useCallback((): boolean => {
    if (step === 1) return true;
    if (step === 2) {
      if (!selectedIndustry) return false;
      if (selectedIndustry === "other" && !customIndustry.trim()) return false;
      return true;
    }
    if (step === 3) return true; // Compliance is optional
    if (step === 4) return true; // Glossary is optional
    return false;
  }, [step, selectedIndustry, customIndustry]);

  // ── Complete onboarding ───────────────────────────────────────────────────
  const handleComplete = async () => {
    setSaving(true);
    setError(null);
    const token = localStorage.getItem("accessToken");

    try {
      const glossary: Record<string, string> = {};
      glossaryEntries.forEach(({ term, definition }) => {
        if (term.trim() && definition.trim()) glossary[term.trim()] = definition.trim();
      });

      const finalIndustrySlug =
        selectedIndustry === "other"
          ? customIndustry.trim().toLowerCase().replace(/\s+/g, "-")
          : selectedIndustry;

      const settingsPatch: Record<string, unknown> = {
        onboarding_complete: true,
        ...(finalIndustrySlug && { industry: finalIndustrySlug }),
        ...(selectedIndustry === "other" && customIndustry.trim() && { industry_display_name: customIndustry.trim() }),
        ...(Object.keys(glossary).length > 0 && { glossary }),
        // Confirm company profile (promote draft → confirmed)
        company_profile: {
          ...(mission.trim() && { mission: mission.trim() }),
          ...(description.trim() && { description: description.trim() }),
          ...(teamSize && { team_size: teamSize }),
          ...(foundedYear && { founded_year: foundedYear }),
        },
      };

      const requests: Promise<unknown>[] = [
        api.patch("/tenants/me/settings", settingsPatch),
      ];

      // Save compliance selections (fire-and-forget if none)
      if (selectedFrameworkIds.size > 0 && token) {
        requests.push(
          fetch(`${API_BASE_URL}/compliance/tenants/me/compliance`, {
            method: "PUT",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ framework_ids: Array.from(selectedFrameworkIds) }),
          }).catch(() => {})
        );
      }

      await Promise.all(requests);
      router.replace("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
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
        <StepIndicator step={step} total={4} />

        {/* Card */}
        <div className="rounded-xl border bg-white p-8 shadow-sm min-h-[360px]">
          {step === 1 && (
            <Step1CompanyInfo
              mission={mission} setMission={setMission}
              description={description} setDescription={setDescription}
              teamSize={teamSize} setTeamSize={setTeamSize}
              foundedYear={foundedYear} setFoundedYear={setFoundedYear}
              autoFilledFields={autoFilledFields}
              profileResearching={profileResearching}
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
            <Step3Compliance
              selectedFrameworkIds={selectedFrameworkIds}
              setSelectedFrameworkIds={setSelectedFrameworkIds}
              industry={selectedIndustry}
            />
          )}
          {step === 4 && (
            <Step4Glossary entries={glossaryEntries} setEntries={setGlossaryEntries} />
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
            {step < 4 ? (
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
