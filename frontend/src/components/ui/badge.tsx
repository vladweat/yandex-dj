import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-accent/15 text-accent",
        secondary: "bg-white/[0.06] text-muted-foreground",
        success: "bg-emerald-500/15 text-emerald-300",
        warning: "bg-amber-500/15 text-amber-300",
        destructive: "bg-red-500/15 text-red-300",
        outline: "border border-white/10 text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
