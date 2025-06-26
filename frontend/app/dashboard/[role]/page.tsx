/*
  This is the content for your NEW file located at:
  frontend/app/dashboard/[role]/page.tsx
*/
"use client";

import React, { useState, useEffect, ElementType } from "react";
import {
  AlertTriangle,
  CheckCircle,
  BarChart,
  User,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";

// --- Type Definitions for Dashboard Data ---

interface ActivityItem {
  description: string;
  time: string;
}

interface CXOData {
  alerts: { total: number };
  approvals: { pending: number };
  healthScore: number;
  activeUsers: number;
  recentActivity: ActivityItem[];
}

interface DeveloperData {
  myMismatches: number;
  myReviews: number;
  syncedComponents: number;
  avgResolutionTime: string;
  recentCommits: ActivityItem[];
}

// --- Reusable Widget Components ---

interface StatCardProps {
  title: string;
  value: string | number;
  icon: ElementType;
  color: string;
}

const StatCard = ({ title, value, icon: Icon, color }: StatCardProps) => (
  <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex items-center gap-4">
    <div
      className={`w-12 h-12 rounded-lg flex items-center justify-center ${color}`}
    >
      <Icon className="text-white" size={24} />
    </div>
    <div>
      <p className="text-gray-500 text-sm">{title}</p>
      <p className="text-2xl font-bold text-gray-800">{value}</p>
    </div>
  </div>
);

interface ListCardProps {
  title: string;
  items: ActivityItem[];
}

const ListCard = ({ title, items }: ListCardProps) => (
  <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm col-span-1 md:col-span-2">
    <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
    <ul className="space-y-3">
      {items.map((item, index) => (
        <li key={index} className="flex items-center justify-between text-sm">
          <p className="text-gray-700">{item.description}</p>
          <span className="text-gray-400">{item.time}</span>
        </li>
      ))}
    </ul>
  </div>
);

// --- Role-Specific Dashboard Components ---

const CXODashboard = ({ data }: { data: CXOData }) => (
  <div className="space-y-6">
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        title="Mismatch Alerts"
        value={data.alerts.total}
        icon={AlertTriangle}
        color="bg-red-500"
      />
      <StatCard
        title="Pending Approvals"
        value={data.approvals.pending}
        icon={CheckCircle}
        color="bg-yellow-500"
      />
      <StatCard
        title="System Health"
        value={`${data.healthScore}%`}
        icon={BarChart}
        color="bg-green-500"
      />
      <StatCard
        title="Active Users"
        value={data.activeUsers}
        icon={User}
        color="bg-blue-500"
      />
    </div>
    <ListCard title="Recent Activity" items={data.recentActivity} />
  </div>
);

const DeveloperDashboard = ({ data }: { data: DeveloperData }) => (
  <div className="space-y-6">
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        title="My Open Mismatches"
        value={data.myMismatches}
        icon={AlertTriangle}
        color="bg-red-500"
      />
      <StatCard
        title="Awaiting My Review"
        value={data.myReviews}
        icon={Clock}
        color="bg-purple-500"
      />
      <StatCard
        title="Synced Components"
        value={data.syncedComponents}
        icon={CheckCircle}
        color="bg-green-500"
      />
      <StatCard
        title="Avg. Resolution Time"
        value={data.avgResolutionTime}
        icon={Clock}
        color="bg-blue-500"
      />
    </div>
    <ListCard title="My Recent Commits" items={data.recentCommits} />
  </div>
);

// --- The Main Dynamic Page Component ---

export default function RoleDashboardPage() {
  const [role, setRole] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Get the role from the URL path on the client side
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pathParts = window.location.pathname.split("/");
      // The role is the last part of the URL, e.g., /dashboard/cxo -> 'cxo'
      const roleFromPath = pathParts.pop() || "";
      setRole(roleFromPath);
    }
  }, []);

  // Fetch data when the role is determined
  useEffect(() => {
    if (!role) return;

    const fetchDataForRole = async () => {
      setIsLoading(true);
      setError(null);
      const token = localStorage.getItem("accessToken");

      if (!token) {
        setError("Authentication token not found. Please log in again.");
        setIsLoading(false);
        return;
      }

      try {
        // We are calling the backend endpoint that you will build.
        const response = await fetch(
          `http://localhost:8000/api/dashboard/${role}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `Error fetching data`);
        }
        const data = await response.json();
        setDashboardData(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDataForRole();
  }, [role]);

  if (isLoading) {
    return <div className="text-center p-10">Loading Dashboard...</div>;
  }

  if (error) {
    return <div className="text-center p-10 text-red-500">Error: {error}</div>;
  }

  // Render the correct dashboard component based on the role from the URL
  const renderDashboardContent = () => {
    switch (role?.toLowerCase()) {
      case "cxo":
        return <CXODashboard data={dashboardData} />;
      case "dev":
        return <DeveloperDashboard data={dashboardData} />;
      // You can add more roles here later, like 'qa' or 'ba'
      default:
        return (
          <div>
            Dashboard for role '<strong>{role}</strong>' is not yet implemented.
          </div>
        );
    }
  };

  return (
    <div>
      <h1 className="text-3xl font-bold capitalize mb-6">{role} Dashboard</h1>
      {renderDashboardContent()}
    </div>
  );
}
