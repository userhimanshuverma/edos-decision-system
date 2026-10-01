import React from "react";

export type TooltipPosition = "top" | "bottom" | "left" | "right";

export interface TooltipProps {
  content: React.ReactNode;
  position?: TooltipPosition;
  children: React.ReactElement;
  className?: string;
}

export function Tooltip({
  content,
  position = "top",
  children,
  className = "",
}: TooltipProps) {
  return (
    <span className={`edos-tooltip-wrapper ${className}`.trim()}>
      {children}
      <span
        role="tooltip"
        className={`edos-tooltip edos-tooltip--${position}`}
      >
        {content}
      </span>
    </span>
  );
}
