import { cn } from "@/lib/utils";
import { InputHTMLAttributes, forwardRef } from "react";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      suppressHydrationWarning
      className={cn(
        "h-10 w-full rounded-md border border-line bg-ink/60 px-3 text-sm text-fg",
        "placeholder:text-muted/60 focus:border-pitch focus:outline-none",
        "focus:ring-2 focus:ring-pitch/30 transition-colors",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("kicker block mb-1.5", className)} {...props} />;
}
