import React from "react";
import { Button } from "./button";

export interface ErrorStateProps {
  title?: string;
  message: string;
  code?: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

export function ErrorState({
  title = "Operational Error Encountered",
  message,
  code,
  onRetry,
  retryLabel = "Retry Operation",
  className = "",
}: ErrorStateProps) {
  return (
    <div className={`edos-error-state ${className}`.trim()} role="alert">
      <div className="edos-error-state__icon-wrapper" aria-hidden="true">
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
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <div className="edos-error-state__content">
        <h4 className="edos-error-state__title">{title}</h4>
        <p className="edos-error-state__message">{message}</p>
        {code && (
          <span className="edos-error-state__code">
            Error Code: <code>{code}</code>
          </span>
        )}
      </div>
      {onRetry && (
        <div className="edos-error-state__actions">
          <Button variant="outline" size="sm" onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      )}
    </div>
  );
}
