/**
 * Billing Dashboard Page
 * Sprint 2 Extended - Multi-Tenancy & RBAC Support
 *
 * CXO-only page for managing billing:
 * - View current plan and balance/usage
 * - Usage statistics and breakdown
 * - Add balance (prepaid)
 * - Transaction history
 * - Plan upgrade options
 */

"use client";

import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  CreditCard,
  DollarSign,
  TrendingUp,
  Calendar,
  FileText,
  Code,
  Zap,
  Users,
  ArrowUpRight,
  Plus,
  Download,
  CheckCircle2,
  Crown,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface BillingData {
  balance: number;
  usage_this_month: number;
  transactions: Transaction[];
  usage_breakdown: UsageBreakdown;
}

interface Transaction {
  id: number;
  type: string;
  amount: number;
  description: string;
  created_at: string;
}

interface UsageBreakdown {
  documents: number;
  code_components: number;
  ai_analysis: number;
  validations: number;
}

export default function BillingPage() {
  const router = useRouter();
  const { user, tenant, isCXO } = useAuth();

  // Redirect if not CXO
  useEffect(() => {
    if (!isCXO()) {
      router.push("/dashboard");
    }
  }, [isCXO, router]);

  const [isLoading, setIsLoading] = useState(true);
  const [billingData, setBillingData] = useState<BillingData | null>(null);
  const [addBalanceOpen, setAddBalanceOpen] = useState(false);
  const [balanceAmount, setBalanceAmount] = useState("");
  const [addBalanceLoading, setAddBalanceLoading] = useState(false);

  const isPrepaid = tenant?.billing_type === "prepaid";

  // Load billing data
  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    setIsLoading(true);
    try {
      const response = await api.get<BillingData>("/billing/");
      setBillingData(response);
    } catch (error) {
      console.error("Failed to load billing data:", error);
      // Set empty data for demo
      setBillingData({
        balance: 0,
        usage_this_month: 0,
        transactions: [],
        usage_breakdown: {
          documents: 0,
          code_components: 0,
          ai_analysis: 0,
          validations: 0,
        },
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Add balance (prepaid only)
  const handleAddBalance = async () => {
    const amount = parseFloat(balanceAmount);
    if (isNaN(amount) || amount <= 0) {
      alert("Please enter a valid amount");
      return;
    }

    setAddBalanceLoading(true);
    try {
      await api.post("/billing/add-balance/", { amount });
      setAddBalanceOpen(false);
      setBalanceAmount("");
      loadBillingData();
    } catch (error) {
      console.error("Failed to add balance:", error);
      alert("Failed to add balance. Please try again.");
    } finally {
      setAddBalanceLoading(false);
    }
  };

  if (!isCXO()) {
    return null;
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Billing & Usage</h1>
            <p className="mt-2 text-gray-600">
              Monitor your spending and manage your subscription
            </p>
          </div>

          {isPrepaid && (
            <Button onClick={() => setAddBalanceOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Balance
            </Button>
          )}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center p-12">
            <div className="text-center">
              <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
              <p className="text-gray-600">Loading billing data...</p>
            </div>
          </div>
        ) : (
          <>
            {/* Overview Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Current Plan</p>
                    <p className="mt-2 text-2xl font-bold capitalize text-gray-900">
                      {tenant?.tier || "Free"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-purple-100 p-3">
                    <Crown className="h-5 w-5 text-purple-600" />
                  </div>
                </div>
              </div>

              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">
                      {isPrepaid ? "Balance" : "This Month"}
                    </p>
                    <p className="mt-2 text-2xl font-bold text-gray-900">
                      ${isPrepaid ? billingData?.balance.toFixed(2) : billingData?.usage_this_month.toFixed(2)}
                    </p>
                  </div>
                  <div className="rounded-lg bg-green-100 p-3">
                    <DollarSign className="h-5 w-5 text-green-600" />
                  </div>
                </div>
              </div>

              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Billing Type</p>
                    <p className="mt-2 text-2xl font-bold capitalize text-gray-900">
                      {tenant?.billing_type || "Prepaid"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-blue-100 p-3">
                    <CreditCard className="h-5 w-5 text-blue-600" />
                  </div>
                </div>
              </div>

              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Transactions</p>
                    <p className="mt-2 text-2xl font-bold text-gray-900">
                      {billingData?.transactions.length || 0}
                    </p>
                  </div>
                  <div className="rounded-lg bg-orange-100 p-3">
                    <TrendingUp className="h-5 w-5 text-orange-600" />
                  </div>
                </div>
              </div>
            </div>

            {/* Usage Breakdown */}
            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Usage Breakdown</h2>
                <span className="text-sm text-gray-600">Current Month</span>
              </div>

              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <UsageCard
                  label="Documents"
                  value={billingData?.usage_breakdown.documents || 0}
                  cost="$0.00"
                  icon={<FileText className="h-5 w-5" />}
                  color="blue"
                />
                <UsageCard
                  label="Code Components"
                  value={billingData?.usage_breakdown.code_components || 0}
                  cost="$0.00"
                  icon={<Code className="h-5 w-5" />}
                  color="green"
                />
                <UsageCard
                  label="AI Analysis"
                  value={billingData?.usage_breakdown.ai_analysis || 0}
                  cost="$0.00"
                  icon={<Zap className="h-5 w-5" />}
                  color="yellow"
                />
                <UsageCard
                  label="Validations"
                  value={billingData?.usage_breakdown.validations || 0}
                  cost="$0.00"
                  icon={<CheckCircle2 className="h-5 w-5" />}
                  color="purple"
                />
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              {/* Plan Details */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <h2 className="mb-6 text-lg font-semibold text-gray-900">Plan Details</h2>

                <div className="space-y-4">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Plan Tier</span>
                    <span className="font-medium capitalize text-gray-900">
                      {tenant?.tier || "Free"}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-600">Max Users</span>
                    <span className="font-medium text-gray-900">
                      {tenant?.max_users || "Unlimited"}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-600">Max Documents</span>
                    <span className="font-medium text-gray-900">
                      {tenant?.max_documents || "Unlimited"}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-600">Billing Type</span>
                    <span className="font-medium capitalize text-gray-900">
                      {tenant?.billing_type || "Prepaid"}
                    </span>
                  </div>

                  {!isPrepaid && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Next Billing Date</span>
                      <span className="font-medium text-gray-900">N/A</span>
                    </div>
                  )}
                </div>

                <div className="mt-6">
                  <Button className="w-full">
                    <ArrowUpRight className="mr-2 h-4 w-4" />
                    Upgrade Plan
                  </Button>
                </div>
              </div>

              {/* Recent Transactions */}
              <div className="rounded-lg border bg-white p-6 shadow-sm">
                <div className="mb-6 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-gray-900">
                    Recent Transactions
                  </h2>
                  <Button variant="outline" size="sm">
                    <Download className="mr-2 h-4 w-4" />
                    Export
                  </Button>
                </div>

                {billingData?.transactions && billingData.transactions.length > 0 ? (
                  <div className="space-y-4">
                    {billingData.transactions.slice(0, 5).map((transaction) => (
                      <div
                        key={transaction.id}
                        className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0"
                      >
                        <div className="flex items-center space-x-3">
                          <div
                            className={`rounded-lg p-2 ${
                              transaction.type === "credit"
                                ? "bg-green-100"
                                : "bg-red-100"
                            }`}
                          >
                            {transaction.type === "credit" ? (
                              <Plus className="h-4 w-4 text-green-600" />
                            ) : (
                              <DollarSign className="h-4 w-4 text-red-600" />
                            )}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-900">
                              {transaction.description}
                            </p>
                            <p className="text-xs text-gray-500">
                              {new Date(transaction.created_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <span
                          className={`font-medium ${
                            transaction.type === "credit"
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {transaction.type === "credit" ? "+" : "-"}$
                          {transaction.amount.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <Calendar className="h-12 w-12 text-gray-400" />
                    <h3 className="mt-4 text-sm font-medium text-gray-900">
                      No transactions yet
                    </h3>
                    <p className="mt-1 text-sm text-gray-600">
                      Transaction history will appear here
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Limits & Usage */}
            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <h2 className="mb-6 text-lg font-semibold text-gray-900">
                Resource Limits
              </h2>

              <div className="space-y-6">
                <ResourceLimit
                  label="Users"
                  used={1}
                  limit={tenant?.max_users || 100}
                  icon={<Users className="h-5 w-5" />}
                />
                <ResourceLimit
                  label="Documents"
                  used={0}
                  limit={tenant?.max_documents || 1000}
                  icon={<FileText className="h-5 w-5" />}
                />
                <ResourceLimit
                  label="Code Components"
                  used={0}
                  limit={10000}
                  icon={<Code className="h-5 w-5" />}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Add Balance Dialog */}
      {addBalanceOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">Add Balance</h2>
              <button
                onClick={() => setAddBalanceOpen(false)}
                className="rounded-md p-1 hover:bg-gray-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="balanceAmount">Amount (USD)</Label>
                <div className="relative mt-2">
                  <DollarSign className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
                  <Input
                    id="balanceAmount"
                    type="number"
                    placeholder="0.00"
                    value={balanceAmount}
                    onChange={(e) => setBalanceAmount(e.target.value)}
                    className="h-11 pl-10"
                    min="0"
                    step="0.01"
                  />
                </div>
              </div>

              <div className="rounded-lg bg-blue-50 p-4">
                <p className="text-sm text-blue-900">
                  Your current balance: ${billingData?.balance.toFixed(2) || "0.00"}
                </p>
                {balanceAmount && parseFloat(balanceAmount) > 0 && (
                  <p className="mt-2 text-sm font-medium text-blue-900">
                    New balance: $
                    {((billingData?.balance || 0) + parseFloat(balanceAmount)).toFixed(2)}
                  </p>
                )}
              </div>

              <div className="flex space-x-3">
                <Button
                  onClick={() => setAddBalanceOpen(false)}
                  variant="outline"
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleAddBalance}
                  disabled={addBalanceLoading}
                  className="flex-1"
                >
                  {addBalanceLoading ? "Processing..." : "Add Balance"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}

// ============================================================================
// Utility Components
// ============================================================================

function UsageCard({
  label,
  value,
  cost,
  icon,
  color,
}: {
  label: string;
  value: number;
  cost: string;
  icon: React.ReactNode;
  color: string;
}) {
  const colorClasses = {
    blue: "bg-blue-100 text-blue-600",
    green: "bg-green-100 text-green-600",
    yellow: "bg-yellow-100 text-yellow-600",
    purple: "bg-purple-100 text-purple-600",
  };

  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div className={`rounded-lg p-2 ${colorClasses[color as keyof typeof colorClasses]}`}>
          {icon}
        </div>
      </div>
      <p className="mt-3 text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-sm text-gray-600">{label}</p>
      <p className="mt-1 text-sm font-medium text-gray-900">{cost}</p>
    </div>
  );
}

function ResourceLimit({
  label,
  used,
  limit,
  icon,
}: {
  label: string;
  used: number;
  limit: number;
  icon: React.ReactNode;
}) {
  const percentage = Math.min(Math.round((used / limit) * 100), 100);
  const isWarning = percentage >= 80;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="text-gray-500">{icon}</div>
          <span className="text-sm font-medium text-gray-900">{label}</span>
        </div>
        <span className="text-sm text-gray-600">
          {used} / {limit}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-200">
        <div
          className={`h-full ${isWarning ? "bg-orange-600" : "bg-blue-600"}`}
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
      {isWarning && (
        <p className="mt-1 text-xs text-orange-600">
          Approaching limit - consider upgrading
        </p>
      )}
    </div>
  );
}
