import type { InputHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-text outline-none transition placeholder:text-muted focus:border-secondary/55 focus:ring-2 focus:ring-secondary/20",
        className,
      )}
      {...props}
    />
  );
}
