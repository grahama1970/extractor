import * as React from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Minus, Plus, ZoomIn } from "lucide-react";

type Props = {
  value: number;                 // 0.5 .. 2.0
  onChange: (z: number) => void;
  onFitWidth?: () => void;
  onFitPage?: () => void;
  disabled?: boolean;
};

export function ZoomControl({ value, onChange, onFitWidth, onFitPage, disabled }: Props) {
  const set = (z: number) => onChange(Math.max(0.5, Math.min(2, Number(z.toFixed(2)))));
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button size="sm" variant="outline" disabled={disabled} aria-label="Zoom">
          <ZoomIn className="h-4 w-4 mr-2" />
          {Math.round(value * 100)}%
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[200px]">
        <div className="flex items-center justify-between mb-2">
          <Button size="icon" variant="outline" onClick={() => set(value - 0.1)} aria-label="Zoom out">
            <Minus className="h-4 w-4" />
          </Button>
          <div className="text-sm">Zoom</div>
          <Button size="icon" variant="outline" onClick={() => set(value + 0.1)} aria-label="Zoom in">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {/* Vertical slider via rotation – keeps dependencies minimal */}
        <div className="flex items-center justify-center py-2">
          <input
            aria-label="Zoom slider"
            type="range"
            min={0.5}
            max={2}
            step={0.1}
            value={value}
            onChange={(e) => set(Number(e.target.value))}
            className="h-40 w-4 [writing-mode:bt-lr] rotate-180"
          />
        </div>
        <div className="grid grid-cols-2 gap-2 mt-3">
          <Button size="sm" variant="outline" onClick={() => set(1)}>100%</Button>
          <Button size="sm" variant="outline" onClick={() => set(1.5)}>150%</Button>
          <Button size="sm" variant="outline" onClick={onFitWidth}>Fit Width</Button>
          <Button size="sm" variant="outline" onClick={onFitPage}>Fit Page</Button>
        </div>
        <div className="mt-3 text-xs text-muted-foreground">
          Shortcuts: <span className="bg-muted px-1 rounded">+</span>, <span className="bg-muted px-1 rounded">-</span>, <span className="bg-muted px-1 rounded">Ctrl/Cmd+0</span>
        </div>
      </PopoverContent>
    </Popover>
  );
}
