/**
 * Header Component
 * Sprint 2 Extended - Multi-Tenancy Support
 *
 * Features:
 * - Tenant branding and logo
 * - User menu with profile/settings/logout
 * - Mobile menu toggle
 * - Tenant information display
 */

"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/contexts/AuthContext";
import { useNotifications } from "@/contexts/NotificationContext";
import { RoleSwitcher } from "./RoleSwitcher";
import { WalletBalanceBadge } from "@/components/billing/WalletBalanceBadge";
import {
  User,
  Settings,
  LogOut,
  ChevronDown,
  Menu,
  Building2,
  Crown,
  Bell,
  CheckCheck,
  FileText,
  Code,
  AlertTriangle,
  Info,
  Sparkles,
  CreditCard,
} from "lucide-react";

interface HeaderProps {
  onMenuToggle: () => void;
}

function getNotificationIcon(type: string) {
  switch (type) {
    case "analysis_complete":
      return <FileText className="h-4 w-4 text-green-500" />;
    case "analysis_failed":
      return <AlertTriangle className="h-4 w-4 text-red-500" />;
    case "validation_alert":
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    default:
      return <Info className="h-4 w-4 text-blue-500" />;
  }
}

export function Header({ onMenuToggle }: HeaderProps) {
  const { user, tenant, logout, isCXO } = useAuth();
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  // Close bell dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setBellOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b bg-white px-4 shadow-sm lg:px-6">
      {/* Left: Logo + Tenant Name */}
      <div className="flex items-center space-x-4">
        {/* Mobile Menu Toggle */}
        <button
          onClick={onMenuToggle}
          className="rounded-md p-2 hover:bg-gray-100 lg:hidden"
        >
          <Menu className="h-6 w-6" />
        </button>

        {/* Logo */}
        <Link href="/dashboard" className="flex items-center space-x-3">
          <div className="rounded-lg bg-blue-600 p-1.5">
            <Image
              src="/dockydoc-logo.jpg"
              alt="DokyDoc"
              width={28}
              height={28}
              className="rounded"
            />
          </div>
          <div className="hidden md:block">
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-gray-900">
                DokyDoc
                <span className="ml-1 text-[10px] font-medium text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded-full align-middle">+ AskyDoc</span>
              </h1>
              {tenant && (
                <>
                  <span className="text-gray-400">|</span>
                  <span className="text-sm font-medium text-gray-600">
                    {tenant.name}
                  </span>
                </>
              )}
            </div>
          </div>
        </Link>
      </div>

      {/* Right: Role Switcher + Tenant Info + User Menu */}
      <div className="flex items-center space-x-4">
        {/* Role Switcher (for multi-role users) */}
        <div className="hidden sm:block">
          <RoleSwitcher />
        </div>

        {/* Tenant Tier Badge */}
        {tenant && (
          <div className="hidden items-center space-x-2 rounded-full bg-blue-50 px-3 py-1 md:flex">
            <Crown className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium capitalize text-blue-600">
              {tenant.tier}
            </span>
          </div>
        )}

        {/* Wallet Balance Badge */}
        <WalletBalanceBadge />

        {/* AskyDoc Quick Access */}
        <Link
          href="/dashboard/chat"
          className="relative rounded-lg p-2 hover:bg-purple-50 transition-colors group"
          title="AskyDoc AI Assistant"
        >
          <Sparkles className="h-5 w-5 text-purple-500 group-hover:text-purple-600" />
        </Link>

        {/* Notification Bell */}
        <div className="relative" ref={bellRef}>
          <button
            onClick={() => setBellOpen(!bellOpen)}
            className="relative rounded-lg p-2 hover:bg-gray-100"
            title="Notifications"
          >
            <Bell className="h-5 w-5 text-gray-600" />
            {unreadCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>

          {bellOpen && (
            <div className="absolute right-0 z-50 mt-2 w-80 rounded-lg border bg-white shadow-lg">
              <div className="flex items-center justify-between border-b px-4 py-3">
                <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
                <div className="flex items-center gap-2">
                  {unreadCount > 0 && (
                    <button
                      onClick={() => markAllRead()}
                      className="text-xs text-blue-600 hover:text-blue-700"
                    >
                      <CheckCheck className="inline h-3.5 w-3.5 mr-0.5" />
                      Mark all read
                    </button>
                  )}
                </div>
              </div>

              <div className="max-h-80 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <Bell className="h-8 w-8 text-gray-300 mb-2" />
                    <p className="text-sm text-gray-500">No notifications yet</p>
                  </div>
                ) : (
                  notifications.slice(0, 10).map((n) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        if (!n.is_read) markRead(n.id);
                      }}
                      className={`w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-gray-50 border-b last:border-b-0 ${
                        !n.is_read ? "bg-blue-50/50" : ""
                      }`}
                    >
                      <div className="mt-0.5 flex-shrink-0">
                        {getNotificationIcon(n.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm ${!n.is_read ? "font-semibold" : "font-medium"} text-gray-900 truncate`}>
                          {n.title}
                        </p>
                        <p className="text-xs text-gray-500 line-clamp-2 mt-0.5">
                          {n.message}
                        </p>
                        {n.type === "analysis_complete" && n.resource_id && (
                          <Link
                            href={`/dashboard/chat?${n.resource_type === "repository" ? "repo" : "doc"}=${n.resource_id}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setBellOpen(false);
                            }}
                            className="inline-flex items-center gap-1 mt-1 text-xs font-medium text-purple-600 hover:text-purple-700"
                          >
                            <Sparkles className="h-3 w-3" />
                            Ask AskyDoc about it
                          </Link>
                        )}
                        {n.created_at && (
                          <p className="text-xs text-gray-400 mt-1">
                            {new Date(n.created_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                      {!n.is_read && (
                        <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-blue-500" />
                      )}
                    </button>
                  ))
                )}
              </div>

              <div className="border-t px-4 py-2">
                <Link
                  href="/dashboard/notifications"
                  onClick={() => setBellOpen(false)}
                  className="block text-center text-sm text-blue-600 hover:text-blue-700"
                >
                  View all notifications
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center space-x-3 rounded-lg px-3 py-2 hover:bg-gray-100"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
              {user?.email.charAt(0).toUpperCase()}
            </div>
            <div className="hidden text-left sm:block">
              <div className="flex items-center space-x-1">
                <span className="text-sm font-medium text-gray-900">
                  {user?.email}
                </span>
                <ChevronDown className="h-4 w-4 text-gray-500" />
              </div>
              <div className="flex items-center space-x-1">
                {isCXO() && (
                  <span className="rounded bg-purple-100 px-1.5 py-0.5 text-xs font-medium text-purple-700">
                    CXO
                  </span>
                )}
                {user?.roles
                  .filter((role) => role !== "CXO")
                  .map((role) => (
                    <span
                      key={role}
                      className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-700"
                    >
                      {role}
                    </span>
                  ))}
              </div>
            </div>
          </button>

          {/* Dropdown Menu */}
          {userMenuOpen && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-40"
                onClick={() => setUserMenuOpen(false)}
              />

              {/* Menu */}
              <div className="absolute right-0 z-50 mt-2 w-64 rounded-lg border bg-white shadow-lg">
                {/* User Info */}
                <div className="border-b p-4">
                  <div className="flex items-center space-x-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
                      {user?.email.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">
                        {user?.email}
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {user?.roles.map((role) => (
                          <span
                            key={role}
                            className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                              role === "CXO"
                                ? "bg-purple-100 text-purple-700"
                                : "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {role}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Tenant Info */}
                {tenant && (
                  <div className="border-b p-4">
                    <div className="flex items-start space-x-3">
                      <Building2 className="mt-0.5 h-5 w-5 text-gray-400" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">
                          {tenant.name}
                        </p>
                        <p className="mt-0.5 text-xs text-gray-500">
                          {tenant.subdomain}.dokydoc.com
                        </p>
                        <div className="mt-2 flex items-center space-x-2">
                          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium capitalize text-blue-700">
                            {tenant.tier}
                          </span>
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium capitalize text-gray-700">
                            {tenant.billing_type}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Menu Items */}
                <div className="p-2">
                  <Link
                    href="/settings/profile"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center space-x-3 rounded-md px-3 py-2 text-sm hover:bg-gray-100"
                  >
                    <User className="h-4 w-4 text-gray-500" />
                    <span>Profile Settings</span>
                  </Link>

                  <Link
                    href="/billing"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center space-x-3 rounded-md px-3 py-2 text-sm hover:bg-gray-100"
                  >
                    <CreditCard className="h-4 w-4 text-gray-500" />
                    <span>Billing & Wallet</span>
                  </Link>

                  <Link
                    href="/settings"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center space-x-3 rounded-md px-3 py-2 text-sm hover:bg-gray-100"
                  >
                    <Settings className="h-4 w-4 text-gray-500" />
                    <span>Settings</span>
                  </Link>

                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      logout();
                    }}
                    className="flex w-full items-center space-x-3 rounded-md px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                  >
                    <LogOut className="h-4 w-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
