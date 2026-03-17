"use client";

import { useState, useEffect } from "react";
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
}

interface ConnectFormState {
  provider: string;
  access_token: string;
  workspace_name: string;
  base_url: string;
}

const PROVIDER_META: Record<
  string,
  { label: string; color: string; description: string; tokenLabel: string; tokenPlaceholder: string }
> = {
  notion: {
    label: "Notion",
    color: "bg-gray-900 text-white",
    description: "Import pages from your Notion workspace",
    tokenLabel: "Notion Integration Token",
    tokenPlaceholder: "secret_...",
  },
  jira: {
    label: "Jira",
    color: "bg-blue-600 text-white",
    description: "Import issues and epics from Jira Cloud",
    tokenLabel: "Jira API Token",
    tokenPlaceholder: "Your Atlassian API token",
  },
  confluence: {
    label: "Confluence",
    color: "bg-blue-500 text-white",
    description: "Import Confluence pages (coming soon)",
    tokenLabel: "API Token",
    tokenPlaceholder: "",
  },
  sharepoint: {
    label: "SharePoint",
    color: "bg-teal-600 text-white",
    description: "Import SharePoint documents (coming soon)",
    tokenLabel: "Access Token",
    tokenPlaceholder: "",
  },
};

// ----- Main Page -----

export default function IntegrationsPage() {
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
  const [error, setError] = useState<string | null>(null);

  // Page browser state
  const [browsingProvider, setBrowsingProvider] = useState<string | null>(null);
  const [pages, setPages] = useState<PageItem[]>([]);
  const [pagesLoading, setPagesLoading] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [importedIds, setImportedIds] = useState<Set<string>>(new Set());
  const [pageQuery, setPageQuery] = useState("");

  const fetchIntegrations = async () => {
    setLoading(true);
    try {
      const data = (await api.get("/integrations/")) as any;
      setIntegrations(data.integrations || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const handleConnect = async () => {
    if (!form.provider || !form.access_token) return;
    setSubmitting(true);
    setError(null);
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
    } catch (e: any) {
      setError(e?.message || "Connection failed. Check your token and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDisconnect = async (id: number) => {
    if (!confirm("Disconnect this integration? The access token will be removed.")) return;
    try {
      await api.delete(`/integrations/${id}`);
      await fetchIntegrations();
    } catch {
      alert("Failed to disconnect.");
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
      alert(`Failed to fetch pages: ${e?.message || "Unknown error"}`);
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
    } catch (e: any) {
      alert(`Import failed: ${e?.message || "Unknown error"}`);
    } finally {
      setImportingId(null);
    }
  };

  const activeIntegrations = integrations.filter((i) => i.is_active);
  const providerMap = Object.fromEntries(activeIntegrations.map((i) => [i.provider, i]));

  const openConnectModal = (provider: string) => {
    setForm({ provider, access_token: "", workspace_name: "", base_url: "" });
    setError(null);
    setConnectingProvider(provider);
  };

  return (
    <div className="p-6 space-y-6">
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
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {Object.entries(PROVIDER_META).map(([provider, meta]) => {
              const connected = providerMap[provider];
              const comingSoon = provider === "confluence" || provider === "sharepoint";
              return (
                <div
                  key={provider}
                  className="bg-white border rounded-xl p-5 shadow-sm flex flex-col gap-3"
                >
                  {/* Provider header */}
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-xs font-semibold px-2.5 py-1 rounded-full ${meta.color}`}
                    >
                      {meta.label}
                    </span>
                    {connected ? (
                      <Badge className="bg-green-100 text-green-700 text-xs">Connected</Badge>
                    ) : comingSoon ? (
                      <Badge className="bg-gray-100 text-gray-500 text-xs">Coming Soon</Badge>
                    ) : (
                      <Badge className="bg-gray-100 text-gray-500 text-xs">Not connected</Badge>
                    )}
                  </div>

                  <p className="text-xs text-gray-500">{meta.description}</p>

                  {/* Connected details */}
                  {connected && (
                    <div className="text-xs text-gray-500 space-y-0.5">
                      {connected.workspace_name && (
                        <p className="font-medium text-gray-700">{connected.workspace_name}</p>
                      )}
                      {connected.last_synced_at && (
                        <p>Last synced: {new Date(connected.last_synced_at).toLocaleString()}</p>
                      )}
                      {connected.sync_error && (
                        <p className="text-red-500 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" />
                          {connected.sync_error.slice(0, 60)}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 mt-auto pt-2">
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
                          onClick={() => handleDisconnect(connected.id)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </>
                    ) : (
                      <Button
                        size="sm"
                        className="flex-1 h-8 text-xs bg-blue-600 hover:bg-blue-700 gap-1"
                        disabled={comingSoon}
                        onClick={() => openConnectModal(provider)}
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

          {/* Page Browser */}
          {browsingProvider && (
            <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b bg-gray-50">
                <h2 className="text-sm font-semibold text-gray-800">
                  Browse {PROVIDER_META[browsingProvider]?.label} Pages
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
                  placeholder="Search pages…"
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

              {/* Page list */}
              <div className="divide-y max-h-96 overflow-y-auto">
                {pagesLoading ? (
                  <div className="flex items-center gap-2 text-sm text-gray-400 py-6 px-5">
                    <Loader2 className="w-4 h-4 animate-spin" /> Fetching pages…
                  </div>
                ) : pages.length === 0 ? (
                  <p className="text-sm text-gray-400 py-6 px-5 text-center">
                    No pages found. Try a different search term.
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
                            {item.updated_at
                              ? new Date(item.updated_at).toLocaleDateString()
                              : "—"}
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

      {/* Connect Modal */}
      {connectingProvider && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                Connect {PROVIDER_META[connectingProvider]?.label}
              </h2>
              <button
                onClick={() => setConnectingProvider(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                {error}
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
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setConnectingProvider(null)}
              >
                Cancel
              </Button>
              <Button
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                disabled={
                  !form.access_token ||
                  (connectingProvider === "jira" && !form.base_url) ||
                  submitting
                }
                onClick={handleConnect}
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
