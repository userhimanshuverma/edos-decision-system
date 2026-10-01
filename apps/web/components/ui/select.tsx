import React, { useId } from "react";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  helperText?: string;
  placeholder?: string;
  options?: SelectOption[];
  children?: React.ReactNode;
}

export function Select({
  id: explicitId,
  label,
  error,
  helperText,
  placeholder,
  options,
  children,
  disabled,
  className = "",
  ...props
}: SelectProps) {
  const generatedId = useId();
  const selectId = explicitId || generatedId;
  const helperId = `${selectId}-helper`;
  const errorId = `${selectId}-error`;

  const hasError = Boolean(error);
  const describedBy = hasError
    ? errorId
    : helperText
    ? helperId
    : undefined;

  return (
    <div className={`edos-form-group ${disabled ? "edos-form-group--disabled" : ""}`.trim()}>
      {label && (
        <label htmlFor={selectId} className="edos-form-label">
          {label}
        </label>
      )}
      <div className="edos-select-wrapper">
        <select
          id={selectId}
          disabled={disabled}
          aria-invalid={hasError ? "true" : undefined}
          aria-describedby={describedBy}
          className={`edos-select ${hasError ? "edos-select--error" : ""} ${className}`.trim()}
          {...props}
        >
          {placeholder && (
            <option value="" disabled hidden>
              {placeholder}
            </option>
          )}
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        <span className="edos-select-chevron" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </span>
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
