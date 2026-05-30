import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  title?: string;
  eyebrow?: string;
  action?: ReactNode;
};

export function Card({
  title,
  eyebrow,
  action,
  className,
  children,
  ...props
}: CardProps) {
  return (
    <section
      className={cn("glass-panel rounded-2xl p-5", className)}
      {...props}
    >
      {(title || eyebrow || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {eyebrow && (
              <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-secondary">
                {eyebrow}
              </p>
            )}
            {title && (
              <h3 className="mt-1 text-base font-semibold text-text">{title}</h3>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
