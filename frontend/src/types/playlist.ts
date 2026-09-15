export type DiversityMode = "normal" | "high";

export interface MusicProfile {
  playlist_title: string;
  playlist_description: string;
  primary_genres: string[];
  mood_tags: string[];
  vocal_type: string;
  reference_artists: string[];
  search_queries: string[];
  target_track_count: number;
}

export interface PlaylistGenerateRequest {
  prompt: string;
  track_count?: number;
  instrumental_only?: boolean;
  exclude_artists?: string[];
  diversity?: DiversityMode;
  source_id?: string | null;
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
  id: string;
  prompt: string;
  title: string;
  description: string;
  playlist_url: string;
  tracks: PlaylistTrackResponse[];
  pool_stats?: PlaylistPoolStats | null;
  profile: MusicProfile;
}

export interface PlaylistHistoryItem {
  id: string;
  prompt: string;
  title: string;
  playlist_url: string;
  pool_stats?: PlaylistPoolStats | null;
  created_at: string;
}

export interface PlaylistHistoryResponse {
  items: PlaylistHistoryItem[];
  limit: number;
  offset: number;
}

export interface PlaylistFormDraft {
  prompt: string;
  trackCount: number;
  instrumentalOnly: boolean;
  excludeArtists: string;
  diversity: DiversityMode;
  sourceId: string | null;
}
