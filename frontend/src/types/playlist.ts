export interface PlaylistGenerateRequest {
  prompt: string;
  track_count?: number;
  instrumental_only?: boolean;
}

export interface PlaylistTrackResponse {
  id: string;
  title: string;
  artist: string;
  duration_ms: number;
  similarity_score: number;
}

export interface PlaylistPoolStats {
  raw: number;
  clean: number;
  selected: number;
}

export interface PlaylistGenerateResponse {
  title: string;
  description: string;
  playlist_url: string;
  tracks: PlaylistTrackResponse[];
  pool_stats?: PlaylistPoolStats | null;
}
