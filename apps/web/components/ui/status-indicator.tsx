import React from "react";

export type StatusState =
  | "ready"
  | "active"
  | "processing"
  | "pending"
  | "warning"
  | "error"
  | "neutral";

export interface StatusIndicatorProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: StatusState;
  state?: StatusState | "READY" | "ACTIVE" | "PROCESSING" | "PENDING" | "WARNING" | "ERROR";
  label: string;
  pulse?: boolean;
}

export function StatusIndicator({
  tone,
  state,
  label,
  pulse = false,
  className = "",
  ...props
}: StatusIndicatorProps) {
  // Support either tone or state prop, normalized to lowercase
  const rawState = (state || tone || "ready").toString().toLowerCase() as StatusState;
  const normalizedTone = rawState === ("danger" as unknown) ? "error" : rawState;
  const toneClass = `edos-status--${normalizedTone}`;
  const pulseClass = pulse ? "edos-status__dot--pulse" : "";

  return (
    <span
      role="status"
      className={`edos-status ${toneClass} ${className}`.trim()}
      {...props}
    >
      <span className={`edos-status__dot ${pulseClass}`.trim()} aria-hidden="true" />
      <span className="edos-status__label">{label}</span>
      <span className="edos-sr-only">Status: {label}</span>
    </span>
  );
}
