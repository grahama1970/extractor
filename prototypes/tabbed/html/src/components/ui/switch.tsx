import * as React from "react";
import * as SwitchPrimitives from "@radix-ui/react-switch";

import { cn } from "@/lib/utils";

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitives.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitives.Root
    className={cn(
      // Track
      "peer relative inline-flex h-7 w-[50px] shrink-0 cursor-pointer items-center rounded-full border "+
        "transition-colors duration-200 ease-out "+
        // Strong, stateful track + border
        "data-[state=checked]:bg-emerald-500 data-[state=checked]:border-emerald-600 "+
        "data-[state=unchecked]:bg-neutral-300 data-[state=unchecked]:border-neutral-300 "+
        "dark:data-[state=unchecked]:bg-neutral-700 dark:data-[state=unchecked]:border-neutral-600 "+
        // Accessible focus ring (neutral to avoid color clash)
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-neutral-500 focus-visible:ring-offset-background "+
        "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
    ref={ref}
  >
    <SwitchPrimitives.Thumb
      className={cn(
        // Thumb
        "pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 h-5 w-5 rounded-full bg-white "+
          "border border-neutral-300 dark:border-neutral-500 shadow will-change-transform "+
          "transition-transform duration-200 ease-out "+
          "data-[state=unchecked]:translate-x-[2px] data-[state=checked]:translate-x-[26px]",
      )}
    />
  </SwitchPrimitives.Root>
));
Switch.displayName = SwitchPrimitives.Root.displayName;

export { Switch };
