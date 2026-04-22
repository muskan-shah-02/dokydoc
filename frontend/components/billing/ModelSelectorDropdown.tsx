"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Sparkles, Zap } from "lucide-react";
import { api } from "@/lib/api";

interface Model {
  model_id: string;
  display_name: string;
  provider: string;
  tier: "free" | "paid";
  description: string;
  cost_per_doc_estimate: string;
}

interface ModelSelectorDropdownProps {
  value: string | null;
  onChange: (modelId: string) => void;
  disabled?: boolean;
}

export function ModelSelectorDropdown({ value, onChange, disabled }: ModelSelectorDropdownProps) {
  const [models, setModels] = useState<Model[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/billing/models")
      .then((data: any) => setModels(data.models ?? []))
      .catch(() => {});
  }, []);

  const selected = models.find((m) => m.model_id === value) ?? models[0];

  if (models.length === 0) return null;

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm shadow-sm hover:border-blue-400 disabled:opacity-50"
      >
        {selected?.tier === "free" ? (
          <Zap className="h-4 w-4 text-green-500" />
        ) : (
          <Sparkles className="h-4 w-4 text-blue-500" />
        )}
        <span className="font-medium text-gray-800">
          {selected?.display_name ?? "Select model"}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 z-50 mt-1 w-72 rounded-xl border bg-white shadow-lg">
            <div className="p-2">
              {models.map((model) => (
                <button
                  key={model.model_id}
                  onClick={() => {
                    onChange(model.model_id);
                    setOpen(false);
                  }}
                  className={`w-full rounded-lg px-3 py-2.5 text-left hover:bg-blue-50 ${
                    model.model_id === (selected?.model_id) ? "bg-blue-50" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {model.tier === "free" ? (
                        <Zap className="h-4 w-4 text-green-500" />
                      ) : (
                        <Sparkles className="h-4 w-4 text-blue-500" />
                      )}
                      <span className="text-sm font-medium text-gray-900">
                        {model.display_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                          model.tier === "free"
                            ? "bg-green-100 text-green-700"
                            : "bg-blue-100 text-blue-700"
                        }`}
                      >
                        {model.tier}
                      </span>
                      <span className="text-xs text-gray-400">{model.cost_per_doc_estimate}</span>
                    </div>
                  </div>
                  <p className="mt-0.5 pl-6 text-xs text-gray-500">{model.description}</p>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
