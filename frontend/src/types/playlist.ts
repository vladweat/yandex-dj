export type DiversityMode = "normal" | "high";
export type FeedbackValue = "like" | "dislike";
export type TrackEditAction = "remove" | "replace";

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
  use_library?: boolean;
  source_id?: string | null;
}

export interface PlaylistFeedbackRequest {
  value: FeedbackValue | null;
}

export interface PlaylistTrackEditRequest {
  track_id: string;
  action: TrackEditAction;
}

export interface PlaylistFeedbackResponse {
  id: string;
  feedback: FeedbackValue | null;
  feedback_at: string | null;
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

export interface PlaylistGenerationOptions {
  track_count: number;
  instrumental_only: boolean;
  exclude_artists: string[];
  diversity: DiversityMode;
  use_library: boolean;
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
  options?: PlaylistGenerationOptions | null;
  warnings?: string[];
  source_id?: string | null;
  latency_ms?: number | null;
  feedback?: FeedbackValue | null;
  has_cover?: boolean;
}

export interface PlaylistHistoryItem {
  id: string;
  prompt: string;
  title: string;
  playlist_url: string;
  pool_stats?: PlaylistPoolStats | null;
  options?: PlaylistGenerationOptions | null;
  created_at: string;
  source_id?: string | null;
  latency_ms?: number | null;
  feedback?: FeedbackValue | null;
}

export interface PlaylistHistoryResponse {
  items: PlaylistHistoryItem[];
  limit: number;
  offset: number;
}

export interface PlaylistQuotaResponse {
  limit: number;
  used: number;
  remaining: number;
  unlimited: boolean;
  resets_at: string;
}

export interface PlaylistFormDraft {
  prompt: string;
  trackCount: number;
  instrumentalOnly: boolean;
  excludeArtists: string;
  diversity: DiversityMode;
  useLibrary: boolean;
  sourceId: string | null;
}
