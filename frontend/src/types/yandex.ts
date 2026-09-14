export interface YandexAccountSummary {
  uid?: number | null;
  login?: string | null;
  display_name?: string | null;
  full_name?: string | null;
  first_name?: string | null;
  second_name?: string | null;
  service_available?: boolean | null;
  region?: number | null;
  registered_at?: string | null;
  child?: boolean | null;
}

export interface YandexStatusResponse {
  account: YandexAccountSummary | null;
  default_email?: string | null;
  subscription?: Record<string, unknown> | null;
  plus?: Record<string, unknown> | null;
  permissions?: Record<string, unknown> | null;
  status: Record<string, unknown>;
}
