/**
 * Organization Settings Page
 * For CXO/Admin users only
 *
 * Features:
 * - Tenant/Organization configuration
 * - Subscription tier management
 * - Organization-wide settings
 */

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  Building2,
  Users,
  CreditCard,
  Settings as SettingsIcon,
  Save,
  CheckCircle2,
  ArrowLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";

export default function OrganizationSettingsPage() {
  const router = useRouter();
  const { tenant, isCXO } = useAuth();
  
  // State
  const [name, setName] = useState(tenant?.name || "");
  const [subdomain, setSubdomain] = useState(tenant?.subdomain || "");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  // Redirect if not CXO
  useEffect(() => {
    if (!isCXO()) {
      router.push("/dashboard");
    }
  }, [isCXO, router]);

  useEffect(() => {
    if (tenant) {
      setName(tenant.name);
      setSubdomain(tenant.subdomain);
    }
  }, [tenant]);

  const handleSave = async () => {
    setIsLoading(true);
    setSuccess(false);
    setError("");

    try {
      await api.put("/tenants/me/", { name });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.detail || "Failed to update organization settings");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isCXO()) {
    return null;
  }

  return (
    <AppLayout>
      <div className="space-y-6 max-w-4xl">
        {/* Back Link */}
        <Link
          href="/users"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to User Management
        </Link>

        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Organization Settings</h1>
          <p className="mt-2 text-gray-600">
            Manage your organization configuration and settings
          </p>
        </div>

        {/* Overview Cards */}
        <div className="grid gap-6 sm:grid-cols-3">
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Subscription</p>
                <p className="mt-2 text-2xl font-bold text-gray-900 capitalize">
                  {tenant?.tier || "Free"}
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
                <p className="text-sm font-medium text-gray-600">User Limit</p>
                <p className="mt-2 text-2xl font-bold text-gray-900">
                  {tenant?.max_users || 10}
                </p>
              </div>
              <div className="rounded-lg bg-green-100 p-3">
                <Users className="h-5 w-5 text-green-600" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Status</p>
                <p className="mt-2 text-2xl font-bold text-gray-900 capitalize">
                  {tenant?.status || "Active"}
                </p>
              </div>
              <div className="rounded-lg bg-purple-100 p-3">
                <SettingsIcon className="h-5 w-5 text-purple-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Settings Form */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                Organization Information
              </h3>
              <p className="mt-1 text-sm text-gray-600">
                Update your organization details
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="orgName">Organization Name</Label>
                <Input
                  id="orgName"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My Company"
                  className="mt-2"
                />
              </div>

              <div>
                <Label htmlFor="subdomain">Subdomain</Label>
                <div className="mt-2 flex items-center space-x-2">
                  <Input
                    id="subdomain"
                    type="text"
                    value={subdomain}
                    disabled
                    className="flex-1"
                  />
                  <span className="text-sm text-gray-500">.dokydoc.com</span>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Subdomain cannot be changed after registration
                </p>
              </div>

              <div>
                <Label htmlFor="billingType">Billing Type</Label>
                <Input
                  id="billingType"
                  type="text"
                  value={tenant?.billing_type || "prepaid"}
                  disabled
                  className="mt-2 capitalize"
                />
              </div>
            </div>

            {error && (
              <div className="rounded-md bg-red-50 p-3">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {success && (
              <div className="flex items-center space-x-2 rounded-md bg-green-50 p-3">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <p className="text-sm text-green-800">Settings saved successfully!</p>
              </div>
            )}

            <div className="flex justify-end">
              <Button
                onClick={handleSave}
                disabled={isLoading || !name}
              >
                <Save className="mr-2 h-4 w-4" />
                {isLoading ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </div>
        </div>

        {/* Quick Links */}
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Quick Actions
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <Link
              href="/users"
              className="flex items-center space-x-3 rounded-lg border p-4 hover:bg-gray-50 transition-colors"
            >
              <Users className="h-5 w-5 text-gray-600" />
              <div>
                <p className="font-medium text-gray-900">Manage Users</p>
                <p className="text-sm text-gray-600">Add and manage team members</p>
              </div>
            </Link>

            <Link
              href="/billing"
              className="flex items-center space-x-3 rounded-lg border p-4 hover:bg-gray-50 transition-colors"
            >
              <CreditCard className="h-5 w-5 text-gray-600" />
              <div>
                <p className="font-medium text-gray-900">Billing & Usage</p>
                <p className="text-sm text-gray-600">View billing and usage details</p>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
