// components/auth/SelectRoleForm.tsx
"use client";

import { useState } from "react";
// We need to create AccessDenied.tsx as well for this to work
import { AccessDenied } from "./AccessDenied";
import { Button } from "@/components/ui/button";

const roles = ["CXO", "Developer", "BA", "Product Manager"];

// Make sure the "export" keyword is here
export function SelectRoleForm() {
  const [showAccessDenied, setShowAccessDenied] = useState(false);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  const handleNext = () => {
    if (!selectedRole) return;

    if (selectedRole === "CXO") {
      setShowAccessDenied(true);
    } else {
      alert(`Access granted for ${selectedRole}!`);
    }
  };

  if (showAccessDenied) {
    return <AccessDenied onBack={() => setShowAccessDenied(false)} />;
  }

  return (
    <div className="w-full max-w-sm space-y-8 p-4 text-center">
      <h1 className="text-3xl font-bold">Roles</h1>
      <div className="space-y-4">
        {roles.map((role) => (
          <Button
            key={role}
            variant={selectedRole === role ? "default" : "outline"}
            className="w-full justify-start p-6 text-left"
            onClick={() => setSelectedRole(role)}
          >
            {role}
          </Button>
        ))}
      </div>
      <Button onClick={handleNext} className="w-full" disabled={!selectedRole}>
        Next
      </Button>
    </div>
  );
}
