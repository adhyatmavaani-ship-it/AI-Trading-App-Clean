import { cn } from "../../lib/cn";

export function Tabs<T extends string>({
  value,
  items,
  onChange,
}: {
  value: T;
  items: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div className="inline-flex rounded-xl border border-white/10 bg-white/[0.04] p-1">
      {items.map((item) => (
        <button
          key={item.value}
          onClick={() => onChange(item.value)}
          className={cn(
            "rounded-lg px-3 py-2 text-sm font-semibold text-muted transition",
            value === item.value && "bg-white/10 text-text shadow-sm",
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
