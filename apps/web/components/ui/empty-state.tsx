import React from "react";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  meta?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  meta,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`edos-empty-state ${className}`.trim()}>
      <div className="edos-empty-state__icon-wrapper" aria-hidden="true">
        {icon || (
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        )}
      </div>
      <h4 className="edos-empty-state__title">{title}</h4>
      {description && (
        <p className="edos-empty-state__description">{description}</p>
      )}
      {action && <div className="edos-empty-state__action">{action}</div>}
      {meta && <div className="edos-empty-state__meta">{meta}</div>}
    </div>
  );
}
