import React from "react";

export interface LoadingStateProps {
  label?: string;
  sublabel?: string;
  type?: "spinner" | "skeleton";
  className?: string;
}

export function LoadingState({
  label = "Processing operational data...",
  sublabel,
  type = "spinner",
  className = "",
}: LoadingStateProps) {
  if (type === "skeleton") {
    return (
      <div className={`edos-loading-skeleton-container ${className}`.trim()} role="status" aria-busy="true">
        <div className="edos-skeleton edos-skeleton--header" />
        <div className="edos-skeleton edos-skeleton--row" />
        <div className="edos-skeleton edos-skeleton--row" />
        <div className="edos-skeleton edos-skeleton--row-short" />
        <span className="edos-sr-only">{label}</span>
      </div>
    );
  }

  return (
    <div className={`edos-loading-state ${className}`.trim()} role="status" aria-busy="true">
      <div className="edos-spinner" aria-hidden="true" />
      <span className="edos-loading-label">{label}</span>
      {sublabel && <span className="edos-loading-sublabel">{sublabel}</span>}
      <span className="edos-sr-only">{label}</span>
    </div>
  );
}
