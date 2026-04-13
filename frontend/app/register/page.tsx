/**
 * Tenant Registration Page
 * Sprint 2 Extended - Multi-Tenancy Support
 *
 * Features:
 * - Multi-step registration form
 * - Subdomain validation with real-time availability check
 * - Tier selection (Free, Pro, Enterprise)
 * - Admin user creation
 * - Auto-login after registration
 */

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  Building2,
  Globe,
  User,
  Mail,
  Lock,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  ChevronLeft,
  Loader2,
} from "lucide-react";

// Tier options
const TIERS = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    description: "Perfect for getting started",
    features: [
      "Up to 5 users",
      "100 documents",
      "Basic analysis",
      "Email support",
    ],
  },
  {
    id: "pro",
    name: "Professional",
    price: "$99/mo",
    description: "For growing teams",
    features: [
      "Up to 50 users",
      "5,000 documents",
      "Advanced analysis",
      "Priority support",
      "API access",
    ],
    popular: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    description: "For large organizations",
    features: [
      "Unlimited users",
      "Unlimited documents",
      "Custom AI models",
      "24/7 support",
      "Dedicated account manager",
      "SLA guarantee",
    ],
  },
];

export default function RegisterPage() {
  const router = useRouter();
  const { setAuthFromResponse } = useAuth();

  // Form state
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: Organization details
  const [orgName, setOrgName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [subdomainAvailable, setSubdomainAvailable] = useState<boolean | null>(
    null
  );
  const [checkingSubdomain, setCheckingSubdomain] = useState(false);

  // Step 1 extras
  const [companyWebsite, setCompanyWebsite] = useState("");

  // Step 2: Tier selection
  const [selectedTier, setSelectedTier] = useState("pro");

  // Step 3: Admin user
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  /**
   * Check subdomain availability with debouncing
   */
  useEffect(() => {
    if (!subdomain || subdomain.length < 3) {
      setSubdomainAvailable(null);
      return;
    }

    const timer = setTimeout(async () => {
      setCheckingSubdomain(true);
      try {
        // Call backend to check subdomain availability
        const response = await api.get<{ available: boolean }>(
          `/tenants/check-subdomain/${subdomain}`
        );
        setSubdomainAvailable(response.available);
      } catch (err) {
        console.error("Subdomain check failed:", err);
        setSubdomainAvailable(null);
      } finally {
        setCheckingSubdomain(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [subdomain]);

  /**
   * Validate subdomain format
   */
  const isValidSubdomain = (value: string): boolean => {
    // Must be 3-30 characters, alphanumeric and hyphens only, start/end with alphanumeric
    const regex = /^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$/;
    return regex.test(value);
  };

  /**
   * Handle organization name change (auto-generate subdomain)
   */
  const handleOrgNameChange = (value: string) => {
    setOrgName(value);

    // Auto-generate subdomain from org name if subdomain is empty
    if (!subdomain) {
      const generated = value
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .replace(/\s+/g, "-")
        .substring(0, 30);
      setSubdomain(generated);
    }
  };

  /**
   * Handle subdomain change
   */
  const handleSubdomainChange = (value: string) => {
    const cleaned = value.toLowerCase().replace(/[^a-z0-9-]/g, "");
    setSubdomain(cleaned);
  };

  /**
   * Validate current step
   */
  const canProceed = (): boolean => {
    if (step === 1) {
      return (
        orgName.trim().length >= 2 &&
        isValidSubdomain(subdomain) &&
        subdomainAvailable === true
      );
    }
    if (step === 2) {
      return selectedTier !== "";
    }
    if (step === 3) {
      return (
        adminEmail.includes("@") &&
        adminPassword.length >= 8 &&
        adminPassword === confirmPassword
      );
    }
    return false;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async () => {
    if (!canProceed()) return;

    setError(null);
    setIsLoading(true);

    try {
      // Register tenant
      const response = await api.post<{
        access_token: string;
        user: any;
        tenant: any;
      }>("/tenants/register", {
        name: orgName,
        subdomain: subdomain,
        tier: selectedTier,
        admin_email: adminEmail,
        admin_password: adminPassword,
        ...(companyWebsite.trim() && { company_website: companyWebsite.trim() }),
      });

      // Set auth state from registration response
      setAuthFromResponse(response.user, response.tenant, response.access_token);

      // Redirect to onboarding wizard for new tenants
      router.push("/dashboard/onboarding");
    } catch (err: any) {
      console.error("Registration failed:", err);
      setError(
        err.detail || "Registration failed. Please try again or contact support."
      );
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Render step content
   */
  const renderStepContent = () => {
    if (step === 1) {
      return (
        <div className="space-y-6">
          <div className="space-y-2">
            <h3 className="text-xl font-semibold">Organization Details</h3>
            <p className="text-sm text-gray-600">
              Let's start by setting up your organization
            </p>
          </div>

          {/* Organization Name */}
          <div className="space-y-2">
            <Label htmlFor="orgName">Organization Name</Label>
            <div className="relative">
              <Building2 className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <Input
                id="orgName"
                type="text"
                placeholder="Acme Corporation"
                required
                value={orgName}
                onChange={(e) => handleOrgNameChange(e.target.value)}
                className="h-11 pl-10"
              />
            </div>
          </div>

          {/* Subdomain */}
          <div className="space-y-2">
            <Label htmlFor="subdomain">Subdomain</Label>
            <div className="relative">
              <Globe className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <Input
                id="subdomain"
                type="text"
                placeholder="acme"
                required
                value={subdomain}
                onChange={(e) => handleSubdomainChange(e.target.value)}
                className="h-11 pl-10 pr-10"
              />
              {checkingSubdomain && (
                <Loader2 className="absolute right-3 top-3 h-5 w-5 animate-spin text-gray-400" />
              )}
              {!checkingSubdomain && subdomainAvailable === true && (
                <CheckCircle2 className="absolute right-3 top-3 h-5 w-5 text-green-600" />
              )}
              {!checkingSubdomain && subdomainAvailable === false && (
                <AlertCircle className="absolute right-3 top-3 h-5 w-5 text-red-600" />
              )}
            </div>
            <div className="flex items-start space-x-2 text-sm">
              <div className="flex-1">
                <p className="text-gray-500">
                  Your organization will be available at:{" "}
                  <span className="font-medium text-blue-600">
                    {subdomain || "your-org"}.dokydoc.com
                  </span>
                </p>
                {subdomain && !isValidSubdomain(subdomain) && (
                  <p className="mt-1 text-red-600">
                    Subdomain must be 3-30 characters, alphanumeric and hyphens
                    only
                  </p>
                )}
                {subdomainAvailable === false && (
                  <p className="mt-1 text-red-600">
                    This subdomain is already taken
                  </p>
                )}
                {subdomainAvailable === true && (
                  <p className="mt-1 text-green-600">
                    This subdomain is available!
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Company Website (P5-10: used for industry auto-detection) */}
          <div className="space-y-2">
            <Label htmlFor="companyWebsite">
              Company Website{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </Label>
            <div className="relative">
              <Globe className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <Input
                id="companyWebsite"
                type="url"
                placeholder="https://acme.com"
                value={companyWebsite}
                onChange={(e) => setCompanyWebsite(e.target.value)}
                className="h-11 pl-10"
              />
            </div>
            <p className="text-xs text-gray-500">
              We&apos;ll automatically detect your industry to personalise DokyDoc for your team
            </p>
          </div>
        </div>
      );
    }

    if (step === 2) {
      return (
        <div className="space-y-6">
          <div className="space-y-2">
            <h3 className="text-xl font-semibold">Choose Your Plan</h3>
            <p className="text-sm text-gray-600">
              Select the plan that best fits your needs
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {TIERS.map((tier) => (
              <div
                key={tier.id}
                onClick={() => setSelectedTier(tier.id)}
                className={`relative cursor-pointer rounded-lg border-2 p-6 transition-all ${
                  selectedTier === tier.id
                    ? "border-blue-600 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                {tier.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white">
                      Popular
                    </span>
                  </div>
                )}

                <div className="space-y-4">
                  <div>
                    <h4 className="text-lg font-semibold">{tier.name}</h4>
                    <div className="mt-2 flex items-baseline">
                      <span className="text-3xl font-bold">{tier.price}</span>
                    </div>
                    <p className="mt-1 text-sm text-gray-600">
                      {tier.description}
                    </p>
                  </div>

                  <ul className="space-y-2">
                    {tier.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-600" />
                        <span className="text-sm">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {selectedTier === tier.id && (
                  <div className="absolute right-4 top-4">
                    <CheckCircle2 className="h-6 w-6 text-blue-600" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (step === 3) {
      return (
        <div className="space-y-6">
          <div className="space-y-2">
            <h3 className="text-xl font-semibold">Create Admin Account</h3>
            <p className="text-sm text-gray-600">
              Set up your administrator account for {orgName}
            </p>
          </div>

          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="adminEmail">Email Address</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <Input
                id="adminEmail"
                type="email"
                placeholder="admin@example.com"
                required
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                className="h-11 pl-10"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-2">
            <Label htmlFor="adminPassword">Password</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <Input
                id="adminPassword"
                type="password"
                placeholder="At least 8 characters"
                required
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                className="h-11 pl-10"
              />
            </div>
            {adminPassword && adminPassword.length < 8 && (
              <p className="text-sm text-red-600">
                Password must be at least 8 characters
              </p>
            )}
          </div>

          {/* Confirm Password */}
          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm Password</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <Input
                id="confirmPassword"
                type="password"
                placeholder="Re-enter your password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="h-11 pl-10"
              />
            </div>
            {confirmPassword &&
              adminPassword !== confirmPassword && (
                <p className="text-sm text-red-600">Passwords do not match</p>
              )}
          </div>

          {/* Summary Box */}
          <div className="rounded-lg bg-gray-50 p-4">
            <h4 className="mb-2 font-medium">Registration Summary</h4>
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-600">Organization:</dt>
                <dd className="font-medium">{orgName}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-600">Subdomain:</dt>
                <dd className="font-medium">{subdomain}.dokydoc.com</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-600">Plan:</dt>
                <dd className="font-medium capitalize">{selectedTier}</dd>
              </div>
            </dl>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <main className="flex h-screen w-full items-center justify-center bg-gray-50">
      <div className="w-full max-w-4xl space-y-8 rounded-xl bg-white p-8 shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="rounded-lg bg-blue-600 p-2">
              <Image
                src="/dockydoc-logo.jpg"
                alt="DokyDoc"
                width={32}
                height={32}
                className="rounded"
              />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Create Your Organization</h1>
              <p className="text-sm text-gray-600">
                Join thousands of teams using DokyDoc
              </p>
            </div>
          </div>

          {/* Step Indicator */}
          <div className="flex items-center space-x-2">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full ${
                    s === step
                      ? "bg-blue-600 text-white"
                      : s < step
                      ? "bg-green-600 text-white"
                      : "bg-gray-200 text-gray-600"
                  }`}
                >
                  {s < step ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : (
                    <span className="text-sm font-semibold">{s}</span>
                  )}
                </div>
                {s < 3 && (
                  <div
                    className={`mx-2 h-0.5 w-12 ${
                      s < step ? "bg-green-600" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="min-h-[400px]">{renderStepContent()}</div>

        {/* Error Message */}
        {error && (
          <div className="rounded-md bg-red-50 p-4">
            <p className="text-sm font-medium text-red-800">{error}</p>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between border-t pt-6">
          <div>
            {step > 1 && (
              <Button
                variant="outline"
                onClick={() => setStep(step - 1)}
                disabled={isLoading}
              >
                <ChevronLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            )}
          </div>

          <div className="flex items-center space-x-4">
            <Link
              href="/login"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Already have an account? Sign in
            </Link>

            {step < 3 ? (
              <Button
                onClick={() => setStep(step + 1)}
                disabled={!canProceed()}
              >
                Continue
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={!canProceed() || isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    Create Organization
                    <CheckCircle2 className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-gray-500">
          <p>
            By registering, you agree to our{" "}
            <Link href="/terms" className="underline hover:text-gray-700">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="underline hover:text-gray-700">
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
