import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-11 w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2 text-base text-foreground outline-none transition-[border-color,box-shadow,background-color] placeholder:text-muted-foreground/70 focus:border-accent/50 focus:bg-white/[0.045] focus:shadow-[0_0_0_3px_rgba(255,204,0,0.12)] disabled:opacity-50 sm:h-10 sm:text-sm",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
