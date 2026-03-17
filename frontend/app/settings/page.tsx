/**
 * Settings Page
 * Sprint 2 Extended - Multi-Tenancy Support
 *
 * Features:
 * - User profile settings
 * - Password change
 * - Tenant settings (CXO only)
 * - My permissions view
 */

"use client";

import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  Settings as SettingsIcon,
  User,
  Lock,
  Building2,
  Shield,
  Save,
  CheckCircle2,
  CreditCard,
  TrendingUp,
  DollarSign,
  X,
  Bell,
  Key,
  Trash2,
  Copy,
  Check,
  Eye,
  EyeOff,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  const { user, tenant, isCXO, permissions } = useAuth();
  const [activeTab, setActiveTab] = useState("profile");

  // Build tabs based on user role
  const tabs = [
    { id: "profile", label: "My Profile", icon: <User className="h-4 w-4" /> },
    { id: "password", label: "Password", icon: <Lock className="h-4 w-4" /> },
    { id: "permissions", label: "Permissions", icon: <Shield className="h-4 w-4" /> },
  ];

  // Notifications tab — available to all users
  tabs.push({
    id: "notifications",
    label: "Notifications",
    icon: <Bell className="h-4 w-4" />,
  });

  // API Keys tab — available to all users
  tabs.push({
    id: "api-keys",
    label: "API Keys",
    icon: <Key className="h-4 w-4" />,
  });

  // Add Organization and Billing tabs for CXO
  if (isCXO()) {
    tabs.push({
      id: "organization",
      label: "Organization",
      icon: <Building2 className="h-4 w-4" />,
    });
    tabs.push({
      id: "billing",
      label: "Billing & Usage",
      icon: <CreditCard className="h-4 w-4" />,
    });
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          <p className="mt-2 text-gray-600">
            Manage your account and organization settings
          </p>
        </div>

        {/* Tabs */}
        <div className="border-b">
          <nav className="-mb-px flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 border-b-2 px-1 py-4 text-sm font-medium ${
                  activeTab === tab.id
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          {activeTab === "profile" && <ProfileTab user={user} />}
          {activeTab === "password" && <PasswordTab />}
          {activeTab === "permissions" && <PermissionsTab permissions={permissions} />}
          {activeTab === "notifications" && <NotificationPrefsTab />}
          {activeTab === "api-keys" && <ApiKeysTab />}
          {activeTab === "organization" && isCXO() && <TenantTab tenant={tenant} />}
          {activeTab === "billing" && isCXO() && <BillingTab />}
        </div>
      </div>
    </AppLayout>
  );
}

// ============================================================================
// Profile Tab
// ============================================================================

function ProfileTab({ user }: { user: any }) {
  const [email, setEmail] = useState(user?.email || "");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setIsLoading(true);
    setSuccess(false);

    try {
      await api.put("/users/me/", { email });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      console.error("Failed to update profile:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Profile Information</h3>
        <p className="mt-1 text-sm text-gray-600">
          Update your account information
        </p>
      </div>

      <div className="max-w-xl space-y-4">
        <div>
          <Label htmlFor="email">Email Address</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2"
          />
        </div>

        <div>
          <Label>Roles</Label>
          <div className="mt-2 flex flex-wrap gap-2">
            {user?.roles.map((role: string) => (
              <span
                key={role}
                className={`rounded px-3 py-1 text-sm font-medium ${
                  role === "CXO"
                    ? "bg-purple-100 text-purple-700"
                    : "bg-gray-100 text-gray-700"
                }`}
              >
                {role}
              </span>
            ))}
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Contact your administrator to change roles
          </p>
        </div>

        <div>
          <Label>Account Created</Label>
          <p className="mt-2 text-sm text-gray-700">
            {new Date(user?.created_at).toLocaleDateString()}
          </p>
        </div>

        {success && (
          <div className="flex items-center space-x-2 rounded-md bg-green-50 p-3 text-green-800">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Profile updated successfully</span>
          </div>
        )}

        <Button onClick={handleSave} disabled={isLoading}>
          <Save className="mr-2 h-4 w-4" />
          {isLoading ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Password Tab
// ============================================================================

function PasswordTab() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setError(null);
    setSuccess(false);

    // Validation
    if (!currentPassword || !newPassword || !confirmPassword) {
      setError("All fields are required");
      return;
    }

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match");
      return;
    }

    setIsLoading(true);

    try {
      await api.post("/users/me/password/", {
        current_password: currentPassword,
        new_password: newPassword,
      });

      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.detail || "Failed to change password");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Change Password</h3>
        <p className="mt-1 text-sm text-gray-600">
          Update your password to keep your account secure
        </p>
      </div>

      <div className="max-w-xl space-y-4">
        <div>
          <Label htmlFor="currentPassword">Current Password</Label>
          <Input
            id="currentPassword"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="mt-2"
          />
        </div>

        <div>
          <Label htmlFor="newPassword">New Password</Label>
          <Input
            id="newPassword"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-2"
          />
          <p className="mt-1 text-sm text-gray-500">
            Must be at least 8 characters
          </p>
        </div>

        <div>
          <Label htmlFor="confirmPassword">Confirm New Password</Label>
          <Input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-2"
          />
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-3">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {success && (
          <div className="flex items-center space-x-2 rounded-md bg-green-50 p-3 text-green-800">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Password changed successfully</span>
          </div>
        )}

        <Button onClick={handleSave} disabled={isLoading}>
          <Save className="mr-2 h-4 w-4" />
          {isLoading ? "Changing..." : "Change Password"}
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Tenant Tab (CXO Only)
// ============================================================================

function TenantTab({ tenant }: { tenant: any }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Organization Settings</h3>
        <p className="mt-1 text-sm text-gray-600">
          View your organization details and configuration
        </p>
      </div>

      <div className="max-w-xl space-y-4">
        <div>
          <Label htmlFor="orgName">Organization Name</Label>
          <div className="mt-2 flex items-center space-x-2">
            <Input
              id="orgName"
              type="text"
              value={tenant?.name || ""}
              disabled
              className="flex-1 bg-gray-50"
            />
            <Lock className="h-4 w-4 text-gray-400" />
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Organization name cannot be changed. Contact support if needed.
          </p>
        </div>

        <div>
          <Label>Subdomain</Label>
          <div className="mt-2 rounded-md bg-gray-50 p-3">
            <p className="text-sm font-medium text-gray-900">
              {tenant?.subdomain}.dokydoc.com
            </p>
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Subdomain cannot be changed after registration
          </p>
        </div>

        <div>
          <Label>Plan</Label>
          <div className="mt-2 flex items-center space-x-3">
            <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium capitalize text-blue-700">
              {tenant?.tier || "Free"}
            </span>
            <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium capitalize text-gray-700">
              {tenant?.billing_type || "Prepaid"}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Max Users</Label>
            <p className="mt-2 text-sm text-gray-700">{tenant?.max_users}</p>
          </div>

          <div>
            <Label>Max Documents</Label>
            <p className="mt-2 text-sm text-gray-700">{tenant?.max_documents}</p>
          </div>
        </div>

        <div>
          <Label>Status</Label>
          <div className="mt-2">
            <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-sm font-medium capitalize text-green-700">
              {tenant?.status || "Active"}
            </span>
          </div>
        </div>

        <div className="rounded-md bg-blue-50 p-3">
          <p className="text-sm text-blue-800">
            Organization settings are read-only. To make changes, please contact your account manager or support.
          </p>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Billing Tab (CXO Only)
// ============================================================================

function BillingTab() {
  const { tenant } = useAuth();
  const [billingData, setBillingData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddBalanceModal, setShowAddBalanceModal] = useState(false);
  const [showUpgradePlanModal, setShowUpgradePlanModal] = useState(false);
  const [showSwitchTypeModal, setShowSwitchTypeModal] = useState(false);

  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    setIsLoading(true);
    try {
      const data = await api.get("/billing/usage");
      setBillingData(data);
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
      loadBillingData(); // Refresh billing data
    } catch (error: any) {
      alert(error.detail || "Failed to add balance");
      console.error("Failed to add balance:", error);
    }
  };

  const handleUpgradePlan = async (newTier: string) => {
    try {
      await api.put("/tenants/me", { tier: newTier });
      setShowUpgradePlanModal(false);
      loadBillingData(); // Refresh
      window.location.reload(); // Reload to update tenant context
    } catch (error: any) {
      alert(error.detail || "Failed to upgrade plan");
      console.error("Failed to upgrade plan:", error);
    }
  };

  const handleSwitchBillingType = async (newType: string) => {
    try {
      await api.put("/tenants/me", { billing_type: newType });
      setShowSwitchTypeModal(false);
      loadBillingData(); // Refresh
    } catch (error: any) {
      alert(error.detail || "Failed to switch billing type");
      console.error("Failed to switch billing type:", error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
          <p className="text-gray-600">Loading billing data...</p>
        </div>
      </div>
    );
  }

  if (!billingData) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Failed to load billing data</p>
      </div>
    );
  }

  const isPrepaid = billingData.billing_type === "prepaid";
  const limitUsagePercentage = billingData.limit_usage_percentage || 0;
  const isNearLimit = limitUsagePercentage > 80;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Billing & Usage</h3>
        <p className="mt-1 text-sm text-gray-600">
          Monitor your organization's billing and usage metrics
        </p>
      </div>

      {/* Current Plan */}
      <div className="rounded-lg border p-4">
        <div className="mb-3 flex items-center justify-between">
          <Label>Current Plan</Label>
          <Button onClick={() => setShowUpgradePlanModal(true)} variant="outline" size="sm">
            Upgrade Plan
          </Button>
        </div>
        <div className="flex items-center space-x-3">
          <span className="rounded-full bg-purple-100 px-4 py-2 text-lg font-bold capitalize text-purple-700">
            {tenant?.tier || "Free"}
          </span>
          <div className="text-sm text-gray-600">
            <div>{tenant?.max_users || 10} users • {tenant?.max_documents || 100} documents</div>
          </div>
        </div>
      </div>

      {/* Billing Type */}
      <div className="rounded-lg bg-blue-50 p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">Billing Type</p>
            <p className="text-xl font-bold capitalize text-gray-900">
              {billingData.billing_type}
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <CreditCard className="h-8 w-8 text-blue-600" />
            <Button onClick={() => setShowSwitchTypeModal(true)} variant="outline" size="sm">
              Switch Type
            </Button>
          </div>
        </div>
      </div>

      {/* Balance (Prepaid Only) */}
      {isPrepaid && (
        <div className="rounded-lg border p-4">
          <div className="mb-2 flex items-center justify-between">
            <Label>Current Balance</Label>
            {billingData.low_balance_alert && (
              <span className="rounded-full bg-yellow-100 px-3 py-1 text-xs font-medium text-yellow-700">
                Low Balance
              </span>
            )}
          </div>
          <div className="flex items-baseline space-x-2">
            <p className="text-3xl font-bold text-gray-900">
              ₹{billingData.balance_inr?.toFixed(2) || "0.00"}
            </p>
            <DollarSign className="h-6 w-6 text-gray-400" />
          </div>
          {billingData.low_balance_alert && (
            <p className="mt-2 text-sm text-yellow-700">
              Your balance is running low. Consider adding funds to continue using services.
            </p>
          )}
        </div>
      )}

      {/* Current Month Cost */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-4">
          <Label>Current Month Cost</Label>
          <div className="mt-2 flex items-baseline space-x-2">
            <p className="text-2xl font-bold text-gray-900">
              ₹{billingData.current_month_cost?.toFixed(2) || "0.00"}
            </p>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            {new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}
          </p>
        </div>

        <div className="rounded-lg border p-4">
          <Label>Last 30 Days Cost</Label>
          <div className="mt-2 flex items-baseline space-x-2">
            <p className="text-2xl font-bold text-gray-900">
              ₹{billingData.last_30_days_cost?.toFixed(2) || "0.00"}
            </p>
            <TrendingUp className="h-5 w-5 text-gray-400" />
          </div>
          <p className="mt-1 text-xs text-gray-500">Rolling 30-day period</p>
        </div>
      </div>

      {/* Monthly Limit */}
      {billingData.monthly_limit_inr && (
        <div className="rounded-lg border p-4">
          <div className="mb-3 flex items-center justify-between">
            <Label>Monthly Spending Limit</Label>
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

      {/* Usage Breakdown */}
      <div className="rounded-lg border p-4">
        <h4 className="mb-3 font-medium text-gray-900">Usage Summary</h4>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Billing Type</span>
            <span className="text-sm font-medium capitalize text-gray-900">
              {billingData.billing_type}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Tenant ID</span>
            <span className="text-sm font-medium text-gray-900">
              #{billingData.tenant_id}
            </span>
          </div>
          {isPrepaid && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Balance Status</span>
                <span
                  className={`text-sm font-medium ${
                    billingData.low_balance_alert ? "text-yellow-600" : "text-green-600"
                  }`}
                >
                  {billingData.low_balance_alert ? "Low Balance" : "Healthy"}
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Top-up Button (Prepaid Only) */}
      {isPrepaid && (
        <div className="rounded-lg bg-gray-50 p-4">
          <p className="mb-3 text-sm text-gray-600">
            Need more balance? Add funds to your prepaid account.
          </p>
          <Button className="w-full" onClick={() => setShowAddBalanceModal(true)}>
            <DollarSign className="mr-2 h-4 w-4" />
            Add Balance
          </Button>
        </div>
      )}

      {/* Add Balance Modal */}
      {showAddBalanceModal && (
        <AddBalanceModal
          onClose={() => setShowAddBalanceModal(false)}
          onConfirm={handleAddBalance}
          currentBalance={billingData.balance_inr || 0}
        />
      )}

      {/* Upgrade Plan Modal */}
      {showUpgradePlanModal && (
        <UpgradePlanModal
          currentTier={tenant?.tier || "free"}
          onClose={() => setShowUpgradePlanModal(false)}
          onConfirm={handleUpgradePlan}
        />
      )}

      {/* Switch Billing Type Modal */}
      {showSwitchTypeModal && (
        <SwitchBillingTypeModal
          currentType={billingData.billing_type}
          currentBalance={billingData.balance_inr || 0}
          onClose={() => setShowSwitchTypeModal(false)}
          onConfirm={handleSwitchBillingType}
        />
      )}
    </div>
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
      users: 10,
      documents: 100,
      features: ["Basic features", "Email support", "10 users", "100 documents"],
    },
    {
      id: "pro",
      name: "Pro",
      price: "₹999/mo",
      users: 50,
      documents: 1000,
      features: ["All Free features", "Priority support", "50 users", "1000 documents", "Advanced analytics"],
    },
    {
      id: "enterprise",
      name: "Enterprise",
      price: "₹4999/mo",
      users: 500,
      documents: 10000,
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
                <li>✓ No upfront balance needed</li>
                <li>✓ Billed monthly based on usage</li>
                <li>✓ Set monthly spending limits</li>
                {currentBalance > 0 && <li>✓ Current balance (₹{currentBalance.toFixed(2)}) will be credited</li>}
              </ul>
            </div>
          ) : (
            <div className="rounded-lg bg-green-50 p-3">
              <h4 className="font-medium text-gray-900">Prepaid Benefits:</h4>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                <li>✓ Pay only for what you use</li>
                <li>✓ No monthly bills</li>
                <li>✓ Full cost control</li>
                <li>✓ Top up anytime</li>
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

// ============================================================================
// Permissions Tab
// ============================================================================

function PermissionsTab({ permissions }: { permissions: string[] }) {
  // Group permissions by category
  const permissionsByCategory = permissions.reduce((acc, permission) => {
    const [category] = permission.split(":");
    if (!acc[category]) acc[category] = [];
    acc[category].push(permission);
    return acc;
  }, {} as Record<string, string[]>);

  const categoryLabels: Record<string, string> = {
    document: "Documents",
    code: "Code Components",
    analysis: "Analysis",
    validation: "Validation",
    task: "Tasks",
    billing: "Billing",
    user: "Users",
    tenant: "Organization",
  };

  const permissionLabels: Record<string, string> = {
    read: "View",
    write: "Create/Edit",
    delete: "Delete",
    analyze: "Analyze",
    view: "View",
    run: "Run",
    create: "Create",
    update: "Update",
    assign: "Assign",
    comment: "Comment",
    manage: "Manage",
    invite: "Invite",
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">My Permissions</h3>
        <p className="mt-1 text-sm text-gray-600">
          View all permissions granted to your account
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {Object.entries(permissionsByCategory).map(([category, perms]) => (
          <div key={category} className="rounded-lg border p-4">
            <h4 className="mb-3 font-medium text-gray-900">
              {categoryLabels[category] || category}
            </h4>
            <div className="space-y-2">
              {perms.map((permission) => {
                const [, action] = permission.split(":");
                return (
                  <div key={permission} className="flex items-center space-x-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    <span className="text-sm text-gray-700">
                      {permissionLabels[action] || action}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {permissions.length === 0 && (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <Shield className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-sm font-medium text-gray-900">
            No permissions assigned
          </h3>
          <p className="mt-2 text-sm text-gray-600">
            Contact your administrator to request access
          </p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Notification Preferences Tab
// ============================================================================

const PREF_FIELDS: { key: string; label: string; description: string }[] = [
  { key: "analysis_complete", label: "Analysis Complete", description: "Notify when document or repository analysis finishes successfully" },
  { key: "analysis_failed", label: "Analysis Failed", description: "Notify when an analysis run encounters errors" },
  { key: "validation_alert", label: "Validation Alerts", description: "Notify when mismatches or validation issues are detected" },
  { key: "mention", label: "Mentions", description: "Notify when you are mentioned in a task or comment" },
  { key: "system", label: "System Messages", description: "Notify for system-level announcements and updates" },
];

function NotificationPrefsTab() {
  const [prefs, setPrefs] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    api.get("/notifications/preferences")
      .then((data: any) => setPrefs(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (key: string, value: boolean) => {
    setPrefs((prev) => ({ ...prev, [key]: value }));
    setSaving(key);
    try {
      await api.put("/notifications/preferences", { [key]: value });
    } catch {
      // Revert on failure
      setPrefs((prev) => ({ ...prev, [key]: !value }));
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Notification Preferences</h3>
        <p className="mt-1 text-sm text-gray-600">
          Control which in-app notifications you receive. Changes are saved automatically.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          Loading preferences…
        </div>
      ) : (
        <div className="space-y-4 max-w-xl">
          {PREF_FIELDS.map(({ key, label, description }) => (
            <div key={key} className="flex items-start justify-between gap-4 py-3 border-b last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-900">{label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{description}</p>
              </div>
              <button
                role="switch"
                aria-checked={!!prefs[key]}
                disabled={saving === key}
                onClick={() => handleToggle(key, !prefs[key])}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none ${
                  prefs[key] ? "bg-blue-600" : "bg-gray-200"
                } ${saving === key ? "opacity-50" : ""}`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${
                    prefs[key] ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// API Keys Tab
// ============================================================================

interface ApiKeyItem {
  id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  request_count: number;
  created_at: string;
}

function ApiKeysTab() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [expiresDays, setExpiresDays] = useState<string>("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [revoking, setRevoking] = useState<number | null>(null);

  const fetchKeys = async () => {
    try {
      const data = await api.get("/api-keys/") as any;
      setKeys(data.api_keys || []);
    } catch {
      console.error("Failed to load API keys");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchKeys(); }, []);

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    setCreating(true);
    try {
      const data = await api.post("/api-keys/", {
        name: newKeyName.trim(),
        expires_days: expiresDays ? parseInt(expiresDays, 10) : null,
      }) as any;
      setRevealedKey(data.raw_key);
      setNewKeyName("");
      setExpiresDays("");
      await fetchKeys();
    } catch {
      alert("Failed to create API key.");
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: number) => {
    if (!confirm("Revoke this API key? This cannot be undone.")) return;
    setRevoking(id);
    try {
      await api.delete(`/api-keys/${id}`);
      setKeys((prev) => prev.filter((k) => k.id !== id));
    } catch {
      alert("Failed to revoke key.");
    } finally {
      setRevoking(null);
    }
  };

  const copyKey = () => {
    if (!revealedKey) return;
    navigator.clipboard.writeText(revealedKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">API Keys</h3>
        <p className="mt-1 text-sm text-gray-600">
          Create keys for programmatic access. Pass them as{" "}
          <code className="bg-gray-100 px-1 py-0.5 rounded text-xs font-mono">X-API-Key</code>{" "}
          header in requests.
        </p>
      </div>

      {/* Revealed key banner */}
      {revealedKey && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg space-y-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-green-800">
            <Key className="w-4 h-4" />
            API key created — copy it now. It will not be shown again.
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono bg-white border border-green-300 rounded px-3 py-2 break-all select-all">
              {revealedKey}
            </code>
            <Button size="sm" variant="outline" onClick={copyKey} className="gap-1.5 flex-shrink-0">
              {copiedKey ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedKey ? "Copied" : "Copy"}
            </Button>
          </div>
          <button onClick={() => setRevealedKey(null)} className="text-xs text-green-700 hover:underline">
            I've saved it — dismiss
          </button>
        </div>
      )}

      {/* Create form */}
      <div className="p-4 border border-dashed rounded-lg space-y-3 max-w-xl">
        <p className="text-sm font-medium text-gray-700">Create new key</p>
        <div className="flex gap-2">
          <Input
            placeholder="Key name (e.g. CI/CD Pipeline)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            className="flex-1"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <Input
            placeholder="Expires (days, optional)"
            value={expiresDays}
            onChange={(e) => setExpiresDays(e.target.value)}
            type="number"
            min={1}
            max={365}
            className="w-40"
          />
          <Button onClick={handleCreate} disabled={creating || !newKeyName.trim()} className="flex-shrink-0">
            {creating ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Key className="w-4 h-4 mr-1.5" />}
            {creating ? "Creating…" : "Create"}
          </Button>
        </div>
      </div>

      {/* Key list */}
      {loading ? (
        <div className="text-sm text-gray-500 py-4">Loading keys…</div>
      ) : keys.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <Key className="w-10 h-10 mx-auto mb-2" />
          <p className="text-sm">No API keys yet</p>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Name</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Key</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Created</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Last used</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Requests</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Expires</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {keys.map((k) => (
                <tr key={k.id} className={`hover:bg-gray-50 ${!k.is_active ? "opacity-50" : ""}`}>
                  <td className="px-4 py-2 font-medium text-gray-900">{k.name}</td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">{k.key_prefix}…</td>
                  <td className="px-4 py-2 text-gray-500">{new Date(k.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2 text-gray-500">{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "—"}</td>
                  <td className="px-4 py-2 text-gray-700">{k.request_count.toLocaleString()}</td>
                  <td className="px-4 py-2 text-gray-500">{k.expires_at ? new Date(k.expires_at).toLocaleDateString() : "Never"}</td>
                  <td className="px-4 py-2 text-right">
                    {k.is_active && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={() => handleRevoke(k.id)}
                        disabled={revoking === k.id}
                      >
                        <Trash2 className="w-3.5 h-3.5 mr-1" />
                        Revoke
                      </Button>
                    )}
                    {!k.is_active && <span className="text-xs text-gray-400">Revoked</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
        <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-amber-700">
          API keys carry the same permissions as your account. Never share them publicly. Revoke unused keys promptly.
        </p>
      </div>
    </div>
  );
}
