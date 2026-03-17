"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
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
const OAUTH_PROVIDERS = new Set(["jira", "slack"]);

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
    description: "Import Confluence pages (coming soon)",
    tokenLabel: "API Token",
    tokenPlaceholder: "",
    useOAuth: false,
    oauthLabel: "",
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

export default function IntegrationsPage() {
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
      const msg = e?.detail || e?.message || "OAuth not configured on the server.";
      setToast({ message: `Cannot start ${provider} OAuth: ${msg}`, type: "error" });
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
              const comingSoon = provider === "confluence" || provider === "sharepoint";
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
                        <Button
                          size="sm"
                          variant="outline"
                          className="flex-1 h-8 text-xs gap-1"
                          onClick={() => handleBrowse(provider)}
                        >
                          <FileText className="w-3.5 h-3.5" /> Browse
                        </Button>
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
