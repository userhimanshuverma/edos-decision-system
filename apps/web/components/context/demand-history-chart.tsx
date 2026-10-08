"use client";

import React, { useState } from "react";
import { DemandContext } from "../../lib/types/context";
import { DailyDemandPoint } from "../../lib/types/demand";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { DataTable, ColumnDef } from "../ui/data-table";

export interface DemandHistoryChartProps {
  demand: DemandContext | null;
}

interface TableRowData extends Record<string, unknown> {
  id: string;
  date: string;
  quantity: number;
  variance: number;
}

export function DemandHistoryChart({ demand }: DemandHistoryChartProps) {
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!demand || !demand.history || demand.history.length === 0) {
    return (
      <Card
        title="Historical Demand Behavior"
        description="Chronological record of daily inventory consumption at this facility."
      >
        <div className="edos-demand-empty">
          <p>No historical demand points recorded for this product and warehouse.</p>
        </div>
      </Card>
    );
  }

  const { history, average_daily_demand, total_demand, trend_direction, percentage_change, window_days } = demand;

  // Chart dimensions & scaling
  const maxQty = Math.max(...history.map((pt) => pt.quantity), 10);
  const chartHeight = 180;
  const chartWidth = 600;
  const paddingLeft = 40;
  const paddingRight = 20;
  const paddingTop = 25;
  const paddingBottom = 35;

  const innerWidth = chartWidth - paddingLeft - paddingRight;
  const innerHeight = chartHeight - paddingTop - paddingBottom;

  const barWidth = Math.max(12, Math.min(28, (innerWidth / history.length) * 0.65));
  const stepX = innerWidth / (history.length || 1);

  // Y-axis tick values
  const yTicks = [0, Math.round(maxQty / 2), maxQty];

  // Table rows for secondary view
  const tableRows: TableRowData[] = history.map((pt, idx) => ({
    id: `row-${idx}`,
    date: pt.date,
    quantity: pt.quantity,
    variance: Number((pt.quantity - average_daily_demand).toFixed(2)),
  }));

  const tableColumns: ColumnDef<TableRowData>[] = [
    {
      key: "date",
      header: "Observation Date",
      render: (row) => <span className="edos-type-mono">{String(row.date)}</span>,
    },
    {
      key: "quantity",
      header: "Consumed Units",
      align: "right",
      render: (row) => (
        <span className="edos-type-mono" style={{ fontWeight: 600 }}>
          {Number(row.quantity).toLocaleString()}
        </span>
      ),
    },
    {
      key: "variance",
      header: "Variance vs Mean",
      align: "right",
      render: (row) => {
        const v = Number(row.variance);
        const sign = v > 0 ? `+${v}` : `${v}`;
        const color = v > 0 ? "var(--warning)" : v < 0 ? "var(--info)" : "var(--text-muted)";
        return (
          <span className="edos-type-mono" style={{ color }}>
            {sign}
          </span>
        );
      },
    },
  ];

  const avgY =
    paddingTop + innerHeight - (average_daily_demand / maxQty) * innerHeight;

  return (
    <Card
      title="Historical Demand Observation"
      description="Observed daily consumption points over the active historical observation window."
      headerAction={
        <div className="edos-demand-header-controls">
          <div className="edos-segmented-control" role="tablist" aria-label="Demand view mode">
            <button
              type="button"
              className={`edos-segmented-btn ${viewMode === "chart" ? "edos-segmented-btn--active" : ""}`}
              onClick={() => setViewMode("chart")}
              role="tab"
              aria-selected={viewMode === "chart"}
            >
              Observed Chart
            </button>
            <button
              type="button"
              className={`edos-segmented-btn ${viewMode === "table" ? "edos-segmented-btn--active" : ""}`}
              onClick={() => setViewMode("table")}
              role="tab"
              aria-selected={viewMode === "table"}
            >
              Data Log ({history.length})
            </button>
          </div>
        </div>
      }
    >
      {/* Top summary metrics */}
      <div className="edos-demand-summary-strip">
        <div className="edos-demand-summary-item">
          <span className="edos-demand-summary-label">TOTAL CONSUMED</span>
          <span className="edos-demand-summary-val">{total_demand.toLocaleString()} units</span>
        </div>
        <div className="edos-demand-summary-item">
          <span className="edos-demand-summary-label">DAILY AVERAGE (MEAN)</span>
          <span className="edos-demand-summary-val">{average_daily_demand.toFixed(2)} units/day</span>
        </div>
        <div className="edos-demand-summary-item">
          <span className="edos-demand-summary-label">OBSERVED WINDOW</span>
          <span className="edos-demand-summary-val">{window_days} calendar days</span>
        </div>
        <div className="edos-demand-summary-item">
          <span className="edos-demand-summary-label">TRAJECTORY SHIFT</span>
          <span className="edos-demand-summary-val">
            <Badge
              variant={
                trend_direction === "increasing"
                  ? "warning"
                  : trend_direction === "decreasing"
                  ? "info"
                  : "neutral"
              }
            >
              {trend_direction === "increasing" ? "↑" : trend_direction === "decreasing" ? "↓" : "→"}{" "}
              {trend_direction.toUpperCase()} ({percentage_change > 0 ? `+${percentage_change}%` : `${percentage_change}%`})
            </Badge>
          </span>
        </div>
      </div>

      {viewMode === "chart" ? (
        <div className="edos-chart-container">
          <svg
            viewBox={`0 0 ${chartWidth} ${chartHeight}`}
            className="edos-demand-svg"
            role="img"
            aria-label="Observed historical daily demand bar chart"
          >
            {/* Grid Lines & Y Axis Ticks */}
            {yTicks.map((val) => {
              const y = paddingTop + innerHeight - (val / maxQty) * innerHeight;
              return (
                <g key={val} className="edos-chart-grid-row">
                  <line
                    x1={paddingLeft}
                    y1={y}
                    x2={chartWidth - paddingRight}
                    y2={y}
                    stroke="var(--border)"
                    strokeWidth="1"
                    strokeDasharray={val === 0 ? "none" : "3,3"}
                  />
                  <text
                    x={paddingLeft - 8}
                    y={y + 4}
                    textAnchor="end"
                    className="edos-chart-axis-label"
                  >
                    {val}
                  </text>
                </g>
              );
            })}

            {/* Average Daily Demand dashed benchmark line */}
            {avgY >= paddingTop && avgY <= paddingTop + innerHeight && (
              <g className="edos-chart-avg-line-group">
                <line
                  x1={paddingLeft}
                  y1={avgY}
                  x2={chartWidth - paddingRight}
                  y2={avgY}
                  stroke="var(--warning)"
                  strokeWidth="1.5"
                  strokeDasharray="4,4"
                />
                <text
                  x={chartWidth - paddingRight - 4}
                  y={avgY - 6}
                  textAnchor="end"
                  fill="var(--warning)"
                  fontSize="10"
                  fontFamily="var(--font-mono)"
                  fontWeight="600"
                >
                  Mean: {average_daily_demand.toFixed(1)} u/d
                </text>
              </g>
            )}

            {/* Bars */}
            {history.map((pt, idx) => {
              const barHeight = Math.max(2, (pt.quantity / maxQty) * innerHeight);
              const x = paddingLeft + idx * stepX + (stepX - barWidth) / 2;
              const y = paddingTop + innerHeight - barHeight;
              const isHovered = hoveredIndex === idx;

              // Format date label (e.g. "09/18" or "18")
              const dateParts = pt.date.split("-");
              const shortDate = dateParts.length === 3 ? `${dateParts[1]}/${dateParts[2]}` : pt.date;

              return (
                <g
                  key={pt.date}
                  className="edos-chart-bar-group"
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  tabIndex={0}
                  role="graphics-symbol"
                  aria-label={`${pt.date}: ${pt.quantity} units`}
                >
                  {/* Subtle bar background hit target */}
                  <rect
                    x={x - 2}
                    y={paddingTop}
                    width={barWidth + 4}
                    height={innerHeight}
                    fill="transparent"
                  />
                  {/* Active bar */}
                  <rect
                    x={x}
                    y={y}
                    width={barWidth}
                    height={barHeight}
                    rx="2"
                    fill={isHovered ? "var(--accent)" : "var(--accent-hover)"}
                    opacity={isHovered ? 1 : 0.85}
                    className="edos-chart-bar"
                  />
                  {/* Quantity label on top of bar */}
                  <text
                    x={x + barWidth / 2}
                    y={y - 4}
                    textAnchor="middle"
                    className="edos-chart-val-label"
                    fill={isHovered ? "var(--text-primary)" : "var(--text-muted)"}
                    fontSize={isHovered ? "11" : "9"}
                    fontWeight={isHovered ? "600" : "500"}
                  >
                    {pt.quantity}
                  </text>
                  {/* X-axis date label */}
                  {(idx % 2 === 0 || idx === history.length - 1) && (
                    <text
                      x={x + barWidth / 2}
                      y={paddingTop + innerHeight + 16}
                      textAnchor="middle"
                      className="edos-chart-axis-label"
                    >
                      {shortDate}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Active Hover Detail Tooltip */}
          {hoveredIndex !== null && history[hoveredIndex] && (
            <div className="edos-chart-tooltip" role="tooltip">
              <span className="edos-chart-tooltip__date">
                {history[hoveredIndex].date}
              </span>
              <span className="edos-chart-tooltip__val">
                <strong>{history[hoveredIndex].quantity} units</strong> demanded
              </span>
              <span className="edos-chart-tooltip__comp">
                {history[hoveredIndex].quantity >= average_daily_demand
                  ? `+${(history[hoveredIndex].quantity - average_daily_demand).toFixed(1)} vs mean`
                  : `${(history[hoveredIndex].quantity - average_daily_demand).toFixed(1)} vs mean`}
              </span>
            </div>
          )}
        </div>
      ) : (
        <div className="edos-demand-table-wrap">
          <DataTable
            columns={tableColumns}
            data={tableRows}
            density="compact"
          />
        </div>
      )}

      {/* Explicit Domain Boundary Notice */}
      <div className="edos-context-callout">
        <div className="edos-context-callout__icon" aria-hidden="true">
          ⓘ
        </div>
        <div className="edos-context-callout__body">
          <span className="edos-context-callout__title">Historical Observation Only</span>
          <p className="edos-context-callout__text">
            This graph strictly renders observed historical consumption points over the {window_days}-day window.
            EDOS Day 10 explicitly contains no forecasting algorithms, predictive ML, or stockout projections.
          </p>
        </div>
      </div>
    </Card>
  );
}
