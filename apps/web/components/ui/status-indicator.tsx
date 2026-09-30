import React from "react";

export type StatusTone = "ready" | "active" | "warning" | "danger" | "neutral";

export interface StatusIndicatorProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: StatusTone;
  label: string;
  pulse?: boolean;
}

export function StatusIndicator({
  tone = "ready",
  label,
  pulse = false,
  className = "",
  ...props
}: StatusIndicatorProps) {
  const toneClass = `edos-status--${tone}`;
  const pulseClass = pulse ? "edos-status__dot--pulse" : "";

  return (
    <span
      role="status"
      className={`edos-status ${toneClass} ${className}`.trim()}
      {...props}
    >
      <span className={`edos-status__dot ${pulseClass}`.trim()} aria-hidden="true" />
      <span className="edos-status__label">{label}</span>
    </span>
  );
}
