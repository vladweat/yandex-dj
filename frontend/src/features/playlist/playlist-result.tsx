"use client";

import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

export function PlaylistResult() {
  const result = usePlaylistStore((state) => state.result);
  if (!result) return null;

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>{result.title}</CardTitle>
        <CardDescription>{result.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button asChild>
          <a href={result.playlist_url} target="_blank" rel="noopener noreferrer">
            Открыть в Яндекс Музыке
            <ExternalLink />
          </a>
        </Button>

        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-950/60 text-slate-400">
              <tr>
                <th className="px-3 py-2 font-medium">Трек</th>
                <th className="px-3 py-2 font-medium">Исполнитель</th>
                <th className="px-3 py-2 font-medium">Длина</th>
                <th className="px-3 py-2 font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {result.tracks.map((track) => (
                <tr key={track.id} className="border-b border-slate-800/60 last:border-0">
                  <td className="px-3 py-2">{track.title}</td>
                  <td className="px-3 py-2 text-slate-400">{track.artist}</td>
                  <td className="px-3 py-2 text-slate-400">{formatDuration(track.duration_ms)}</td>
                  <td className="px-3 py-2 text-slate-400">{track.similarity_score.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
