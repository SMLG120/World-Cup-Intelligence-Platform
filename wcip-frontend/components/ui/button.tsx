import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  primary: "bg-pitch text-ink font-semibold hover:brightness-110 active:brightness-95",
  outline: "border border-line text-fg hover:border-pitch hover:text-pitch",
  ghost: "text-muted hover:text-fg hover:bg-elevated",
  danger: "border border-signal/40 text-signal hover:bg-signal/10",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-5 text-sm",
  lg: "h-12 px-7 text-base",
};

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      suppressHydrationWarning
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md uppercase tracking-wide transition-all",
        "disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none",
        "focus-visible:ring-2 focus-visible:ring-pitch/60",
        variants[variant], sizes[size], className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
