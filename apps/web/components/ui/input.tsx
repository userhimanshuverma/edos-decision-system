import React, { useId } from "react";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
}

export function Input({
  id: explicitId,
  label,
  error,
  helperText,
  startIcon,
  endIcon,
  disabled,
  className = "",
  type = "text",
  ...props
}: InputProps) {
  const generatedId = useId();
  const inputId = explicitId || generatedId;
  const helperId = `${inputId}-helper`;
  const errorId = `${inputId}-error`;

  const hasError = Boolean(error);
  const describedBy = hasError
    ? errorId
    : helperText
    ? helperId
    : undefined;

  return (
    <div className={`edos-form-group ${disabled ? "edos-form-group--disabled" : ""}`.trim()}>
      {label && (
        <label htmlFor={inputId} className="edos-form-label">
          {label}
        </label>
      )}
      <div className="edos-input-wrapper">
        {startIcon && <span className="edos-input-icon edos-input-icon--start">{startIcon}</span>}
        <input
          id={inputId}
          type={type}
          disabled={disabled}
          aria-invalid={hasError ? "true" : undefined}
          aria-describedby={describedBy}
          className={`edos-input ${hasError ? "edos-input--error" : ""} ${startIcon ? "edos-input--with-start-icon" : ""} ${endIcon ? "edos-input--with-end-icon" : ""} ${className}`.trim()}
          {...props}
        />
        {endIcon && <span className="edos-input-icon edos-input-icon--end">{endIcon}</span>}
      </div>
      {hasError ? (
        <p id={errorId} className="edos-form-error" role="alert">
          {error}
        </p>
      ) : helperText ? (
        <p id={helperId} className="edos-form-helper">
          {helperText}
        </p>
      ) : null}
    </div>
  );
}
