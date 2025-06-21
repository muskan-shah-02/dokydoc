"use client";

import { useState, useEffect } from "react";
import { SelectRoleForm } from "@/components/auth/SelectRoleForm";

interface User {
  email: string;
  is_active: boolean;
  roles: string[];
  id: number;
}

export default function SelectRolePage() {
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      console.log("[1] Starting fetchUser function...");
      const token = localStorage.getItem("accessToken");

      if (!token) {
        console.error("[2] Token not found in localStorage.");
        setError("Authentication token not found. Please log in again.");
        setLoading(false);
        return;
      }
      console.log("[2] Token found.");

      try {
        console.log("[3] Sending fetch request to /api/users/me...");
        const response = await fetch("http://localhost:8000/api/users/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        console.log(
          "[4] Received response from server. Status:",
          response.status
        );

        if (response.ok) {
          console.log(
            "[5] Response is OK (2xx status). Reading response body as text..."
          );
          const responseText = await response.text();
          console.log("[6] Raw response text:", responseText);

          try {
            console.log("[7] Parsing response text as JSON...");
            const userData = JSON.parse(responseText);
            console.log("[8] JSON parsing successful. Setting user state.");
            setUser(userData);
          } catch (jsonError) {
            console.error("[8] FAILED to parse JSON.", jsonError);
            setError("Received an invalid response from the server.");
          }
        } else {
          console.error("[5] Response is NOT OK. Status:", response.status);
          setError("Failed to fetch user data.");
        }
      } catch (networkError) {
        console.error("[3] FETCH FAILED with network error.", networkError);
        setError("An error occurred while fetching user data.");
      } finally {
        console.log("[9] Fetch process finished.");
        setLoading(false);
      }
    };

    fetchUser();
  }, []);

  if (loading) {
    return (
      <main className="flex h-screen w-full items-center justify-center">
        <p>Loading...</p>
      </main>
    );
  }

  if (error || !user) {
    return (
      <main className="flex h-screen w-full items-center justify-center">
        <p className="text-red-500">{error || "User not found."}</p>
      </main>
    );
  }

  return (
    <main className="flex h-screen w-full items-center justify-center">
      <div className="w-full max-w-md">
        <h1 className="mb-4 text-center text-2xl font-bold">
          Welcome, {user.email}!
        </h1>
        <p className="mb-8 text-center text-muted-foreground">
          Please select your role to continue.
        </p>
        <SelectRoleForm userRoles={user.roles} />
      </div>
    </main>
  );
}
