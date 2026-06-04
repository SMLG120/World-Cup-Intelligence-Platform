import { cn } from "@/lib/utils";
import { HTMLAttributes } from "react";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-2 py-0.5 text-[0.65rem] uppercase",
        "tracking-wider border border-line text-muted",
        className,
      )}
      {...props}
    />
  );
}
