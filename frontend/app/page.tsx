// app/page.tsx

// This directive must be at the top
"use client";

import { useState } from "react";
// ADD THIS LINE: Import the router for navigation
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Page() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // ADD THIS LINE: Initialize the router
  const router = useRouter();

  const handleLogin = async () => {
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
        // Assuming the token is in data.access_token
        // You would typically store this token in local storage or a cookie
        console.log("Login successful, token:", data.access_token);
        router.push("/select-role");
      } else {
        // Handle login error
        console.error("Login failed");
        // You might want to show an error message to the user
      }
    } catch (error) {
      console.error("An error occurred during login:", error);
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
            {/* The onClick handler for this button will now trigger the navigation */}
            <Button type="submit" className="w-full" onClick={handleLogin}>
              Log In
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
