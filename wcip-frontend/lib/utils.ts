import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function ordinal(n: number): string {
  const rounded = Math.round(n);
  const s = ["th", "st", "nd", "rd"];
  const v = rounded % 100;
  return rounded + (s[(v - 20) % 10] || s[v] || s[0]);
}

// A stable accent colour per chart series.
const PALETTE = [
  "hsl(75 95% 55%)",   // pitch lime
  "hsl(8 90% 64%)",    // coral
  "hsl(200 90% 62%)",  // sky
  "hsl(45 95% 58%)",   // amber
  "hsl(280 70% 68%)",  // violet
  "hsl(160 70% 50%)",  // teal
];
export function teamColor(index: number): string {
  return PALETTE[index % PALETTE.length];
}
