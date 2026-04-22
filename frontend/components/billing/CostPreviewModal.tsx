"use client";

import { useState, useEffect } from "react";
import { X, Wallet, AlertTriangle, Info, Zap, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { ModelSelectorDropdown } from "./ModelSelectorDropdown";

interface CostPreview {
  model_id: string;
  doc_size_kb: number;
  passes: number;
  input_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  raw_cost_inr: number;
  markup_percent: number;
  markup_inr: number;
  total_cost_inr: number;
  wallet_balance_inr: number | null;
  can_afford: boolean | null;
}

interface CostPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (modelId: string) => void;
  docSizeKb: number;
  passes?: number;
  initialModel?: string | null;
}

export function CostPreviewModal({
  isOpen,
  onClose,
  onConfirm,
  docSizeKb,
  passes = 3,
  initialModel = null,
}: CostPreviewModalProps) {
  const [selectedModel, setSelectedModel] = useState<string>(initialModel ?? "gemini-2.0-flash");
  const [preview, setPreview] = useState<CostPreview | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    api
      .post("/billing/cost-preview", {
        doc_size_kb: docSizeKb,
        passes,
        model_id: selectedModel,
      })
      .then((data) => setPreview(data as CostPreview))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isOpen, selectedModel, docSizeKb, passes]);

  if (!isOpen) return null;

  const canAfford = preview?.can_afford !== false;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Cost Preview</h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="space-y-5 p-6">
          {/* Model selector */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">AI Model</label>
            <ModelSelectorDropdown
              value={selectedModel}
              onChange={setSelectedModel}
              disabled={loading}
            />
          </div>

          {/* Cost breakdown */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
            </div>
          ) : preview ? (
            <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 space-y-3">
              <div className="flex justify-between text-sm text-gray-600">
                <span>Estimated tokens</span>
                <span className="font-medium text-gray-800">
                  {(preview.input_tokens + preview.output_tokens).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-sm text-gray-600">
                <span>AI cost (raw)</span>
                <span className="font-medium text-gray-800">₹{preview.raw_cost_inr.toFixed(4)}</span>
              </div>
              <div className="flex justify-between text-sm text-gray-600">
                <span>Platform markup ({preview.markup_percent}%)</span>
                <span className="font-medium text-gray-800">₹{preview.markup_inr.toFixed(4)}</span>
              </div>
              <div className="border-t pt-2 flex justify-between text-base font-semibold text-gray-900">
                <span>You pay</span>
                <span className="text-blue-600">₹{preview.total_cost_inr.toFixed(4)}</span>
              </div>

              {/* Transparency note */}
              <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-xs text-blue-700">
                <Info className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                <span>
                  Raw cost = what {preview.model_id.startsWith("claude") ? "Anthropic" : "Google"} charges us.
                  Platform markup covers infrastructure, support, and product development.
                </span>
              </div>
            </div>
          ) : null}

          {/* Wallet status */}
          {preview && (
            <div className={`flex items-center gap-2 rounded-lg p-3 text-sm ${
              canAfford ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
            }`}>
              {canAfford ? (
                <Wallet className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              <span>
                {preview.wallet_balance_inr !== null
                  ? canAfford
                    ? `Wallet balance ₹${preview.wallet_balance_inr.toFixed(2)} — sufficient`
                    : `Wallet balance ₹${preview.wallet_balance_inr.toFixed(2)} — insufficient. Top up to continue.`
                  : "Wallet balance unavailable"}
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 border-t px-6 py-4">
          <button
            onClick={onClose}
            className="flex-1 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(selectedModel)}
            disabled={!canAfford || loading}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Analyze with {selectedModel.includes("lite") ? "Gemini Flash-Lite" : selectedModel.includes("claude") ? "Claude" : "Gemini"}
          </button>
        </div>
      </div>
    </div>
  );
}
