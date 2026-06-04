import { cn } from "@/lib/utils";
import { InputHTMLAttributes } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  display: string;
}

export function Slider({ label, display, className, ...props }: Props) {
  return (
    <div>
      <div className="flex justify-between items-baseline mb-1">
        <span className="kicker">{label}</span>
        <span className="tnum text-xs text-pitch">{display}</span>
      </div>
      <input
        type="range"
        className={cn(
          "w-full h-1.5 appearance-none rounded-full bg-line cursor-pointer",
          "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-3.5",
          "[&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:rounded-full",
          "[&::-webkit-slider-thumb]:bg-pitch [&::-webkit-slider-thumb]:cursor-pointer",
          "[&::-webkit-slider-thumb]:shadow-[0_0_0_4px_hsl(var(--pitch)/0.2)]",
          className,
        )}
        {...props}
      />
    </div>
  );
}
