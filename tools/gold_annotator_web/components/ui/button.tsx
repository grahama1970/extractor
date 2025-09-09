import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "secondary" | "outline" | "ghost";
type Size = "sm" | "md";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({ className, variant = "default", size = "md", ...props }: ButtonProps) {
  const base = "inline-flex items-center justify-center rounded-md text-sm font-medium disabled:opacity-50";
  const sizeCls = size === "sm" ? "px-2 py-1 text-xs" : "px-3 py-2";
  const variantCls: Record<Variant, string> = {
    default: "bg-black text-white shadow hover:bg-black/90",
    secondary: "bg-slate-800 text-slate-100 border border-slate-700 hover:bg-slate-700",
    outline: "bg-transparent text-slate-200 border border-slate-700 hover:bg-slate-800",
    ghost: "bg-transparent text-slate-200 hover:bg-slate-800",
  };
  return (
    <button className={cn(base, sizeCls, variantCls[variant], className)} {...props} />
  );
}
