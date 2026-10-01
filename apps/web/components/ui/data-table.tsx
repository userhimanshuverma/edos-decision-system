import React from "react";

export type ColumnAlign = "left" | "center" | "right";

export interface ColumnDef<T> {
  key: string;
  header: React.ReactNode;
  align?: ColumnAlign;
  width?: string | number;
  render?: (row: T, index: number) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  keyField?: keyof T | ((row: T, index: number) => string | number);
  density?: "compact" | "comfortable";
  hoverable?: boolean;
  selectedId?: string | number;
  onRowClick?: (row: T, index: number) => void;
  emptyMessage?: React.ReactNode;
  caption?: string;
  className?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  keyField = "id" as keyof T,
  density = "comfortable",
  hoverable = true,
  selectedId,
  onRowClick,
  emptyMessage = "No records found.",
  caption,
  className = "",
}: DataTableProps<T>) {
  const getRowKey = (row: T, index: number): string | number => {
    if (typeof keyField === "function") {
      return keyField(row, index);
    }
    const val = row[keyField];
    if (val !== undefined && val !== null) {
      return String(val);
    }
    return index;
  };

  return (
    <div className={`edos-table-container edos-table--${density} ${className}`.trim()}>
      <table className="edos-table">
        {caption && <caption className="edos-sr-only">{caption}</caption>}
        <thead className="edos-table__head">
          <tr className="edos-table__head-row">
            {columns.map((col) => {
              const alignClass = col.align ? `edos-table__cell--${col.align}` : "";
              return (
                <th
                  key={col.key}
                  scope="col"
                  style={col.width ? { width: col.width } : undefined}
                  className={`edos-table__th ${alignClass}`.trim()}
                >
                  {col.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="edos-table__body">
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="edos-table__empty-cell"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, index) => {
              const key = getRowKey(row, index);
              const isSelected = selectedId !== undefined && selectedId === key;
              const rowClass = [
                "edos-table__row",
                hoverable ? "edos-table__row--hoverable" : "",
                isSelected ? "edos-table__row--selected" : "",
                onRowClick ? "edos-table__row--clickable" : "",
              ]
                .filter(Boolean)
                .join(" ");

              return (
                <tr
                  key={key}
                  className={rowClass}
                  onClick={onRowClick ? () => onRowClick(row, index) : undefined}
                >
                  {columns.map((col) => {
                    const alignClass = col.align ? `edos-table__cell--${col.align}` : "";
                    const content = col.render
                      ? col.render(row, index)
                      : (row[col.key] as React.ReactNode);

                    return (
                      <td
                        key={col.key}
                        className={`edos-table__td ${alignClass}`.trim()}
                      >
                        {content}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
