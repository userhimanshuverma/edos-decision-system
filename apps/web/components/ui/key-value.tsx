import React from "react";

export interface KeyValueItem {
  label: string;
  value: React.ReactNode;
  badge?: React.ReactNode;
  description?: string;
  monospace?: boolean;
}

export interface KeyValueProps {
  items: KeyValueItem[];
  columns?: 1 | 2 | 3 | 4;
  layout?: "horizontal" | "vertical";
  className?: string;
}

export function KeyValue({
  items,
  columns = 2,
  layout = "vertical",
  className = "",
}: KeyValueProps) {
  const gridClass = `edos-kv--cols-${columns}`;
  const layoutClass = `edos-kv--${layout}`;

  return (
    <dl className={`edos-kv-grid ${gridClass} ${layoutClass} ${className}`.trim()}>
      {items.map((item, idx) => (
        <div key={idx} className="edos-kv-item">
          <dt className="edos-kv-label">{item.label}</dt>
          <dd className="edos-kv-value-group">
            <span className={`edos-kv-value ${item.monospace ? "edos-kv-value--mono" : ""}`.trim()}>
              {item.value}
            </span>
            {item.badge && <span className="edos-kv-badge">{item.badge}</span>}
            {item.description && (
              <span className="edos-kv-desc">{item.description}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
