/**
 * Global Billing Toast Notifications
 *
 * Shows toast notifications in the bottom-right corner on any page when:
 * - Gemini API is called (shows current balance)
 * - Processing completes (shows cost, tokens, and processing time)
 *
 * Features:
 * - Toast stays visible for 30 seconds
 * - Minimized icon persists after dismissal for re-viewing
 * - Shows token count (input + output)
 * - Shows processing duration
 */

"use client";

import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from "react";
import { X, Wallet, Zap, CheckCircle, AlertTriangle, Loader2, Clock, Cpu, ChevronUp, Receipt } from "lucide-react";
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
  tokens?: { input: number; output: number; total: number };
  processingTime?: number; // in seconds
  duration?: number; // ms, 0 = persistent until dismissed
}

// Last completed operation info for re-viewing
interface LastOperation {
  cost: number;
  balance: number;
  tokens?: { input: number; output: number; total: number };
  processingTime?: number;
  timestamp: Date;
}

interface BillingNotificationContextType {
  showProcessingStarted: (balance: number) => void;
  showProcessingComplete: (cost: number, newBalance: number, tokens?: { input: number; output: number }, processingTime?: number) => void;
  showLowBalance: (balance: number) => void;
  showError: (message: string) => void;
  dismissToast: (id: string) => void;
  refreshBalance: () => Promise<number | null>;
  getProcessingStartTime: () => number | null;
  setProcessingStartTime: (time: number | null) => void;
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
  const [lastOperation, setLastOperation] = useState<LastOperation | null>(null);
  const [showMinimizedIcon, setShowMinimizedIcon] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const processingStartTimeRef = useRef<number | null>(null);

  const addToast = useCallback((toast: Omit<BillingToast, "id">) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast = { ...toast, id };

    setToasts(prev => [...prev, newToast]);

    // Auto-dismiss after duration (default 30 seconds, 0 = no auto-dismiss)
    const duration = toast.duration ?? 30000;
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

  const getProcessingStartTime = useCallback(() => {
    return processingStartTimeRef.current;
  }, []);

  const setProcessingStartTime = useCallback((time: number | null) => {
    processingStartTimeRef.current = time;
  }, []);

  const showProcessingStarted = useCallback((balance: number) => {
    // Record start time
    processingStartTimeRef.current = Date.now();

    addToast({
      type: "processing",
      title: "AI Processing Started",
      message: "Gemini API is analyzing your document...",
      balance,
      duration: 0, // Persistent until processing completes
    });
  }, [addToast]);

  const showProcessingComplete = useCallback((
    cost: number,
    newBalance: number,
    tokens?: { input: number; output: number },
    processingTime?: number
  ) => {
    // Calculate processing time if not provided
    let duration = processingTime;
    if (duration === undefined && processingStartTimeRef.current) {
      duration = Math.round((Date.now() - processingStartTimeRef.current) / 1000);
    }
    processingStartTimeRef.current = null;

    // Remove any processing toasts
    setToasts(prev => prev.filter(t => t.type !== "processing"));

    const tokenData = tokens ? {
      input: tokens.input,
      output: tokens.output,
      total: tokens.input + tokens.output
    } : undefined;

    // Save last operation for re-viewing
    setLastOperation({
      cost,
      balance: newBalance,
      tokens: tokenData,
      processingTime: duration,
      timestamp: new Date(),
    });
    setShowMinimizedIcon(true);

    addToast({
      type: "cost",
      title: "Processing Complete",
      message: `This operation cost INR ${cost.toFixed(2)}`,
      cost,
      balance: newBalance,
      tokens: tokenData,
      processingTime: duration,
      duration: 30000, // 30 seconds
    });

    // Show low balance warning if needed
    if (newBalance < 100) {
      setTimeout(() => {
        addToast({
          type: "low_balance",
          title: "Low Balance Warning",
          message: `Your balance is running low. Top up to continue using AI features.`,
          balance: newBalance,
          duration: 15000,
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
      duration: 15000,
    });
  }, [addToast]);

  const showError = useCallback((message: string) => {
    // Clear start time
    processingStartTimeRef.current = null;

    // Remove any processing toasts
    setToasts(prev => prev.filter(t => t.type !== "processing"));

    addToast({
      type: "error",
      title: "Processing Failed",
      message,
      duration: 10000,
    });
  }, [addToast]);

  // Re-show last operation toast
  const handleReviewClick = useCallback(() => {
    if (lastOperation) {
      setIsExpanded(!isExpanded);
    }
  }, [lastOperation, isExpanded]);

  // Format time elapsed since last operation
  const formatTimeAgo = (date: Date) => {
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    return `${Math.floor(minutes / 60)}h ago`;
  };

  // Update time ago display
  const [, forceUpdate] = useState({});
  useEffect(() => {
    if (showMinimizedIcon && lastOperation) {
      const interval = setInterval(() => forceUpdate({}), 10000);
      return () => clearInterval(interval);
    }
  }, [showMinimizedIcon, lastOperation]);

  return (
    <BillingNotificationContext.Provider
      value={{
        showProcessingStarted,
        showProcessingComplete,
        showLowBalance,
        showError,
        dismissToast,
        refreshBalance,
        getProcessingStartTime,
        setProcessingStartTime,
      }}
    >
      {children}

      {/* Toast Container - Fixed to bottom-right */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-3 max-w-sm">
        {toasts.map(toast => (
          <ToastCard key={toast.id} toast={toast} onDismiss={dismissToast} />
        ))}

        {/* Minimized Re-view Icon (always shows after any processing completes) */}
        {showMinimizedIcon && lastOperation && (
          <div className="relative">
            {/* Expanded Card */}
            {isExpanded && (
              <div
                className="absolute bottom-14 right-0 w-72 rounded-lg border border-gray-200 bg-white/95 backdrop-blur-sm shadow-lg p-4 animate-in slide-in-from-bottom-2 duration-200"
              >
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-sm text-gray-900">Last Operation</h4>
                  <span className="text-xs text-gray-500">{formatTimeAgo(lastOperation.timestamp)}</span>
                </div>

                <div className="space-y-2 text-sm">
                  {/* Cost */}
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600 flex items-center gap-1">
                      <Zap className="h-4 w-4" /> Cost:
                    </span>
                    <span className="font-semibold text-gray-900">INR {lastOperation.cost.toFixed(2)}</span>
                  </div>

                  {/* Balance */}
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600 flex items-center gap-1">
                      <Wallet className="h-4 w-4" /> Balance:
                    </span>
                    <span className={`font-semibold ${lastOperation.balance < 100 ? "text-orange-600" : "text-green-600"}`}>
                      INR {lastOperation.balance.toFixed(2)}
                    </span>
                  </div>

                  {/* Tokens */}
                  {lastOperation.tokens && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600 flex items-center gap-1">
                        <Cpu className="h-4 w-4" /> Tokens:
                      </span>
                      <span className="font-medium text-gray-700">
                        {lastOperation.tokens.total.toLocaleString()}
                        <span className="text-xs text-gray-500 ml-1">
                          ({lastOperation.tokens.input.toLocaleString()} in / {lastOperation.tokens.output.toLocaleString()} out)
                        </span>
                      </span>
                    </div>
                  )}

                  {/* Processing Time */}
                  {lastOperation.processingTime !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600 flex items-center gap-1">
                        <Clock className="h-4 w-4" /> Duration:
                      </span>
                      <span className="font-medium text-gray-700">
                        {formatDuration(lastOperation.processingTime)}
                      </span>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => setShowMinimizedIcon(false)}
                  className="mt-3 w-full text-xs text-gray-500 hover:text-gray-700 underline"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Minimized Icon Button - Prominent and always visible */}
            <button
              onClick={handleReviewClick}
              className={`
                flex items-center gap-2 px-4 py-2.5 rounded-full shadow-xl transition-all duration-200
                animate-in slide-in-from-right-2 duration-300
                ${isExpanded
                  ? "bg-blue-600 text-white ring-2 ring-blue-300"
                  : "bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:from-green-600 hover:to-emerald-700 ring-2 ring-green-300/50"
                }
              `}
              title="Click to view last billing details"
            >
              <Receipt className="h-5 w-5" />
              <span className="text-sm font-semibold">₹{lastOperation.cost.toFixed(2)}</span>
              <ChevronUp className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
            </button>
          </div>
        )}
      </div>
    </BillingNotificationContext.Provider>
  );
}

// Format duration in human readable format
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
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
      style={{ minWidth: "340px" }}
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

            {/* Detailed Info for cost type */}
            {toast.type === "cost" && (
              <div className="mt-3 space-y-1.5 text-sm">
                {/* Balance */}
                {toast.balance !== undefined && (
                  <div className="flex items-center gap-2">
                    <Wallet className="h-4 w-4 text-gray-400" />
                    <span className="text-gray-600">Balance:</span>
                    <span className={`font-semibold ${
                      toast.balance < 100 ? "text-orange-600" : "text-green-600"
                    }`}>
                      INR {toast.balance.toFixed(2)}
                    </span>
                  </div>
                )}

                {/* Tokens */}
                {toast.tokens && (
                  <div className="flex items-center gap-2">
                    <Cpu className="h-4 w-4 text-gray-400" />
                    <span className="text-gray-600">Tokens:</span>
                    <span className="font-medium text-gray-700">
                      {toast.tokens.total.toLocaleString()}
                      <span className="text-xs text-gray-500 ml-1">
                        ({toast.tokens.input.toLocaleString()} in / {toast.tokens.output.toLocaleString()} out)
                      </span>
                    </span>
                  </div>
                )}

                {/* Processing Time */}
                {toast.processingTime !== undefined && (
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-gray-400" />
                    <span className="text-gray-600">Duration:</span>
                    <span className="font-medium text-gray-700">
                      {formatDuration(toast.processingTime)}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Balance/Cost Info for other types */}
            {toast.type !== "cost" && (toast.balance !== undefined || toast.cost !== undefined) && (
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
