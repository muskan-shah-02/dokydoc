// frontend/app/dashboard/page.tsx

"use client";

import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";

export default function DashboardPage() {
  const [devData, setDevData] = useState<string | null>(null);
  const [baData, setBaData] = useState<string | null>(null);
  const [cxoData, setCxoData] = useState<string | null>(null);
  const [pmData, setPmData] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async (endpoint: string, setData: (data: string) => void) => {
    const token = localStorage.getItem("accessToken");
    if (!token) {
      setError("You are not logged in.");
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/dashboard/${endpoint}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const result = await response.json();

      if (response.ok) {
        setData(result.message);
      } else {
        // If the user doesn't have the role, the API returns a 403 Forbidden error
        setData(`Access Denied: ${result.detail || 'You do not have the required role.'}`);
      }
    } catch (err) {
      setData("Failed to fetch data.");
    }
  };

  // Use a button to trigger the data fetching
  return (
    <main className="flex h-screen w-full flex-col items-center justify-center space-y-8">
      <h1 className="text-3xl font-bold">Dashboard</h1>

      <div className="w-full max-w-md space-y-4 rounded-lg border p-6">
        <h2 className="text-xl font-semibold">Protected Data</h2>
        <div className="flex items-center justify-between">
          <p>Developer Data:</p>
          <Button onClick={() => fetchData('developer-data', setDevData)}>Fetch</Button>
        </div>
        {devData && <p className="mt-2 rounded bg-gray-100 p-2 text-sm">{devData}</p>}

        <div className="flex items-center justify-between">
          <p>BA Data:</p>
          <Button onClick={() => fetchData('ba-data', setBaData)}>Fetch</Button>
        </div>
        {baData && <p className="mt-2 rounded bg-gray-100 p-2 text-sm">{baData}</p>}
        <div className="flex items-center justify-between">
          <p>CXO Data:</p>
          <Button onClick={() => fetchData('cxo-data', setCxoData)}>Fetch</Button>
        </div>
        {cxoData && <p className="mt-2 rounded bg-gray-100 p-2 text-sm">{cxoData}</p>}
        <div className="flex items-center justify-between">
          <p>PM Data:</p>
          <Button onClick={() => fetchData('pm-data', setPmData)}>Fetch</Button>
        </div>
        {pmData && <p className="mt-2 rounded bg-gray-100 p-2 text-sm">{pmData}</p>}
      </div>

      {error && <p className="text-red-500">{error}</p>}
    </main>
  );
}