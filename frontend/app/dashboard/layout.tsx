/**
 * Dashboard Layout
 * Sprint 2 Extended - Simplified to use only AppLayout
 *
 * This layout no longer renders its own sidebar - all navigation
 * is handled by the main AppLayout component to avoid duplicate sidebars.
 */

"use client";

import React from "react";

// --- Main Dashboard Layout ---
// Simply renders children - AppLayout handles sidebar and header
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
