"use client";

import { useState } from "react";
import { CheckCircle2, Building2, Mail, Phone, Users, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";

const TEAM_SIZES = ["1–10", "11–50", "51–200", "200+"];

export function EnterpriseContactForm() {
  const [form, setForm] = useState({
    company_name: "",
    contact_name: "",
    email: "",
    phone: "",
    team_size: "",
    use_case: "",
    message: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/billing/enterprise-contact", form);
      setSubmitted(true);
    } catch (err: any) {
      setError(err?.message ?? "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-green-200 bg-green-50 p-10 text-center">
        <CheckCircle2 className="h-12 w-12 text-green-500" />
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Request Received!</h3>
          <p className="mt-1 text-sm text-gray-600">
            Our team will reach out within 1 business day.
          </p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Company name *</label>
          <div className="relative">
            <Building2 className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              required
              type="text"
              value={form.company_name}
              onChange={(e) => setForm({ ...form, company_name: e.target.value })}
              className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="Acme Corp"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Your name *</label>
          <input
            required
            type="text"
            value={form.contact_name}
            onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            placeholder="Jane Doe"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Work email *</label>
          <div className="relative">
            <Mail className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              required
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="jane@company.com"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Phone</label>
          <div className="relative">
            <Phone className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="+91 98765 43210"
            />
          </div>
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">Team size</label>
        <div className="flex flex-wrap gap-2">
          {TEAM_SIZES.map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => setForm({ ...form, team_size: size })}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
                form.team_size === size
                  ? "border-blue-500 bg-blue-50 text-blue-700"
                  : "border-gray-200 text-gray-600 hover:border-gray-300"
              }`}
            >
              <Users className="h-3.5 w-3.5" />
              {size}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">Primary use case</label>
        <input
          type="text"
          value={form.use_case}
          onChange={(e) => setForm({ ...form, use_case: e.target.value })}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          placeholder="e.g. BRD compliance, multi-tenant SaaS, regulatory documents"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">Message</label>
        <div className="relative">
          <MessageSquare className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <textarea
            rows={4}
            value={form.message}
            onChange={(e) => setForm({ ...form, message: e.target.value })}
            className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none"
            placeholder="Tell us about your requirements..."
          />
        </div>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {submitting ? "Sending…" : "Request Enterprise Demo"}
      </button>
    </form>
  );
}
