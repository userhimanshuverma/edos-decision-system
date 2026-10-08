import React from "react";
import Link from "next/link";
import { navigationSections, NavItem } from "../../lib/navigation";
import { Badge } from "../ui/badge";

export interface SidebarProps {
  currentPath?: string;
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({
  currentPath = "/",
  isOpen = false,
  onClose,
}: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="edos-sidebar__backdrop"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`edos-sidebar ${isOpen ? "edos-sidebar--open" : ""}`.trim()}
        aria-label="Application navigation"
      >
        <div className="edos-sidebar__brand">
          <div className="edos-sidebar__brand-mark" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2L2 7L12 12L22 7L12 2Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M2 17L12 22L22 17"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M2 12L12 17L22 12"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div className="edos-sidebar__brand-meta">
            <span className="edos-sidebar__brand-name">EDOS</span>
            <span className="edos-sidebar__brand-sub">Decision OS</span>
          </div>
          <Badge variant="default" className="edos-sidebar__brand-badge">
            V1
          </Badge>
        </div>

        <nav className="edos-sidebar__nav">
          {navigationSections.map((section, sectionIdx) => (
            <div key={section.title || `section-${sectionIdx}`} className="edos-sidebar__section">
              {section.title && (
                <div className="edos-sidebar__section-title">
                  {section.title}
                </div>
              )}
              <ul className="edos-sidebar__list">
                {section.items.map((item: NavItem) => {
                  const isActive = currentPath === item.href;
                  return (
                    <li key={item.id} className="edos-sidebar__item">
                      {item.disabled ? (
                        <span
                          className="edos-sidebar__link edos-sidebar__link--disabled"
                          aria-disabled="true"
                          title="Module coming in later phase"
                        >
                          <span className="edos-sidebar__icon-slot">
                            {renderIcon(item.id)}
                          </span>
                          <span className="edos-sidebar__item-label">
                            {item.label}
                          </span>
                          {item.badge ? (
                            <Badge variant="neutral" className="edos-sidebar__item-badge">
                              {item.badge}
                            </Badge>
                          ) : (
                            <span className="edos-sidebar__item-tag">Planned</span>
                          )}
                        </span>
                      ) : (
                        <Link
                          href={item.href}
                          className={`edos-sidebar__link ${
                            isActive ? "edos-sidebar__link--active" : ""
                          }`}
                          aria-current={isActive ? "page" : undefined}
                          onClick={onClose}
                        >
                          <span className="edos-sidebar__icon-slot">
                            {renderIcon(item.id)}
                          </span>
                          <span className="edos-sidebar__item-label">
                            {item.label}
                          </span>
                          {item.badge && (
                            <Badge variant="default" className="edos-sidebar__item-badge">
                              {item.badge}
                            </Badge>
                          )}
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="edos-sidebar__footer">
          <div className="edos-sidebar__footer-meta">
            <span className="edos-sidebar__footer-label">Engine Protocol</span>
            <span className="edos-sidebar__footer-value">EDOS-OP-0.1</span>
          </div>
          <div className="edos-sidebar__footer-status">
            <span className="edos-sidebar__status-dot" aria-hidden="true" />
            <span>Ready for pipeline</span>
          </div>
        </div>
      </aside>
    </>
  );
}

function renderIcon(id: string) {
  switch (id) {
    case "overview":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="7" height="7" />
          <rect x="14" y="3" width="7" height="7" />
          <rect x="14" y="14" width="7" height="7" />
          <rect x="3" y="14" width="7" height="7" />
        </svg>
      );
    case "context":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
        </svg>
      );
    case "all-decisions":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      );
    case "products":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
        </svg>
      );
    case "inventory":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="16.5" y1="9.4" x2="7.5" y2="4.21" />
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
          <line x1="12" y1="22.08" x2="12" y2="12" />
        </svg>
      );
    case "suppliers":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      );
    case "audit-logs":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      );
    default:
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
        </svg>
      );
  }
}
