declare module "recharts" {
  import type { ComponentType, ReactNode } from "react";

  type ChartComponent = ComponentType<Record<string, unknown> & { children?: ReactNode }>;

  export const Area: ChartComponent;
  export const AreaChart: ChartComponent;
  export const Bar: ChartComponent;
  export const BarChart: ChartComponent;
  export const CartesianGrid: ChartComponent;
  export const Cell: ChartComponent;
  export const ErrorBar: ChartComponent;
  export const LabelList: ChartComponent;
  export const Legend: ChartComponent;
  export const PolarAngleAxis: ChartComponent;
  export const PolarGrid: ChartComponent;
  export const PolarRadiusAxis: ChartComponent;
  export const Radar: ChartComponent;
  export const RadarChart: ChartComponent;
  export const ReferenceLine: ChartComponent;
  export const ResponsiveContainer: ChartComponent;
  export const Tooltip: ChartComponent;
  export const XAxis: ChartComponent;
  export const YAxis: ChartComponent;
}
