// frontend/app/page.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Page() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null); // State to hold error messages
  const router = useRouter();

  const handleLogin = async () => {
    setError(null); // Clear previous errors on a new attempt

    try {
      const response = await fetch(
        "http://localhost:8000/api/login/access-token",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: new URLSearchParams({
            username: email,
            password: password,
          }),
        }
      );

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("accessToken", data.access_token);
        router.push("/select-role");
      } else {
        // --- THIS IS THE UPDATED ERROR HANDLING ---
        // Read the detailed error message from the backend's response
        const errorData = await response.json();
        const errorMessage = errorData.detail || "An unknown error occurred.";
        console.error("Login failed:", errorMessage);
        setError(errorMessage); // Set the error message to be displayed in the UI
      }
    } catch (err) {
      console.error("A network error occurred:", err);
      setError("Unable to connect to the server. Please try again later.");
    }
  };

  return (
    <main className="flex h-screen w-full items-center justify-center">
      {/* Left Panel */}
      <div className="hidden h-full w-1/2 flex-col items-center justify-center space-y-4 bg-black text-white lg:flex">
        <Image
          src="/dockydoc-logo.jpg"
          alt="DockyDoc Logo"
          width={150}
          height={150}
        />
        <h1 className="text-5xl font-bold">DockyDoc</h1>
        <p className="text-xl text-muted-foreground">
          Visualize. Validate. Version.
        </p>
      </div>
      {/* Right Panel */}
      <div className="flex h-full w-full items-center justify-center bg-white lg:w-1/2">
        <div className="w-full max-w-sm space-y-6 p-4">
          <div className="space-y-2 text-left">
            <h1 className="text-3xl font-bold">Log in</h1>
          </div>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {/* --- ADD THIS TO DISPLAY THE ERROR MESSAGE --- */}
            {error && (
              <p className="text-sm font-medium text-red-500">{error}</p>
            )}
            {/* --------------------------------------------- */}

            <Button type="button" onClick={handleLogin} className="w-full">
              Log In
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
