/*
  This is the updated code for your EXISTING file at:
  frontend/components/auth/SelectRoleForm.tsx
*/
"use client";

import { useState } from "react";
// import { useRouter } from "next/navigation"; // Removed for compatibility
import { Button } from "@/components/ui/button";

interface SelectRoleFormProps {
  userRoles: string[];
}

export function SelectRoleForm({ userRoles }: SelectRoleFormProps) {
  const [selectedRole, setSelectedRole] = useState<string>("");
  // const router = useRouter(); // Replaced with window.location.href

  const availableRoles = ["CXO", "BA", "Developer", "Product Manager"];

  const handleRoleSelect = () => {
    if (!selectedRole) {
      alert("Please select a role to continue.");
      return;
    }

    // Convert the selected role into a URL-friendly slug
    // e.g., "Product Manager" becomes "product-manager"
    const roleSlug = selectedRole.toLowerCase().replace(/ /g, "-");

    if (userRoles.includes(selectedRole)) {
      // Navigate using standard browser location method
      window.location.href = `/dashboard/${roleSlug}`;
    } else {
      window.location.href = "/access-denied";
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {availableRoles.map((role) => (
          <Button
            key={role}
            variant={selectedRole === role ? "default" : "outline"}
            onClick={() => setSelectedRole(role)}
            className="w-full"
          >
            {role}
          </Button>
        ))}
      </div>
      <Button onClick={handleRoleSelect} className="w-full">
        Continue as {selectedRole || "..."}
      </Button>
    </div>
  );
}
