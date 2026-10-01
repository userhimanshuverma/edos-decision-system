import React from "react";

export type BadgeVariant =
  | "default"
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "outline";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: React.ReactNode;
}

export function Badge({
  variant = "default",
  className = "",
  children,
  ...props
}: BadgeProps) {
  const baseClass = "edos-badge";
  const variantClass = `edos-badge--${variant}`;
  const combinedClassName = [baseClass, variantClass, className]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={combinedClassName} {...props}>
      {children}
    </span>
  );
}
