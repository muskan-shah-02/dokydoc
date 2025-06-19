// app/select-role/page.tsx
import Image from "next/image";
import { SelectRoleForm } from "@/components/auth/SelectRoleForm"; // Import the component you created

export default function SelectRolePage() {
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
        <SelectRoleForm />
      </div>
    </main>
  );
}
