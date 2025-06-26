/*
  This is the updated code for your EXISTING file at:
  frontend/app/dashboard/layout.tsx
*/
"use client";

import React, {
  useState,
  useMemo,
  createContext,
  useContext,
  ElementType,
  useEffect,
} from "react";
// import Link from 'next/link'; // Removed for compatibility
// import { usePathname } from 'next/navigation'; // Removed for compatibility
import {
  LayoutDashboard,
  FileText,
  GitBranch,
  CheckSquare,
  History,
  Download,
  ShieldCheck,
  Cog,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Search,
  Bell,
  User,
  ChevronsUpDown,
} from "lucide-react";

// --- Helper function to format role slugs for display ---
const formatRoleForDisplay = (slug: string): string => {
  if (!slug) return "N/A";
  return slug.replace(/-/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
};

// --- Context for Sidebar State ---
const SidebarContext = createContext({ isCollapsed: false });

// --- DokyDoc Logo Component ---
const DokyDocLogo = ({ isCollapsed }: { isCollapsed: boolean }) => (
  <a
    href="/select-role"
    className={`flex items-center h-16 bg-white border-b border-gray-200 ${
      isCollapsed ? "justify-center" : "px-6"
    }`}
  >
    <svg
      className={`transition-all duration-300 ${
        isCollapsed ? "h-8 w-8" : "h-9 w-9"
      }`}
      viewBox="0 0 100 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M78.6,0.1c-12.2,0-22.1,9.9-22.1,22.1c0,2.4,0.4,4.8,1.2,7c-3.5-2.1-7.6-3.3-12-3.3c-14.9,0-27,12.1-27,27   s12.1,27,27,27c6.1,0,11.7-2,16.3-5.5c3.2,3.3,7.7,5.5,12.7,5.5c10.5,0,19-8.5,19-19S89.1,0.1,78.6,0.1z M78.6,57.1   c-3.9,0-7-3.1-7-7s3.1-7,7-7s7,3.1,7,7S82.5,57.1,78.6,57.1z"
        fill="#4A90E2"
      />
      <path
        d="M20.7,48.2c-0.8-2.3-1.2-4.6-1.2-7c0-12.2,9.9-22.1,22.1-22.1c4.4,0,8.5,1.3,12,3.3c-2.3,13.4-12.1,23.8-25.2,25.6   C25.9,56.8,22.9,53,20.7,48.2z"
        fill="#90B8DE"
      />
    </svg>
    {!isCollapsed && (
      <span className="ml-2 text-xl font-bold text-gray-800 whitespace-nowrap">
        DokyDoc
      </span>
    )}
  </a>
);

// --- Interface definition for SidebarItem props ---
interface SidebarItemProps {
  icon: ElementType;
  text: string;
  active: boolean;
  alert?: boolean;
  href: string;
}

// --- Sidebar Item ---
const SidebarItem = ({
  icon: Icon,
  text,
  active,
  alert,
  href,
}: SidebarItemProps) => {
  const { isCollapsed } = useContext(SidebarContext);
  return (
    <li>
      <a
        href={href}
        className={`relative flex items-center py-3 px-4 my-1 font-medium rounded-lg cursor-pointer transition-colors group ${
          active
            ? "bg-gradient-to-tr from-blue-200 to-blue-100 text-blue-800"
            : "hover:bg-blue-50 text-gray-600"
        }`}
      >
        <Icon size={20} />
        <span
          className={`overflow-hidden transition-all ${
            isCollapsed ? "w-0 ml-0" : "w-52 ml-3"
          }`}
        >
          {text}
        </span>
        {alert && !isCollapsed && (
          <div className="absolute right-4 w-2 h-2 rounded bg-blue-400" />
        )}
      </a>
    </li>
  );
};

// --- Sidebar Component ---
const Sidebar = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [pathname, setPathname] = useState("");

  useEffect(() => {
    // This check ensures window is defined, making it safe for SSR environments
    if (typeof window !== "undefined") {
      setPathname(window.location.pathname);
    }
  }, []);

  const roleSlug = pathname.split("/")[2] || "";
  const displayRole = formatRoleForDisplay(roleSlug);

  const menuItems: Omit<SidebarItemProps, "active">[] = useMemo(
    () => [
      {
        icon: LayoutDashboard,
        text: "Dashboard",
        href: `/dashboard/${roleSlug}`,
      },
      { icon: FileText, text: "Documents", href: "/dashboard/documents" },
      { icon: GitBranch, text: "Code", href: "/dashboard/code" },
      {
        icon: GitBranch,
        text: "Visual Architecture",
        href: "/dashboard/visual-architecture",
        alert: true,
      },
      {
        icon: CheckSquare,
        text: "Validation Panel",
        href: "/dashboard/validation-panel",
      },
      {
        icon: History,
        text: "Sync Timeline",
        href: "/dashboard/sync-timeline",
      },
      { icon: Download, text: "Export", href: "/dashboard/export" },
      {
        icon: ShieldCheck,
        text: "Audit Trail",
        href: "/dashboard/audit-trail",
      },
      { icon: Cog, text: "Settings & More", href: "/dashboard/settings" },
    ],
    [roleSlug]
  );

  return (
    <SidebarContext.Provider value={{ isCollapsed }}>
      <aside
        className={`h-screen sticky top-0 transition-all duration-300 ${
          isCollapsed ? "w-24" : "w-72"
        }`}
      >
        <nav className="h-full flex flex-col bg-white border-r border-gray-200 shadow-sm">
          <DokyDocLogo isCollapsed={isCollapsed} />
          <ul className="flex-1 px-4 mt-4">
            {menuItems.map((item) => (
              <SidebarItem
                key={item.text}
                {...item}
                active={pathname === item.href}
              />
            ))}
          </ul>
          <div className="border-t border-gray-200 p-4">
            <div className="flex items-center">
              <img
                src="https://i.pravatar.cc/40?u=a042581f4e29026704d"
                alt="User"
                className="w-10 h-10 rounded-full"
              />
              <div
                className={`flex justify-between items-center overflow-hidden transition-all ${
                  isCollapsed ? "w-0" : "w-40 ml-3"
                }`}
              >
                <div className="leading-4">
                  <h4 className="font-semibold">Muskan S.</h4>
                  <span className="text-xs text-gray-600">{displayRole}</span>
                </div>
                <LogOut
                  size={20}
                  className="text-gray-600 hover:text-red-500 cursor-pointer"
                />
              </div>
            </div>
          </div>
          <button
            onClick={() => setIsCollapsed((prev) => !prev)}
            className="absolute -right-3 top-16 p-1.5 rounded-full bg-white border border-gray-200 text-gray-600 hover:bg-gray-100"
          >
            {isCollapsed ? (
              <ChevronRight size={20} />
            ) : (
              <ChevronLeft size={20} />
            )}
          </button>
        </nav>
      </aside>
    </SidebarContext.Provider>
  );
};

// --- Top Bar Component ---
const TopBar = () => {
  const [displayRole, setDisplayRole] = useState("N/A");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const roleSlug = window.location.pathname.split("/")[2] || "";
      setDisplayRole(formatRoleForDisplay(roleSlug));
    }
  }, []);

  return (
    <header className="flex items-center justify-between h-16 bg-white border-b border-gray-200 px-6 sticky top-0 z-10">
      <div className="flex items-center gap-4">
        <button className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50">
          Project Switcher <ChevronsUpDown size={16} />
        </button>
        <button className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50">
          {displayRole} <ChevronsUpDown size={16} />
        </button>
        <div className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-green-700 bg-green-100 rounded-full">
          <span className="h-2.5 w-2.5 bg-green-500 rounded-full animate-pulse"></span>
          Sync Status
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button className="p-2 rounded-full hover:bg-gray-100">
          <Search size={20} className="text-gray-600" />
        </button>
        <button className="p-2 rounded-full hover:bg-gray-100 relative">
          <Bell size={20} className="text-gray-600" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500 border-2 border-white"></span>
        </button>
        <button className="p-2 rounded-full hover:bg-gray-100">
          <User size={20} className="text-gray-600" />
        </button>
      </div>
    </header>
  );
};

// --- Main Dashboard Layout ---
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex bg-gray-50 min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
