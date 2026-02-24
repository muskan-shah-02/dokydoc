import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProjectProvider } from "@/contexts/ProjectContext";
import { BillingNotificationProvider } from "@/components/BillingToast";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

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
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <ProjectProvider>
            <BillingNotificationProvider>
              {children}
            </BillingNotificationProvider>
          </ProjectProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
