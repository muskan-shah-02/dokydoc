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

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/contexts/AuthContext";
import {
  User,
  Settings,
  LogOut,
  ChevronDown,
  Menu,
  Building2,
  Crown,
} from "lucide-react";

interface HeaderProps {
  onMenuToggle: () => void;
}

export function Header({ onMenuToggle }: HeaderProps) {
  const { user, tenant, logout, isCXO } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

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
              <h1 className="text-lg font-bold text-gray-900">DokyDoc</h1>
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

      {/* Right: Tenant Info + User Menu */}
      <div className="flex items-center space-x-4">
        {/* Tenant Tier Badge */}
        {tenant && (
          <div className="hidden items-center space-x-2 rounded-full bg-blue-50 px-3 py-1 sm:flex">
            <Crown className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium capitalize text-blue-600">
              {tenant.tier}
            </span>
          </div>
        )}

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
                className="fixed inset-0 z-10"
                onClick={() => setUserMenuOpen(false)}
              />

              {/* Menu */}
              <div className="absolute right-0 z-20 mt-2 w-64 rounded-lg border bg-white shadow-lg">
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
