import React from "react";

export type TimelineStatus = "completed" | "current" | "upcoming" | "error";

export interface TimelineItem {
  id: string;
  title: string;
  description?: React.ReactNode;
  time?: string;
  status?: TimelineStatus;
  badge?: React.ReactNode;
}

export interface TimelineProps {
  items: TimelineItem[];
  className?: string;
}

export function Timeline({ items, className = "" }: TimelineProps) {
  return (
    <div className={`edos-timeline ${className}`.trim()} role="list">
      {items.map((item, index) => {
        const status = item.status || "upcoming";
        const isLast = index === items.length - 1;

        return (
          <div
            key={item.id}
            role="listitem"
            className={`edos-timeline-step edos-timeline-step--${status} ${isLast ? "edos-timeline-step--last" : ""}`.trim()}
          >
            <div className="edos-timeline-indicator">
              <div className="edos-timeline-node">
                {status === "completed" && (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
                {status === "current" && <span className="edos-timeline-pulse-dot" />}
                {status === "error" && (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                )}
              </div>
              {!isLast && <div className="edos-timeline-track" />}
            </div>

            <div className="edos-timeline-content">
              <div className="edos-timeline-header">
                <span className="edos-timeline-title">{item.title}</span>
                {item.badge && <span className="edos-timeline-badge">{item.badge}</span>}
                {item.time && <span className="edos-timeline-time">{item.time}</span>}
              </div>
              {item.description && (
                <div className="edos-timeline-description">{item.description}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
