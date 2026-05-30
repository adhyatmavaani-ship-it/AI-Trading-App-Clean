import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type BadgeTone = "green" | "blue" | "violet" | "amber" | "red" | "muted";

const tones: Record<BadgeTone, string> = {
  green: "border-primary/30 bg-primary/10 text-primary",
  blue: "border-secondary/30 bg-secondary/10 text-secondary",
  violet: "border-accent/35 bg-accent/15 text-violet-200",
  amber: "border-warning/35 bg-warning/10 text-warning",
  red: "border-danger/35 bg-danger/10 text-danger",
  muted: "border-white/10 bg-white/[0.06] text-muted",
};

export function Badge({
  tone = "muted",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
