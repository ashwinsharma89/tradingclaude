"use client";

interface SignalBadgeProps {
  signal: string;
  size?: "sm" | "md";
}

export default function SignalBadge({ signal, size = "md" }: SignalBadgeProps) {
  const base = size === "sm" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1";

  if (signal === "overbought") {
    return (
      <span className={`${base} rounded font-medium bg-accent-red/20 text-accent-red`}>
        Overbought
      </span>
    );
  }

  if (signal === "oversold") {
    return (
      <span className={`${base} rounded font-medium bg-accent-green/20 text-accent-green`}>
        Oversold
      </span>
    );
  }

  return (
    <span className={`${base} rounded font-medium bg-text-muted/20 text-text-muted`}>
      Neutral
    </span>
  );
}
