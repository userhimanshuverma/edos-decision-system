"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { Header } from "./header";
import { Sidebar } from "./sidebar";

export interface AppShellProps {
  children: React.ReactNode;
  currentSection?: string;
  currentPath?: string;
}

function resolveSectionName(pathname: string): string {
  if (pathname.startsWith("/context")) return "Decision Context";
  if (pathname.startsWith("/design-system")) return "Design System";
  if (pathname.startsWith("/decisions")) return "Decisions";
  if (pathname.startsWith("/supply-chain/products")) return "Products";
  if (pathname.startsWith("/supply-chain/inventory")) return "Inventory";
  if (pathname.startsWith("/supply-chain/suppliers")) return "Suppliers";
  if (pathname.startsWith("/supply-chain")) return "Supply Chain";
  if (pathname.startsWith("/audit")) return "Audit";
  return "Overview";
}

export function AppShell({
  children,
  currentSection,
  currentPath,
}: AppShellProps) {
  const pathname = usePathname() || "/";
  const activePath = currentPath || pathname;
  const activeSection = currentSection || resolveSectionName(activePath);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const closeSidebar = () => {
    setIsSidebarOpen(false);
  };

  return (
    <div className="edos-shell">
      <Header
        currentSection={activeSection}
        onToggleSidebar={toggleSidebar}
        isSidebarOpen={isSidebarOpen}
      />
      <div className="edos-shell__body">
        <Sidebar
          currentPath={activePath}
          isOpen={isSidebarOpen}
          onClose={closeSidebar}
        />
        <main id="main-content" className="edos-shell__workspace" tabIndex={-1}>
          <div className="edos-shell__content-container">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
