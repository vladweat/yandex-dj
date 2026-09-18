"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { fetchPlaylistCoverBlob } from "@/lib/api";
import { cn } from "@/lib/utils";

type PlaylistCoverProps = {
  generationId: string;
  hasCover: boolean;
  title: string;
  className?: string;
};

export function PlaylistCover({ generationId, hasCover, title, className }: PlaylistCoverProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!hasCover) {
      setObjectUrl(null);
      setFailed(false);
      return;
    }
    let revoked = false;
    let url: string | null = null;
    setFailed(false);
    void fetchPlaylistCoverBlob(generationId)
      .then((blob) => {
        if (revoked || !blob) {
          if (!revoked && !blob) setFailed(true);
          return;
        }
        url = URL.createObjectURL(blob);
        setObjectUrl(url);
      })
      .catch(() => {
        if (!revoked) setFailed(true);
      });
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [generationId, hasCover]);

  if (!hasCover || failed) return null;

  if (!objectUrl) {
    return (
      <Skeleton
        className={cn("aspect-square w-full max-w-[220px] rounded-2xl sm:max-w-[260px]", className)}
        aria-hidden
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- blob URL from authorized API
    <img
      src={objectUrl}
      alt={`AI-обложка: ${title}`}
      className={cn(
        "aspect-square w-full max-w-[220px] rounded-2xl border border-white/10 object-cover shadow-lg sm:max-w-[260px]",
        className,
      )}
    />
  );
}
