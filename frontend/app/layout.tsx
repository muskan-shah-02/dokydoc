import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProjectProvider } from "@/contexts/ProjectContext";
import { NotificationProvider } from "@/contexts/NotificationContext";
import { BillingNotificationProvider } from "@/components/BillingToast";

export const metadata: Metadata = {
  title: "DokyDoc - Document Governance Platform",
  description: "AI-powered document analysis and governance with multi-tenancy support",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>
          <ProjectProvider>
            <NotificationProvider>
              <BillingNotificationProvider>
                {children}
              </BillingNotificationProvider>
            </NotificationProvider>
          </ProjectProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
