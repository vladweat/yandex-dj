"use client";

import * as React from "react";
import type { ReactNode } from "react";

import { FadeIn } from "@/components/ui/fade-in";
import { cn } from "@/lib/utils";

function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn(
        "flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.03] py-5 text-foreground backdrop-blur-sm sm:py-6",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("flex flex-col gap-1.5 px-4 sm:px-6", className)}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      data-slot="card-title"
      className={cn("font-display text-lg font-semibold leading-snug tracking-tight", className)}
      {...props}
    />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-sm leading-relaxed text-muted-foreground", className)}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card-content" className={cn("px-4 sm:px-6", className)} {...props} />
  );
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center px-4 sm:px-6", className)}
      {...props}
    />
  );
}

interface PanelProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

function Panel({ title, subtitle, children, className = "" }: PanelProps) {
  return (
    <FadeIn className={className}>
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {subtitle ? <CardDescription>{subtitle}</CardDescription> : null}
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </FadeIn>
  );
}

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle, Panel };
