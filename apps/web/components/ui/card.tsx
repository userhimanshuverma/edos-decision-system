import React from "react";

export interface CardProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title?: React.ReactNode;
  description?: React.ReactNode;
  headerAction?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  elevated?: boolean;
}

export function Card({
  title,
  description,
  headerAction,
  children,
  footer,
  elevated = false,
  className = "",
  ...props
}: CardProps) {
  const hasHeader = Boolean(title || description || headerAction);
  const elevationClass = elevated ? "edos-card--elevated" : "";

  return (
    <div className={`edos-card ${elevationClass} ${className}`.trim()} {...props}>
      {hasHeader && (
        <div className="edos-card__header">
          <div className="edos-card__titles">
            {title && <h3 className="edos-card__title">{title}</h3>}
            {description && (
              <p className="edos-card__description">{description}</p>
            )}
          </div>
          {headerAction && (
            <div className="edos-card__action">{headerAction}</div>
          )}
        </div>
      )}
      <div className="edos-card__content">{children}</div>
      {footer && <div className="edos-card__footer">{footer}</div>}
    </div>
  );
}
