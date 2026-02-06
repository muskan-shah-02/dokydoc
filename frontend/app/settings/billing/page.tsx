/**
 * Billing Settings Page
 * Sprint 2 Refinement - FR-07: Billing Module
 *
 * Features:
 * - CXO/Admin only access
 * - View current plan and billing type
 * - Balance management (prepaid)
 * - Usage metrics and costs
 * - Plan upgrade/switch options
 */

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  CreditCard,
  TrendingUp,
  DollarSign,
  ArrowLeft,
  CheckCircle2,
  X,
  AlertTriangle,
  Zap,
  Cpu,
  Calculator,
  Info,
  ExternalLink,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";

export default function BillingSettingsPage() {
  const router = useRouter();
  const { tenant, isCXO, isAdmin } = useAuth();

  const [billingData, setBillingData] = useState<any>(null);
  const [pricingData, setPricingData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddBalanceModal, setShowAddBalanceModal] = useState(false);
  const [showUpgradePlanModal, setShowUpgradePlanModal] = useState(false);
  const [showSwitchTypeModal, setShowSwitchTypeModal] = useState(false);
  const [showPricingDetails, setShowPricingDetails] = useState(false);

  // Redirect if not CXO or Admin
  useEffect(() => {
    if (!isCXO() && !isAdmin()) {
      router.push("/dashboard");
    }
  }, [isCXO, isAdmin, router]);

  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    setIsLoading(true);
    try {
      const [billingResponse, pricingResponse] = await Promise.all([
        api.get("/billing/usage"),
        api.get("/billing/pricing"),
      ]);
      setBillingData(billingResponse);
      setPricingData(pricingResponse);
    } catch (error) {
      console.error("Failed to load billing data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddBalance = async (amount: number) => {
    try {
      await api.post("/billing/topup", { amount_inr: amount });
      setShowAddBalanceModal(false);
      loadBillingData();
    } catch (error: any) {
      alert(error.detail || "Failed to add balance");
    }
  };

  const handleUpgradePlan = async (newTier: string) => {
    try {
      await api.put("/tenants/me", { tier: newTier });
      setShowUpgradePlanModal(false);
      loadBillingData();
      window.location.reload();
    } catch (error: any) {
      alert(error.detail || "Failed to upgrade plan");
    }
  };

  const handleSwitchBillingType = async (newType: string) => {
    try {
      await api.put("/tenants/me", { billing_type: newType });
      setShowSwitchTypeModal(false);
      loadBillingData();
    } catch (error: any) {
      alert(error.detail || "Failed to switch billing type");
    }
  };

  if (!isCXO() && !isAdmin()) {
    return null;
  }

  const isPrepaid = billingData?.billing_type === "prepaid";
  const limitUsagePercentage = billingData?.limit_usage_percentage || 0;
  const isNearLimit = limitUsagePercentage > 80;

  return (
    <AppLayout>
      <div className="space-y-6 max-w-4xl">
        {/* Back Link */}
        <Link
          href="/settings"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Settings
        </Link>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Billing & Usage</h1>
            <p className="mt-2 text-gray-600">
              Monitor billing, usage metrics, and manage your subscription
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/settings/billing/analytics">
              <Button variant="outline">
                <BarChart3 className="mr-2 h-4 w-4" />
                View Analytics
              </Button>
            </Link>
            {isPrepaid && (
              <Button onClick={() => setShowAddBalanceModal(true)}>
                <DollarSign className="mr-2 h-4 w-4" />
                Add Balance
              </Button>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
              <p className="text-gray-600">Loading billing data...</p>
            </div>
          </div>
        ) : !billingData ? (
          <div className="rounded-lg border bg-white p-12 text-center shadow-sm">
            <AlertTriangle className="mx-auto h-12 w-12 text-yellow-500" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              Failed to load billing data
            </h3>
            <p className="mt-2 text-gray-600">
              Please try again later or contact support.
            </p>
            <Button onClick={loadBillingData} className="mt-4">
              Retry
            </Button>
          </div>
        ) : (
          <>
            {/* Overview Cards */}
            <div className="grid gap-6 sm:grid-cols-3">
              {/* Current Plan */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Current Plan</p>
                    <p className="mt-2 text-2xl font-bold text-gray-900 capitalize">
                      {tenant?.tier || "Free"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-purple-100 p-3">
                    <Zap className="h-5 w-5 text-purple-600" />
                  </div>
                </div>
                <Button
                  onClick={() => setShowUpgradePlanModal(true)}
                  variant="outline"
                  size="sm"
                  className="mt-4 w-full"
                >
                  Upgrade Plan
                </Button>
              </div>

              {/* Billing Type */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Billing Type</p>
                    <p className="mt-2 text-2xl font-bold text-gray-900 capitalize">
                      {billingData.billing_type}
                    </p>
                  </div>
                  <div className="rounded-lg bg-blue-100 p-3">
                    <CreditCard className="h-5 w-5 text-blue-600" />
                  </div>
                </div>
                <Button
                  onClick={() => setShowSwitchTypeModal(true)}
                  variant="outline"
                  size="sm"
                  className="mt-4 w-full"
                >
                  Switch Type
                </Button>
              </div>

              {/* Balance or Monthly Cost */}
              {isPrepaid ? (
                <div className="rounded-lg border bg-white p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Balance</p>
                      <p className="mt-2 text-2xl font-bold text-gray-900">
                        ₹{billingData.balance_inr?.toFixed(2) || "0.00"}
                      </p>
                    </div>
                    <div className={`rounded-lg p-3 ${billingData.low_balance_alert ? 'bg-yellow-100' : 'bg-green-100'}`}>
                      <DollarSign className={`h-5 w-5 ${billingData.low_balance_alert ? 'text-yellow-600' : 'text-green-600'}`} />
                    </div>
                  </div>
                  {billingData.low_balance_alert && (
                    <p className="mt-2 text-xs text-yellow-700">Low balance warning</p>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border bg-white p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-600">This Month</p>
                      <p className="mt-2 text-2xl font-bold text-gray-900">
                        ₹{billingData.current_month_cost?.toFixed(2) || "0.00"}
                      </p>
                    </div>
                    <div className="rounded-lg bg-green-100 p-3">
                      <TrendingUp className="h-5 w-5 text-green-600" />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Usage Section */}
            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Usage Overview</h3>

              <div className="grid gap-6 md:grid-cols-2">
                <div>
                  <Label className="text-gray-600">Current Month Cost</Label>
                  <div className="mt-2 flex items-baseline space-x-2">
                    <p className="text-2xl font-bold text-gray-900">
                      ₹{billingData.current_month_cost?.toFixed(2) || "0.00"}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    {new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}
                  </p>
                </div>

                <div>
                  <Label className="text-gray-600">Last 30 Days</Label>
                  <div className="mt-2 flex items-baseline space-x-2">
                    <p className="text-2xl font-bold text-gray-900">
                      ₹{billingData.last_30_days_cost?.toFixed(2) || "0.00"}
                    </p>
                    <TrendingUp className="h-5 w-5 text-gray-400" />
                  </div>
                  <p className="mt-1 text-xs text-gray-500">Rolling 30-day period</p>
                </div>
              </div>

              {/* Monthly Limit Progress */}
              {billingData.monthly_limit_inr && (
                <div className="mt-6 pt-6 border-t">
                  <div className="mb-3 flex items-center justify-between">
                    <Label className="text-gray-600">Monthly Spending Limit</Label>
                    {isNearLimit && (
                      <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-700">
                        Near Limit
                      </span>
                    )}
                  </div>

                  <div className="mb-2 flex items-baseline justify-between">
                    <span className="text-sm text-gray-600">
                      ₹{billingData.current_month_cost?.toFixed(2) || "0.00"} / ₹{billingData.monthly_limit_inr?.toFixed(2)}
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {limitUsagePercentage.toFixed(0)}%
                    </span>
                  </div>

                  <div className="h-3 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={`h-full transition-all ${
                        isNearLimit ? "bg-red-600" : "bg-green-600"
                      }`}
                      style={{ width: `${Math.min(limitUsagePercentage, 100)}%` }}
                    />
                  </div>

                  {billingData.limit_remaining_inr !== undefined && (
                    <p className="mt-2 text-sm text-gray-600">
                      ₹{billingData.limit_remaining_inr.toFixed(2)} remaining this month
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Pricing Transparency Section */}
            {pricingData && (
              <div className="rounded-lg border bg-white shadow-sm overflow-hidden">
                <button
                  onClick={() => setShowPricingDetails(!showPricingDetails)}
                  className="w-full p-6 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-100 p-2">
                      <Calculator className="h-5 w-5 text-purple-600" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">Pricing Transparency</h3>
                      <p className="text-sm text-gray-600">
                        Model: {pricingData.model} • Input: ${pricingData.rates_usd?.input_per_1m_tokens}/1M • Output: ${pricingData.rates_usd?.output_per_1m_tokens}/1M
                      </p>
                    </div>
                  </div>
                  <div className={`transform transition-transform ${showPricingDetails ? "rotate-180" : ""}`}>
                    <svg className="h-5 w-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {showPricingDetails && (
                  <div className="p-6 pt-0 space-y-6 border-t bg-gray-50/50">
                    {/* Pricing Table */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                        <Cpu className="h-4 w-4" />
                        AI Token Pricing ({pricingData.model})
                      </h4>
                      <div className="overflow-hidden rounded-lg border bg-white">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-100">
                            <tr>
                              <th className="px-4 py-3 text-left font-semibold text-gray-700">Factor</th>
                              <th className="px-4 py-3 text-right font-semibold text-gray-700">USD Rate</th>
                              <th className="px-4 py-3 text-right font-semibold text-gray-700">INR Rate</th>
                              <th className="px-4 py-3 text-left font-semibold text-gray-700">Description</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y">
                            <tr>
                              <td className="px-4 py-3 font-medium text-gray-900">Input Tokens</td>
                              <td className="px-4 py-3 text-right text-gray-700">${pricingData.rates_usd?.input_per_1m_tokens} / 1M</td>
                              <td className="px-4 py-3 text-right text-gray-700">₹{pricingData.rates_inr?.input_per_1m_tokens?.toFixed(2)} / 1M</td>
                              <td className="px-4 py-3 text-gray-600">Prompts, documents, context</td>
                            </tr>
                            <tr className="bg-yellow-50">
                              <td className="px-4 py-3 font-medium text-gray-900 flex items-center gap-2">
                                Output Tokens
                                <span className="px-1.5 py-0.5 text-xs font-medium bg-yellow-200 text-yellow-800 rounded">8.3x</span>
                              </td>
                              <td className="px-4 py-3 text-right font-semibold text-yellow-700">${pricingData.rates_usd?.output_per_1m_tokens} / 1M</td>
                              <td className="px-4 py-3 text-right font-semibold text-yellow-700">₹{pricingData.rates_inr?.output_per_1m_tokens?.toFixed(2)} / 1M</td>
                              <td className="px-4 py-3 text-yellow-700">AI responses, JSON results ⚠️</td>
                            </tr>
                            <tr>
                              <td className="px-4 py-3 font-medium text-gray-900">Cached Tokens</td>
                              <td className="px-4 py-3 text-right text-green-600">${pricingData.rates_usd?.cached_per_1m_tokens} / 1M</td>
                              <td className="px-4 py-3 text-right text-green-600">₹{pricingData.rates_inr?.cached_per_1m_tokens?.toFixed(2)} / 1M</td>
                              <td className="px-4 py-3 text-gray-600">90% discount if cached</td>
                            </tr>
                            <tr>
                              <td className="px-4 py-3 font-medium text-gray-900">Search Queries</td>
                              <td className="px-4 py-3 text-right text-gray-700">${pricingData.rates_usd?.search_per_1k_queries} / 1K</td>
                              <td className="px-4 py-3 text-right text-gray-700">₹{pricingData.rates_inr?.search_per_1k_queries?.toFixed(2)} / 1K</td>
                              <td className="px-4 py-3 text-gray-600">Grounding (not currently used)</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Formula */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                        <Info className="h-4 w-4" />
                        Cost Calculation Formula
                      </h4>
                      <div className="rounded-lg bg-slate-900 p-4 font-mono text-sm text-slate-300 overflow-x-auto">
                        <div className="text-slate-500 mb-2">// Step 1: Calculate USD cost</div>
                        <div className="text-green-400">cost_usd = (input_tokens / 1,000,000 × ${pricingData.rates_usd?.input_per_1m_tokens})</div>
                        <div className="text-yellow-400 ml-10">+ (output_tokens / 1,000,000 × ${pricingData.rates_usd?.output_per_1m_tokens})</div>
                        <div className="text-slate-500 mt-3 mb-2">// Step 2: Convert to INR</div>
                        <div className="text-blue-400">cost_inr = cost_usd × {pricingData.exchange_rate?.usd_to_inr}</div>
                      </div>
                    </div>

                    {/* Example Calculation */}
                    {pricingData.formula?.example && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900 mb-3">Example Calculation</h4>
                        <div className="rounded-lg border bg-white p-4">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-gray-500">Input Tokens</p>
                              <p className="font-semibold text-gray-900">{pricingData.formula.example.input_tokens.toLocaleString()}</p>
                            </div>
                            <div>
                              <p className="text-gray-500">Output Tokens</p>
                              <p className="font-semibold text-gray-900">{pricingData.formula.example.output_tokens.toLocaleString()}</p>
                            </div>
                            <div>
                              <p className="text-gray-500">Total (USD)</p>
                              <p className="font-semibold text-gray-900">${pricingData.formula.example.total_usd?.toFixed(6)}</p>
                            </div>
                            <div>
                              <p className="text-gray-500">Total (INR)</p>
                              <p className="font-semibold text-green-600">₹{pricingData.formula.example.total_inr?.toFixed(4)}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Exchange Rate & Source */}
                    <div className="flex items-center justify-between text-sm text-gray-500 pt-2 border-t">
                      <div className="flex items-center gap-4">
                        <span>Exchange Rate: $1 = ₹{pricingData.exchange_rate?.usd_to_inr}</span>
                        <span>•</span>
                        <span>Last Updated: {pricingData.last_updated}</span>
                      </div>
                      <a
                        href="https://ai.google.dev/pricing"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-blue-600 hover:text-blue-700"
                      >
                        Google AI Pricing <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>

                    {/* Warning Note */}
                    <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-4">
                      <div className="flex gap-3">
                        <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
                        <div className="text-sm">
                          <p className="font-medium text-yellow-800">Output tokens are 8.3x more expensive than input tokens!</p>
                          <p className="mt-1 text-yellow-700">
                            AI-generated responses (JSON analysis results, summaries) cost significantly more than the document text you send.
                            This is the primary cost driver for document analysis.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Plan Details */}
            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Plan Details</h3>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-sm text-gray-600">Max Users</p>
                  <p className="mt-1 text-xl font-bold text-gray-900">{tenant?.max_users || 10}</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-sm text-gray-600">Max Documents</p>
                  <p className="mt-1 text-xl font-bold text-gray-900">{tenant?.max_documents || 100}</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-sm text-gray-600">Status</p>
                  <p className="mt-1 text-xl font-bold text-green-600 capitalize">{tenant?.status || "Active"}</p>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {isPrepaid && (
                  <Button
                    onClick={() => setShowAddBalanceModal(true)}
                    variant="outline"
                    className="justify-start"
                  >
                    <DollarSign className="mr-2 h-4 w-4" />
                    Add Balance
                  </Button>
                )}
                <Button
                  onClick={() => setShowUpgradePlanModal(true)}
                  variant="outline"
                  className="justify-start"
                >
                  <Zap className="mr-2 h-4 w-4" />
                  Upgrade Plan
                </Button>
                <Button
                  onClick={() => setShowSwitchTypeModal(true)}
                  variant="outline"
                  className="justify-start"
                >
                  <CreditCard className="mr-2 h-4 w-4" />
                  Switch Billing Type
                </Button>
              </div>
            </div>
          </>
        )}

        {/* Modals */}
        {showAddBalanceModal && billingData && (
          <AddBalanceModal
            onClose={() => setShowAddBalanceModal(false)}
            onConfirm={handleAddBalance}
            currentBalance={billingData.balance_inr || 0}
          />
        )}

        {showUpgradePlanModal && (
          <UpgradePlanModal
            currentTier={tenant?.tier || "free"}
            onClose={() => setShowUpgradePlanModal(false)}
            onConfirm={handleUpgradePlan}
          />
        )}

        {showSwitchTypeModal && billingData && (
          <SwitchBillingTypeModal
            currentType={billingData.billing_type}
            currentBalance={billingData.balance_inr || 0}
            onClose={() => setShowSwitchTypeModal(false)}
            onConfirm={handleSwitchBillingType}
          />
        )}
      </div>
    </AppLayout>
  );
}

// ============================================================================
// Add Balance Modal
// ============================================================================

function AddBalanceModal({
  onClose,
  onConfirm,
  currentBalance,
}: {
  onClose: () => void;
  onConfirm: (amount: number) => void;
  currentBalance: number;
}) {
  const [amount, setAmount] = useState(1000);
  const [isLoading, setIsLoading] = useState(false);

  const handleConfirm = async () => {
    if (amount < 100) {
      alert("Minimum top-up amount is ₹100");
      return;
    }
    setIsLoading(true);
    await onConfirm(amount);
    setIsLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Add Balance</h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-4 rounded-lg bg-blue-50 p-3">
          <p className="text-sm text-gray-600">Current Balance</p>
          <p className="text-2xl font-bold text-gray-900">₹{currentBalance.toFixed(2)}</p>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="amount">Amount to Add (₹)</Label>
            <Input
              id="amount"
              type="number"
              min="100"
              step="100"
              value={amount}
              onChange={(e) => setAmount(parseInt(e.target.value) || 0)}
              className="mt-2"
            />
            <p className="mt-1 text-xs text-gray-500">Minimum: ₹100</p>
          </div>

          <div className="grid grid-cols-4 gap-2">
            {[500, 1000, 5000, 10000].map((quickAmount) => (
              <button
                key={quickAmount}
                onClick={() => setAmount(quickAmount)}
                className={`rounded-lg border p-2 text-sm font-medium transition-colors ${
                  amount === quickAmount
                    ? "border-blue-600 bg-blue-50 text-blue-600"
                    : "border-gray-300 hover:border-blue-300"
                }`}
              >
                ₹{quickAmount}
              </button>
            ))}
          </div>

          <div className="rounded-lg bg-green-50 p-3">
            <p className="text-sm text-gray-600">New Balance</p>
            <p className="text-xl font-bold text-green-700">
              ₹{(currentBalance + amount).toFixed(2)}
            </p>
          </div>

          <div className="flex space-x-3">
            <Button onClick={onClose} variant="outline" className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleConfirm} disabled={isLoading} className="flex-1">
              {isLoading ? "Adding..." : `Add ₹${amount}`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Upgrade Plan Modal
// ============================================================================

function UpgradePlanModal({
  currentTier,
  onClose,
  onConfirm,
}: {
  currentTier: string;
  onClose: () => void;
  onConfirm: (tier: string) => void;
}) {
  const [selectedTier, setSelectedTier] = useState(currentTier);
  const [isLoading, setIsLoading] = useState(false);

  const plans = [
    {
      id: "free",
      name: "Free",
      price: "₹0",
      features: ["Basic features", "Email support", "10 users", "100 documents"],
    },
    {
      id: "pro",
      name: "Pro",
      price: "₹999/mo",
      features: ["All Free features", "Priority support", "50 users", "1000 documents", "Advanced analytics"],
    },
    {
      id: "enterprise",
      name: "Enterprise",
      price: "₹4999/mo",
      features: ["All Pro features", "24/7 support", "500 users", "10000 documents", "Custom integrations", "SLA guarantee"],
    },
  ];

  const handleConfirm = async () => {
    if (selectedTier === currentTier) {
      alert("Please select a different plan");
      return;
    }
    setIsLoading(true);
    await onConfirm(selectedTier);
    setIsLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-4xl rounded-lg bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-semibold text-gray-900">Upgrade Plan</h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-3 mb-6">
          {plans.map((plan) => (
            <button
              key={plan.id}
              onClick={() => setSelectedTier(plan.id)}
              className={`rounded-lg border-2 p-4 text-left transition-all ${
                selectedTier === plan.id
                  ? "border-blue-600 bg-blue-50"
                  : "border-gray-200 hover:border-blue-300"
              } ${plan.id === currentTier ? "opacity-60" : ""}`}
              disabled={plan.id === currentTier}
            >
              <div className="mb-3">
                <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
                <p className="text-2xl font-bold text-blue-600">{plan.price}</p>
                {plan.id === currentTier && (
                  <span className="mt-2 inline-block rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium">
                    Current Plan
                  </span>
                )}
              </div>
              <ul className="space-y-2">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start text-sm text-gray-600">
                    <CheckCircle2 className="mr-2 h-4 w-4 flex-shrink-0 text-green-600" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </button>
          ))}
        </div>

        <div className="flex space-x-3">
          <Button onClick={onClose} variant="outline" className="flex-1">
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isLoading || selectedTier === currentTier} className="flex-1">
            {isLoading ? "Upgrading..." : `Upgrade to ${plans.find(p => p.id === selectedTier)?.name}`}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Switch Billing Type Modal
// ============================================================================

function SwitchBillingTypeModal({
  currentType,
  currentBalance,
  onClose,
  onConfirm,
}: {
  currentType: string;
  currentBalance: number;
  onClose: () => void;
  onConfirm: (type: string) => void;
}) {
  const [isLoading, setIsLoading] = useState(false);
  const newType = currentType === "prepaid" ? "postpaid" : "prepaid";

  const handleConfirm = async () => {
    setIsLoading(true);
    await onConfirm(newType);
    setIsLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            Switch to {newType === "prepaid" ? "Prepaid" : "Postpaid"}?
          </h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-4 space-y-3">
          <p className="text-sm text-gray-600">
            You're switching from <span className="font-medium capitalize">{currentType}</span> to{" "}
            <span className="font-medium capitalize">{newType}</span> billing.
          </p>

          {newType === "postpaid" ? (
            <div className="rounded-lg bg-blue-50 p-3">
              <h4 className="font-medium text-gray-900">Postpaid Benefits:</h4>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                <li>No upfront balance needed</li>
                <li>Billed monthly based on usage</li>
                <li>Set monthly spending limits</li>
                {currentBalance > 0 && <li>Current balance (₹{currentBalance.toFixed(2)}) will be credited</li>}
              </ul>
            </div>
          ) : (
            <div className="rounded-lg bg-green-50 p-3">
              <h4 className="font-medium text-gray-900">Prepaid Benefits:</h4>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                <li>Pay only for what you use</li>
                <li>No monthly bills</li>
                <li>Full cost control</li>
                <li>Top up anytime</li>
              </ul>
            </div>
          )}
        </div>

        <div className="flex space-x-3">
          <Button onClick={onClose} variant="outline" className="flex-1">
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isLoading} className="flex-1">
            {isLoading ? "Switching..." : `Switch to ${newType === "prepaid" ? "Prepaid" : "Postpaid"}`}
          </Button>
        </div>
      </div>
    </div>
  );
}
