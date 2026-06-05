import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number;
  max?: number;
  className?: string;
  barClassName?: string;
  size?: "sm" | "md" | "lg";
}

const sizes = { sm: "h-1", md: "h-2", lg: "h-3" };

export function Progress({
  value,
  max = 100,
  className,
  barClassName,
  size = "md",
}: ProgressProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemax={max}
      className={cn("w-full bg-elevated rounded-full overflow-hidden", sizes[size], className)}
    >
      <div
        className={cn("h-full bg-pitch rounded-full transition-all duration-500", barClassName)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
