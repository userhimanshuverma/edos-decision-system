import React from "react";
import { StatusIndicator } from "../ui/status-indicator";

export interface HeaderProps {
  currentSection?: string;
  onToggleSidebar?: () => void;
  isSidebarOpen?: boolean;
}

export function Header({
  currentSection = "Overview",
  onToggleSidebar,
  isSidebarOpen = false,
}: HeaderProps) {
  return (
    <header className="edos-header" role="banner">
      <div className="edos-header__left">
        {onToggleSidebar && (
          <button
            type="button"
            className="edos-header__toggle-btn"
            onClick={onToggleSidebar}
            aria-label={isSidebarOpen ? "Close navigation sidebar" : "Open navigation sidebar"}
            aria-expanded={isSidebarOpen}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        )}

        <div className="edos-header__brand-context">
          <span className="edos-header__brand-tag">EDOS</span>
          <span className="edos-header__separator" aria-hidden="true">/</span>
          <span className="edos-header__section-title">{currentSection}</span>
        </div>
      </div>

      <div className="edos-header__center">
        <div className="edos-header__search-placeholder" aria-label="Global search (disabled placeholder)">
          <svg
            className="edos-header__search-icon"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span className="edos-header__search-text">Quick find (⌘K)...</span>
          <span className="edos-header__search-shortcut" aria-hidden="true">⌘K</span>
        </div>
      </div>

      <div className="edos-header__right">
        <div className="edos-header__status">
          <StatusIndicator tone="ready" label="System Ready" pulse />
        </div>

        <div className="edos-header__user-placeholder" title="Current Operator Context">
          <span className="edos-header__user-avatar" aria-hidden="true">OP</span>
          <span className="edos-header__user-label">Operator</span>
        </div>
      </div>
    </header>
  );
}
