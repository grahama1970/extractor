/**
 * D3Table — large-format table for 5ft viewing distance.
 *
 * 18px body text, 20px bold headers, 16px padding, persona-tinted stripes.
 */
import React from "react";

type Props = {
  data: Record<string, unknown>[];
  accentHsl?: string;
  title?: string;
};

export default function D3Table({ data, accentHsl, title }: Props) {
  if (data.length === 0) {
    return <p className="text-lg text-muted-foreground p-8">No data to display</p>;
  }

  const columns = Object.keys(data[0]);
  const accent = accentHsl ? `hsl(${accentHsl})` : "hsl(var(--persona-accent))";

  return (
    <div className="w-full h-full overflow-auto p-6 animate-fade-in-5ft">
      {title && (
        <h2 className="text-2xl font-bold mb-4" style={{ color: accent }}>
          {title}
        </h2>
      )}
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                className="text-left font-bold border-b-2 whitespace-nowrap"
                style={{
                  fontSize: "20px",
                  padding: "16px",
                  borderColor: accent,
                  color: accent,
                }}
              >
                {col.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              style={{
                backgroundColor: i % 2 === 0 ? "transparent" : `color-mix(in srgb, ${accent} 6%, transparent)`,
              }}
            >
              {columns.map((col) => (
                <td
                  key={col}
                  className="border-b border-border/50"
                  style={{ fontSize: "18px", padding: "16px" }}
                >
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "number") {
    // Format percentages (0-1 range) and regular numbers
    if (value > 0 && value <= 1 && value !== Math.floor(value)) {
      return `${(value * 100).toFixed(1)}%`;
    }
    return value.toLocaleString();
  }
  return String(value);
}
