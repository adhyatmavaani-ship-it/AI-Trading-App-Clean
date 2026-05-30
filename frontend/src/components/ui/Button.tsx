import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  icon?: ReactNode;
};

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-black hover:bg-primary/90 shadow-[0_0_30px_rgba(0,230,118,0.22)]",
  secondary:
    "bg-white/[0.08] text-text ring-1 ring-white/[0.12] hover:bg-white/[0.12] hover:ring-secondary/35",
  ghost: "text-muted hover:bg-white/[0.08] hover:text-text",
  danger: "bg-danger/14 text-danger ring-1 ring-danger/30 hover:bg-danger/20",
};

export function Button({
  className,
  variant = "primary",
  icon,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-secondary/60 disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
