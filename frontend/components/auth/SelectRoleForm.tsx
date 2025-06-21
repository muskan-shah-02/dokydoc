// frontend/components/auth/SelectRoleForm.tsx

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

// The component only needs the user's roles now
interface SelectRoleFormProps {
  userRoles: string[];
}

export function SelectRoleForm({ userRoles }: SelectRoleFormProps) {
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const router = useRouter();

  const availableRoles = ["CXO", "BA", "Developer", "Product Manager"];

  const handleRoleSelect = () => {
    if (!selectedRole) {
      alert("Please select a role.");
      return;
    }
    // --- ADD THESE THREE LINES FOR DEBUGGING ---
    console.log("------ Role Check ------");
    console.log("Role Selected in UI:", selectedRole);
    console.log("Roles Assigned to User (from backend):", userRoles);
    // -----------------------------------------
    // Check if the selected role is valid for the current user
    if (userRoles.includes(selectedRole)) {
      console.log(`Access granted for role: ${selectedRole}`);
      router.push("/dashboard");
    } else {
      // If access is denied, redirect to the separate page
      console.log(
        `Access denied for role: ${selectedRole}. User roles: [${userRoles.join(
          ", "
        )}]`
      );
      router.push("/access-denied");
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
      <Button
        onClick={handleRoleSelect}
        disabled={!selectedRole}
        className="w-full"
      >
        Continue
      </Button>
    </div>
  );
}
