import type { ReactNode } from "react";

export type Column<T> = {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  align?: "left" | "right";
};

export function Table<T>({
  columns,
  rows,
  empty,
}: {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-white/10">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-muted">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={`px-4 py-3 font-semibold ${column.align === "right" ? "text-right" : "text-left"}`}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.08]">
          {rows.length === 0 ? (
            <tr>
              <td className="px-4 py-6 text-center text-muted" colSpan={columns.length}>
                {empty ?? "No rows yet."}
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr key={index} className="bg-transparent transition hover:bg-white/[0.03]">
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-4 py-3 ${column.align === "right" ? "text-right" : "text-left"}`}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
