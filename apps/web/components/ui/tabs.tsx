import React from "react";
import { Badge } from "./badge";

export interface TabItem {
  id: string;
  label: string;
  badge?: string | number;
  disabled?: boolean;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
  ariaLabel?: string;
}

export function Tabs({
  tabs,
  activeTab,
  onChange,
  className = "",
  ariaLabel = "Tabs",
}: TabsProps) {
  return (
    <div className={`edos-tabs-container ${className}`.trim()}>
      <div className="edos-tabs" role="tablist" aria-label={ariaLabel}>
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              role="tab"
              type="button"
              id={`tab-${tab.id}`}
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.id}`}
              disabled={tab.disabled}
              className={`edos-tab ${isActive ? "edos-tab--active" : ""} ${tab.disabled ? "edos-tab--disabled" : ""}`.trim()}
              onClick={() => !tab.disabled && onChange(tab.id)}
            >
              <span className="edos-tab__label">{tab.label}</span>
              {tab.badge !== undefined && (
                <Badge
                  variant={isActive ? "default" : "neutral"}
                  className="edos-tab__badge"
                >
                  {tab.badge}
                </Badge>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
