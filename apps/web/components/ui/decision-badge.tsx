import React from "react";

export type DecisionState =
  | "Detected"
  | "Processing"
  | "Validated"
  | "Recommended"
  | "Pending Review"
  | "Approved"
  | "Rejected"
  | "Escalated";

export interface DecisionBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  state: DecisionState;
  showIcon?: boolean;
}

const STATE_CONFIG: Record<
  DecisionState,
  {
    className: string;
    dotColor: string;
    label: string;
  }
> = {
  Detected: {
    className: "edos-decision-badge--detected",
    dotColor: "var(--info)",
    label: "Detected",
  },
  Processing: {
    className: "edos-decision-badge--processing",
    dotColor: "var(--accent)",
    label: "Processing",
  },
  Validated: {
    className: "edos-decision-badge--validated",
    dotColor: "var(--info)",
    label: "Validated",
  },
  Recommended: {
    className: "edos-decision-badge--recommended",
    dotColor: "var(--accent)",
    label: "Recommended",
  },
  "Pending Review": {
    className: "edos-decision-badge--pending-review",
    dotColor: "var(--warning)",
    label: "Pending Review",
  },
  Approved: {
    className: "edos-decision-badge--approved",
    dotColor: "var(--success)",
    label: "Approved",
  },
  Rejected: {
    className: "edos-decision-badge--rejected",
    dotColor: "var(--danger)",
    label: "Rejected",
  },
  Escalated: {
    className: "edos-decision-badge--escalated",
    dotColor: "var(--warning)",
    label: "Escalated",
  },
};

export function DecisionBadge({
  state,
  showIcon = true,
  className = "",
  ...props
}: DecisionBadgeProps) {
  const config = STATE_CONFIG[state] || STATE_CONFIG.Detected;

  return (
    <span
      className={`edos-decision-badge ${config.className} ${className}`.trim()}
      {...props}
    >
      {showIcon && (
        <span
          className="edos-decision-badge__dot"
          style={{ backgroundColor: config.dotColor }}
          aria-hidden="true"
        />
      )}
      <span className="edos-decision-badge__label">{config.label}</span>
    </span>
  );
}
