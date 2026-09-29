import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EDOS — Enterprise Decision Operating System",
  description: "Decision intelligence for operational systems.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
