"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Wallet, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";

interface WalletBalance {
  balance_inr: number;
  free_credit_inr: number;
  total_available_inr: number;
  low_balance: boolean;
}

export function WalletBalanceBadge() {
  const [balance, setBalance] = useState<WalletBalance | null>(null);

  useEffect(() => {
    api.get("/billing/wallet/balance")
      .then((data) => setBalance(data as WalletBalance))
      .catch(() => {});
  }, []);

  if (!balance) return null;

  const isLow = balance.low_balance;

  return (
    <Link
      href="/billing"
      className={`hidden items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium transition-colors md:flex ${
        isLow
          ? "bg-red-50 text-red-700 hover:bg-red-100"
          : "bg-green-50 text-green-700 hover:bg-green-100"
      }`}
      title={
        balance.free_credit_inr > 0
          ? `₹${balance.free_credit_inr.toFixed(2)} free credit + ₹${balance.balance_inr.toFixed(2)} paid balance`
          : undefined
      }
    >
      {isLow ? (
        <AlertTriangle className="h-3.5 w-3.5" />
      ) : (
        <Wallet className="h-3.5 w-3.5" />
      )}
      <span>₹{balance.total_available_inr.toFixed(2)}</span>
      {balance.free_credit_inr > 0 && (
        <span className="rounded-full bg-white/60 px-1 py-0.5 text-[10px] font-semibold leading-none">
          FREE
        </span>
      )}
    </Link>
  );
}
