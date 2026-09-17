import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold tracking-wide transition-[color,background-color,border-color,box-shadow,transform] touch-manipulation disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-accent/50 active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-accent text-slate-950 shadow-[0_0_0_1px_rgba(255,204,0,0.2),0_8px_24px_-8px_rgba(255,204,0,0.55)] hover:bg-[#ffd633] hover:shadow-[0_0_0_1px_rgba(255,204,0,0.25),0_12px_28px_-8px_rgba(255,204,0,0.65)]",
        destructive: "bg-red-500/15 text-red-300 hover:bg-red-500/25",
        outline:
          "border border-white/10 bg-white/[0.02] text-foreground hover:border-white/20 hover:bg-white/[0.05]",
        secondary: "bg-white/[0.06] text-foreground hover:bg-white/[0.1]",
        ghost: "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-12 rounded-2xl px-6 text-[15px]",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}

export { Button, buttonVariants };
