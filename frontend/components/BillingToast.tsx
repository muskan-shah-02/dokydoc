/**
 * Global Billing Toast Notifications
 *
 * Shows toast notifications in the bottom-right corner on any page when:
 * - Gemini API is called (shows current balance)
 * - Processing completes (shows cost of operation)
 */

"use client";

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from "react";
import { X, Wallet, Zap, CheckCircle, AlertTriangle, Loader2 } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

// Toast types
export type ToastType = "processing" | "success" | "cost" | "low_balance" | "error";

export interface BillingToast {
  id: string;
  type: ToastType;
  title: string;
  message: string;
  balance?: number;
  cost?: number;
  duration?: number; // ms, 0 = persistent until dismissed
}

interface BillingNotificationContextType {
  showProcessingStarted: (balance: number) => void;
  showProcessingComplete: (cost: number, newBalance: number) => void;
  showLowBalance: (balance: number) => void;
  showError: (message: string) => void;
  dismissToast: (id: string) => void;
  refreshBalance: () => Promise<number | null>;
}

const BillingNotificationContext = createContext<BillingNotificationContextType | null>(null);

export function useBillingNotification() {
  const context = useContext(BillingNotificationContext);
  if (!context) {
    throw new Error("useBillingNotification must be used within BillingNotificationProvider");
  }
  return context;
}

// Provider component
export function BillingNotificationProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<BillingToast[]>([]);

  const addToast = useCallback((toast: Omit<BillingToast, "id">) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast = { ...toast, id };

    setToasts(prev => [...prev, newToast]);

    // Auto-dismiss after duration (default 5 seconds, 0 = no auto-dismiss)
    const duration = toast.duration ?? 5000;
    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, duration);
    }

    return id;
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const refreshBalance = useCallback(async (): Promise<number | null> => {
    try {
      const data = await api.get<{ balance_inr?: number }>("/billing/usage");
      return data?.balance_inr ?? null;
    } catch {
      return null;
    }
  }, []);

  const showProcessingStarted = useCallback((balance: number) => {
    addToast({
      type: "processing",
      title: "AI Processing Started",
      message: "Gemini API is analyzing your document...",
      balance,
      duration: 0, // Persistent until processing completes
    });
  }, [addToast]);

  const showProcessingComplete = useCallback((cost: number, newBalance: number) => {
    // Remove any processing toasts
    setToasts(prev => prev.filter(t => t.type !== "processing"));

    addToast({
      type: "cost",
      title: "Processing Complete",
      message: `This operation cost INR ${cost.toFixed(2)}`,
      cost,
      balance: newBalance,
      duration: 8000,
    });

    // Show low balance warning if needed
    if (newBalance < 100) {
      setTimeout(() => {
        addToast({
          type: "low_balance",
          title: "Low Balance Warning",
          message: `Your balance is running low. Top up to continue using AI features.`,
          balance: newBalance,
          duration: 10000,
        });
      }, 1000);
    }
  }, [addToast]);

  const showLowBalance = useCallback((balance: number) => {
    addToast({
      type: "low_balance",
      title: "Low Balance Alert",
      message: "Your prepaid balance is running low.",
      balance,
      duration: 10000,
    });
  }, [addToast]);

  const showError = useCallback((message: string) => {
    // Remove any processing toasts
    setToasts(prev => prev.filter(t => t.type !== "processing"));

    addToast({
      type: "error",
      title: "Processing Failed",
      message,
      duration: 8000,
    });
  }, [addToast]);

  return (
    <BillingNotificationContext.Provider
      value={{
        showProcessingStarted,
        showProcessingComplete,
        showLowBalance,
        showError,
        dismissToast,
        refreshBalance,
      }}
    >
      {children}
      {/* Toast Container - Fixed to bottom-right */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-3 max-w-sm">
        {toasts.map(toast => (
          <ToastCard key={toast.id} toast={toast} onDismiss={dismissToast} />
        ))}
      </div>
    </BillingNotificationContext.Provider>
  );
}

// Individual Toast Card
function ToastCard({
  toast,
  onDismiss
}: {
  toast: BillingToast;
  onDismiss: (id: string) => void;
}) {
  const config = getToastConfig(toast.type);

  return (
    <div
      className={`
        relative overflow-hidden rounded-lg border shadow-lg backdrop-blur-sm
        animate-in slide-in-from-right-full duration-300
        ${config.bgColor} ${config.borderColor}
      `}
      style={{ minWidth: "320px" }}
    >
      {/* Progress bar for processing */}
      {toast.type === "processing" && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-blue-200 overflow-hidden">
          <div className="h-full bg-blue-500 animate-pulse" style={{ width: "100%" }} />
        </div>
      )}

      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className={`flex-shrink-0 rounded-full p-2 ${config.iconBg}`}>
            {config.icon}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4 className={`font-semibold text-sm ${config.titleColor}`}>
                {toast.title}
              </h4>
              <button
                onClick={() => onDismiss(toast.id)}
                className="flex-shrink-0 rounded-full p-1 hover:bg-black/10 transition-colors"
              >
                <X className="h-4 w-4 text-gray-500" />
              </button>
            </div>

            <p className="mt-1 text-sm text-gray-600">{toast.message}</p>

            {/* Balance/Cost Info */}
            {(toast.balance !== undefined || toast.cost !== undefined) && (
              <div className="mt-2 flex items-center gap-4 text-sm">
                {toast.balance !== undefined && (
                  <div className="flex items-center gap-1">
                    <Wallet className="h-4 w-4 text-gray-400" />
                    <span className="text-gray-600">Balance:</span>
                    <span className={`font-semibold ${
                      toast.balance < 100 ? "text-orange-600" : "text-green-600"
                    }`}>
                      INR {toast.balance.toFixed(2)}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Low Balance Action */}
            {toast.type === "low_balance" && (
              <Link
                href="/settings/billing"
                className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-orange-600 hover:text-orange-700 underline"
              >
                Top up now
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Toast configuration by type
function getToastConfig(type: ToastType) {
  switch (type) {
    case "processing":
      return {
        bgColor: "bg-blue-50/95",
        borderColor: "border-blue-200",
        iconBg: "bg-blue-100",
        icon: <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />,
        titleColor: "text-blue-800",
      };
    case "success":
      return {
        bgColor: "bg-green-50/95",
        borderColor: "border-green-200",
        iconBg: "bg-green-100",
        icon: <CheckCircle className="h-5 w-5 text-green-600" />,
        titleColor: "text-green-800",
      };
    case "cost":
      return {
        bgColor: "bg-white/95",
        borderColor: "border-gray-200",
        iconBg: "bg-green-100",
        icon: <Zap className="h-5 w-5 text-green-600" />,
        titleColor: "text-gray-900",
      };
    case "low_balance":
      return {
        bgColor: "bg-orange-50/95",
        borderColor: "border-orange-200",
        iconBg: "bg-orange-100",
        icon: <AlertTriangle className="h-5 w-5 text-orange-600" />,
        titleColor: "text-orange-800",
      };
    case "error":
      return {
        bgColor: "bg-red-50/95",
        borderColor: "border-red-200",
        iconBg: "bg-red-100",
        icon: <AlertTriangle className="h-5 w-5 text-red-600" />,
        titleColor: "text-red-800",
      };
  }
}
