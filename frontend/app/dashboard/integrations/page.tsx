"use client";

export const dynamic = "force-dynamic";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Link2,
  Loader2,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Trash2,
  Plus,
  FileText,
  AlertCircle,
  ExternalLink,
  Download,
  Slack,
  LogIn,
  Settings2,
  Database,
  Zap,
  ChevronDown,
  ChevronUp,
  GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

// ----- Types -----

interface IntegrationStatus {
  id: number;
  provider: string;
  workspace_name: string | null;
  workspace_id: string | null;
  base_url: string | null;
  is_active: boolean;
  last_synced_at: string | null;
  sync_error: string | null;
  created_at: string;
}

interface PageItem {
  id: string;
  title: string;
  url: string;
  updated_at: string;
  member_count?: number;
  topic?: string;
}

interface ConnectFormState {
  provider: string;
  access_token: string;
  workspace_name: string;
  base_url: string;
}

// OAuth-capable providers use the full OAuth flow.
// Notion uses manual token (internal integration token model).
const OAUTH_PROVIDERS = new Set(["jira", "confluence", "slack", "github"]);

const PROVIDER_META: Record<
  string,
  {
    label: string;
    color: string;
    description: string;
    tokenLabel: string;
    tokenPlaceholder: string;
    useOAuth: boolean;
    oauthLabel: string;
  }
> = {
  notion: {
    label: "Notion",
    color: "bg-gray-900 text-white",
    description: "Import pages from your Notion workspace",
    tokenLabel: "Notion Integration Token",
    tokenPlaceholder: "secret_...",
    useOAuth: false,
    oauthLabel: "",
  },
  jira: {
    label: "Jira",
    color: "bg-blue-600 text-white",
    description: "Import issues and epics from Jira Cloud",
    tokenLabel: "Jira API Token",
    tokenPlaceholder: "Your Atlassian API token",
    useOAuth: true,
    oauthLabel: "Connect with Atlassian",
  },
  slack: {
    label: "Slack",
    color: "bg-[#4A154B] text-white",
    description: "Browse channels and import message history as docs",
    tokenLabel: "Slack Bot Token",
    tokenPlaceholder: "xoxb-...",
    useOAuth: true,
    oauthLabel: "Connect with Slack",
  },
  confluence: {
    label: "Confluence",
    color: "bg-blue-500 text-white",
    description: "Browse and import pages from your Confluence Cloud workspace",
    tokenLabel: "Atlassian API Token",
    tokenPlaceholder: "Your Atlassian API token",
    useOAuth: true,
    oauthLabel: "Connect with Atlassian",
  },
  sharepoint: {
    label: "SharePoint",
    color: "bg-teal-600 text-white",
    description: "Import SharePoint documents (coming soon)",
    tokenLabel: "Access Token",
    tokenPlaceholder: "",
    useOAuth: false,
    oauthLabel: "",
  },
  github: {
    label: "GitHub",
    color: "bg-gray-900 text-white",
    description: "Connect your GitHub account to access private repositories in Code Analysis",
    tokenLabel: "GitHub Personal Access Token",
    tokenPlaceholder: "ghp_...",
    useOAuth: true,
    oauthLabel: "Connect with GitHub",
  },
};

// ----- Toast helper -----

function Toast({
  message,
  type,
  onClose,
}: {
  message: string;
  type: "success" | "error";
  onClose: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onClose, 5000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      className={`fixed top-4 right-4 z-50 flex items-center gap-3 rounded-xl shadow-lg px-5 py-3.5 text-sm font-medium ${
        type === "success"
          ? "bg-green-600 text-white"
          : "bg-red-600 text-white"
      }`}
    >
      {type === "success" ? (
        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
      ) : (
        <AlertCircle className="w-4 h-4 flex-shrink-0" />
      )}
      {message}
      <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100">
        <XCircle className="w-4 h-4" />
      </button>
    </div>
  );
}

// ----- Main Page -----

function IntegrationsContent() {
  const searchParams = useSearchParams();

  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const [form, setForm] = useState<ConnectFormState>({
    provider: "",
    access_token: "",
    workspace_name: "",
    base_url: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);

  // Toast
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // JIRA deep sync config state
  const [showJiraConfig, setShowJiraConfig] = useState(false);
  const [jiraProjectKeys, setJiraProjectKeys] = useState<string[]>([]);
  const [jiraKeyInput, setJiraKeyInput] = useState("");
  const [jiraSyncFreq, setJiraSyncFreq] = useState("manual");
  const [jiraAcField, setJiraAcField] = useState("");
  const [jiraSavingConfig, setJiraSavingConfig] = useState(false);
  const [jiraSyncStatus, setJiraSyncStatus] = useState<any>(null);
  const [jiraSyncing, setJiraSyncing] = useState(false);

  const fetchJiraSyncStatus = async () => {
    try {
      const data = (await api.get("/integrations/jira/sync/status")) as any;
      setJiraSyncStatus(data);
      if (data.sync_config?.project_keys) setJiraProjectKeys(data.sync_config.project_keys);
      if (data.sync_config?.sync_frequency) setJiraSyncFreq(data.sync_config.sync_frequency);
      if (data.sync_config?.custom_field_mappings?.acceptance_criteria)
        setJiraAcField(data.sync_config.custom_field_mappings.acceptance_criteria);
    } catch { /* not connected yet */ }
  };

  useEffect(() => {
    // Fetch JIRA sync status when JIRA is connected
    const jiraConnected = integrations.some((i) => i.provider === "jira" && i.is_active);
    if (jiraConnected) fetchJiraSyncStatus();
  }, [integrations]);

  const addJiraProjectKey = () => {
    const key = jiraKeyInput.trim().toUpperCase();
    if (key && !jiraProjectKeys.includes(key)) {
      setJiraProjectKeys([...jiraProjectKeys, key]);
    }
    setJiraKeyInput("");
  };

  const removeJiraProjectKey = (k: string) => {
    setJiraProjectKeys(jiraProjectKeys.filter((p) => p !== k));
  };

  const handleSaveJiraConfig = async () => {
    setJiraSavingConfig(true);
    try {
      await api.put("/integrations/jira/config", {
        project_keys: jiraProjectKeys,
        sync_frequency: jiraSyncFreq,
        acceptance_criteria_field: jiraAcField || undefined,
        include_subtasks: false,
      });
      setToast({ message: "Jira sync configuration saved.", type: "success" });
      await fetchJiraSyncStatus();
    } catch (e: any) {
      setToast({ message: `Failed to save config: ${e?.message || "Unknown error"}`, type: "error" });
    } finally {
      setJiraSavingConfig(false);
    }
  };

  const handleJiraSync = async () => {
    setJiraSyncing(true);
    try {
      const result = (await api.post("/integrations/jira/sync", {})) as any;
      setToast({
        message: `Jira sync complete: ${result.synced} items synced, ${result.ingested_to_brain} added to Brain.`,
        type: "success",
      });
      await fetchJiraSyncStatus();
      await fetchIntegrations();
    } catch (e: any) {
      setToast({ message: `Sync failed: ${e?.message || "Unknown error"}`, type: "error" });
    } finally {
      setJiraSyncing(false);
    }
  };

  // Page browser state
  const [browsingProvider, setBrowsingProvider] = useState<string | null>(null);
  const [pages, setPages] = useState<PageItem[]>([]);
  const [pagesLoading, setPagesLoading] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [importedIds, setImportedIds] = useState<Set<string>>(new Set());
  const [pageQuery, setPageQuery] = useState("");

  const fetchIntegrations = useCallback(async () => {
    setLoading(true);
    try {
      const data = (await api.get("/integrations/")) as any;
      setIntegrations(data.integrations || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIntegrations();
  }, [fetchIntegrations]);

  // Handle OAuth callback query params (?oauth_success=jira&workspace=... or ?oauth_error=...)
  useEffect(() => {
    const success = searchParams.get("oauth_success");
    const error = searchParams.get("oauth_error");
    const workspace = searchParams.get("workspace");
    const provider = searchParams.get("provider");

    if (success) {
      const label = PROVIDER_META[success]?.label || success;
      const ws = workspace ? ` (${decodeURIComponent(workspace)})` : "";
      setToast({ message: `${label}${ws} connected successfully!`, type: "success" });
      fetchIntegrations();
      // Clean URL
      window.history.replaceState({}, "", "/dashboard/integrations");
    } else if (error) {
      const label = provider ? PROVIDER_META[provider]?.label || provider : "Integration";
      setToast({
        message: `${label} connection failed: ${decodeURIComponent(error)}. Check your app credentials.`,
        type: "error",
      });
      window.history.replaceState({}, "", "/dashboard/integrations");
    }
  }, [searchParams, fetchIntegrations]);

  // OAuth redirect flow
  const handleOAuthConnect = async (provider: string) => {
    setOauthLoading(provider);
    try {
      const data = (await api.get(
        `/integrations/${provider}/oauth/authorize`
      )) as any;
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (e: any) {
      const status = (e as any)?.status;
      if (status === 501) {
        // OAuth not configured on server — silently fall back to API token modal
        setToast({
          message: `${PROVIDER_META[provider]?.label || provider} OAuth is not configured on this server. Please connect using your API token instead.`,
          type: "error",
        });
        openManualModal(provider);
      } else {
        const msg = e?.detail || e?.message || "OAuth not configured on the server.";
        setToast({ message: `Cannot start ${provider} OAuth: ${msg}`, type: "error" });
      }
      setOauthLoading(null);
    }
  };

  // Manual token connect (Notion, manual fallback)
  const handleManualConnect = async () => {
    if (!form.provider || !form.access_token) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.post("/integrations/connect", {
        provider: form.provider,
        access_token: form.access_token,
        workspace_name: form.workspace_name || undefined,
        base_url: form.base_url || undefined,
      });
      setConnectingProvider(null);
      setForm({ provider: "", access_token: "", workspace_name: "", base_url: "" });
      await fetchIntegrations();
      setToast({
        message: `${PROVIDER_META[form.provider]?.label || form.provider} connected successfully!`,
        type: "success",
      });
    } catch (e: any) {
      setFormError(e?.message || "Connection failed. Check your token and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDisconnect = async (id: number, provider: string) => {
    if (!confirm("Disconnect this integration? The access token will be removed.")) return;
    try {
      await api.delete(`/integrations/${id}`);
      await fetchIntegrations();
      setToast({
        message: `${PROVIDER_META[provider]?.label || provider} disconnected.`,
        type: "success",
      });
    } catch {
      setToast({ message: "Failed to disconnect.", type: "error" });
    }
  };

  const handleBrowse = async (provider: string, query = "") => {
    setBrowsingProvider(provider);
    setPagesLoading(true);
    setPages([]);
    try {
      const data = (await api.get(
        `/integrations/${provider}/pages${query ? `?query=${encodeURIComponent(query)}` : ""}`
      )) as any;
      setPages(data.items || []);
    } catch (e: any) {
      setToast({ message: `Failed to fetch pages: ${e?.message || "Unknown error"}`, type: "error" });
    } finally {
      setPagesLoading(false);
    }
  };

  const handleImport = async (provider: string, item: PageItem) => {
    setImportingId(item.id);
    try {
      await api.post(`/integrations/${provider}/import`, {
        external_id: item.id,
        title: item.title,
      });
      setImportedIds((prev) => new Set([...prev, item.id]));
      setToast({ message: `"${item.title}" imported as a document.`, type: "success" });
    } catch (e: any) {
      setToast({ message: `Import failed: ${e?.message || "Unknown error"}`, type: "error" });
    } finally {
      setImportingId(null);
    }
  };

  const activeIntegrations = integrations.filter((i) => i.is_active);
  const providerMap = Object.fromEntries(activeIntegrations.map((i) => [i.provider, i]));

  const openManualModal = (provider: string) => {
    setForm({ provider, access_token: "", workspace_name: "", base_url: "" });
    setFormError(null);
    setConnectingProvider(provider);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-gradient-to-br from-blue-500 to-teal-500 rounded-lg">
          <Link2 className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Integrations</h1>
          <p className="text-sm text-gray-500">
            Connect external documentation sources and import content directly
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-gray-400 py-8">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : (
        <>
          {/* Provider Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Object.entries(PROVIDER_META).map(([provider, meta]) => {
              const connected = providerMap[provider];
              const comingSoon = provider === "sharepoint";
              // GitHub shows a special "Code Repos" badge when connected
              const isOAuthLoading = oauthLoading === provider;

              return (
                <div
                  key={provider}
                  className="bg-white border rounded-xl p-5 shadow-sm flex flex-col gap-3"
                >
                  {/* Provider header */}
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${meta.color}`}>
                      {meta.label}
                    </span>
                    {connected ? (
                      <Badge className="bg-green-100 text-green-700 text-xs">
                        <CheckCircle2 className="w-3 h-3 mr-1" /> Connected
                      </Badge>
                    ) : comingSoon ? (
                      <Badge className="bg-gray-100 text-gray-500 text-xs">Coming Soon</Badge>
                    ) : (
                      <Badge className="bg-gray-100 text-gray-500 text-xs">Not connected</Badge>
                    )}
                  </div>

                  <p className="text-xs text-gray-500">{meta.description}</p>

                  {/* Connected workspace info */}
                  {connected && (
                    <div className="text-xs text-gray-500 space-y-0.5 bg-gray-50 rounded-lg p-2.5">
                      {connected.workspace_name && (
                        <p className="font-semibold text-gray-800">{connected.workspace_name}</p>
                      )}
                      {connected.workspace_id && (
                        <p className="text-gray-400">ID: {connected.workspace_id}</p>
                      )}
                      {connected.last_synced_at && (
                        <p>Last synced: {new Date(connected.last_synced_at).toLocaleString()}</p>
                      )}
                      {connected.sync_error && (
                        <p className="text-red-500 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" />
                          {connected.sync_error.slice(0, 80)}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 mt-auto pt-1">
                    {connected ? (
                      <>
                        {provider === "github" ? (
                          <Link href="/dashboard/code?add=github" className="flex-1">
                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full h-8 text-xs gap-1"
                            >
                              <GitBranch className="w-3.5 h-3.5" /> Add Repo
                            </Button>
                          </Link>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 h-8 text-xs gap-1"
                            onClick={() => handleBrowse(provider)}
                          >
                            <FileText className="w-3.5 h-3.5" /> Browse
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs text-red-600 hover:bg-red-50 border-red-200"
                          onClick={() => handleDisconnect(connected.id, provider)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </>
                    ) : meta.useOAuth ? (
                      <div className="flex flex-col gap-1.5 w-full">
                        {/* Primary: OAuth button */}
                        <Button
                          size="sm"
                          className="w-full h-8 text-xs gap-1.5 bg-blue-600 hover:bg-blue-700"
                          disabled={comingSoon || isOAuthLoading}
                          onClick={() => handleOAuthConnect(provider)}
                        >
                          {isOAuthLoading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <LogIn className="w-3.5 h-3.5" />
                          )}
                          {isOAuthLoading ? "Redirecting…" : meta.oauthLabel}
                        </Button>
                        {/* Secondary: manual token fallback */}
                        <button
                          className="text-[10px] text-gray-400 hover:text-gray-600 underline text-center"
                          onClick={() => openManualModal(provider)}
                        >
                          Use API token instead
                        </button>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        className="flex-1 h-8 text-xs bg-blue-600 hover:bg-blue-700 gap-1"
                        disabled={comingSoon}
                        onClick={() => openManualModal(provider)}
                      >
                        <Plus className="w-3.5 h-3.5" />
                        {comingSoon ? "Coming Soon" : "Connect"}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* ── JIRA Deep Sync Config Panel ── */}
          {providerMap["jira"] && (
            <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
              <button
                onClick={() => setShowJiraConfig(!showJiraConfig)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Settings2 className="w-4 h-4 text-blue-600" />
                  <span className="text-sm font-semibold text-gray-800">Jira Sync Configuration</span>
                  {jiraSyncStatus?.item_count > 0 && (
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
                      {jiraSyncStatus.item_count} items synced
                    </span>
                  )}
                  {jiraSyncStatus?.last_synced_at && (
                    <span className="text-xs text-gray-400">
                      Last sync: {new Date(jiraSyncStatus.last_synced_at).toLocaleString()}
                    </span>
                  )}
                </div>
                {showJiraConfig ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
              </button>

              {showJiraConfig && (
                <div className="px-5 pb-5 space-y-4 border-t pt-4">
                  <p className="text-xs text-gray-500">
                    Configure which Jira projects to sync. Once synced, epics and stories train the Brain
                    (knowledge graph) and become available for JIRA-aware validation.
                  </p>

                  {/* Project keys */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1.5">
                      Project Keys to Sync
                    </label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={jiraKeyInput}
                        onChange={(e) => setJiraKeyInput(e.target.value.toUpperCase())}
                        onKeyDown={(e) => { if (e.key === "Enter") addJiraProjectKey(); }}
                        placeholder="e.g. PROJ"
                        className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400 font-mono uppercase"
                      />
                      <Button size="sm" variant="outline" className="h-8 text-xs" onClick={addJiraProjectKey}>
                        <Plus className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                    {jiraProjectKeys.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {jiraProjectKeys.map((k) => (
                          <span key={k} className="inline-flex items-center gap-1 text-xs font-mono bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                            {k}
                            <button onClick={() => removeJiraProjectKey(k)} className="hover:opacity-70">
                              <XCircle className="w-3 h-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Sync frequency */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1.5">Sync Frequency</label>
                    <select
                      value={jiraSyncFreq}
                      onChange={(e) => setJiraSyncFreq(e.target.value)}
                      className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                    >
                      <option value="manual">Manual only</option>
                      <option value="hourly">Every hour</option>
                      <option value="daily">Daily</option>
                    </select>
                  </div>

                  {/* Advanced: custom AC field */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1.5">
                      Acceptance Criteria Field
                      <span className="ml-1 text-gray-400 font-normal">(advanced — leave blank for default)</span>
                    </label>
                    <input
                      type="text"
                      value={jiraAcField}
                      onChange={(e) => setJiraAcField(e.target.value)}
                      placeholder="customfield_10100"
                      className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 font-mono focus:outline-none focus:ring-2 focus:ring-blue-400"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      The Jira custom field name that stores acceptance criteria for your stories.
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3 pt-1">
                    <Button
                      className="bg-blue-600 hover:bg-blue-700 text-xs h-8 gap-1.5"
                      disabled={jiraProjectKeys.length === 0 || jiraSavingConfig}
                      onClick={handleSaveJiraConfig}
                    >
                      {jiraSavingConfig ? (
                        <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving…</>
                      ) : (
                        <><Database className="w-3.5 h-3.5" /> Save Config</>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      className="text-xs h-8 gap-1.5 border-blue-300 text-blue-700 hover:bg-blue-50"
                      disabled={jiraProjectKeys.length === 0 || jiraSyncing}
                      onClick={handleJiraSync}
                    >
                      {jiraSyncing ? (
                        <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Syncing…</>
                      ) : (
                        <><Zap className="w-3.5 h-3.5" /> Sync Now</>
                      )}
                    </Button>
                  </div>

                  {jiraSyncStatus?.sync_error && (
                    <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                      <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                      {jiraSyncStatus.sync_error}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Page / Channel Browser */}
          {browsingProvider && (
            <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b bg-gray-50">
                <h2 className="text-sm font-semibold text-gray-800">
                  Browse {PROVIDER_META[browsingProvider]?.label}{" "}
                  {browsingProvider === "slack" ? "Channels" : "Pages"}
                </h2>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => {
                    setBrowsingProvider(null);
                    setPages([]);
                    setPageQuery("");
                  }}
                >
                  <XCircle className="w-4 h-4" />
                </Button>
              </div>

              {/* Search */}
              <div className="px-5 py-3 border-b flex gap-2">
                <input
                  type="text"
                  value={pageQuery}
                  onChange={(e) => setPageQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleBrowse(browsingProvider, pageQuery);
                  }}
                  placeholder={
                    browsingProvider === "slack" ? "Filter channels…" : "Search pages…"
                  }
                  className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 gap-1 text-xs"
                  onClick={() => handleBrowse(browsingProvider, pageQuery)}
                >
                  <RefreshCw className="w-3.5 h-3.5" /> Search
                </Button>
              </div>

              {/* Item list */}
              <div className="divide-y max-h-96 overflow-y-auto">
                {pagesLoading ? (
                  <div className="flex items-center gap-2 text-sm text-gray-400 py-6 px-5">
                    <Loader2 className="w-4 h-4 animate-spin" /> Fetching…
                  </div>
                ) : pages.length === 0 ? (
                  <p className="text-sm text-gray-400 py-6 px-5 text-center">
                    No results. Try a different search term.
                  </p>
                ) : (
                  pages.map((item) => {
                    const isImported = importedIds.has(item.id);
                    const isImporting = importingId === item.id;
                    return (
                      <div
                        key={item.id}
                        className="flex items-center justify-between px-5 py-3 hover:bg-gray-50"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-800 truncate">{item.title}</p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {item.topic
                              ? item.topic.slice(0, 60)
                              : item.updated_at
                              ? new Date(item.updated_at).toLocaleDateString()
                              : "—"}
                            {item.member_count != null && (
                              <span className="ml-2">{item.member_count} members</span>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                          {item.url && (
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-gray-400 hover:text-gray-600"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          )}
                          <Button
                            size="sm"
                            variant={isImported ? "outline" : "default"}
                            className={`h-7 text-xs gap-1 ${
                              isImported
                                ? "text-green-600 border-green-300"
                                : "bg-blue-600 hover:bg-blue-700"
                            }`}
                            disabled={isImported || isImporting}
                            onClick={() => handleImport(browsingProvider, item)}
                          >
                            {isImporting ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : isImported ? (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" /> Imported
                              </>
                            ) : (
                              <>
                                <Download className="w-3.5 h-3.5" /> Import
                              </>
                            )}
                          </Button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Manual Token Modal */}
      {connectingProvider && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  Connect {PROVIDER_META[connectingProvider]?.label}
                </h2>
                {OAUTH_PROVIDERS.has(connectingProvider) && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    Manual token — for service accounts or CI environments
                  </p>
                )}
              </div>
              <button
                onClick={() => setConnectingProvider(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                {formError}
              </div>
            )}

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {PROVIDER_META[connectingProvider]?.tokenLabel} *
                </label>
                <input
                  type="password"
                  value={form.access_token}
                  onChange={(e) => setForm({ ...form, access_token: e.target.value })}
                  placeholder={PROVIDER_META[connectingProvider]?.tokenPlaceholder}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                  autoFocus
                />
              </div>

              {connectingProvider === "jira" && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Jira Base URL * (e.g. https://company.atlassian.net)
                  </label>
                  <input
                    type="url"
                    value={form.base_url}
                    onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                    placeholder="https://yourcompany.atlassian.net"
                    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Workspace Name (optional)
                </label>
                <input
                  type="text"
                  value={form.workspace_name}
                  onChange={(e) => setForm({ ...form, workspace_name: e.target.value })}
                  placeholder="My Workspace"
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button variant="outline" className="flex-1" onClick={() => setConnectingProvider(null)}>
                Cancel
              </Button>
              <Button
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                disabled={
                  !form.access_token ||
                  (connectingProvider === "jira" && !form.base_url) ||
                  submitting
                }
                onClick={handleManualConnect}
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Connecting…
                  </>
                ) : (
                  "Connect"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function IntegrationsPage() {
  return <Suspense fallback={<div className="flex h-screen items-center justify-center"><div className="animate-spin h-8 w-8 border-2 border-indigo-600 rounded-full border-t-transparent" /></div>}><IntegrationsContent /></Suspense>;
}
