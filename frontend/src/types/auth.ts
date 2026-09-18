export interface DeviceFlowStartResponse {
  device_code: string;
  user_code: string;
  verification_url: string;
  expires_in: number;
  interval: number;
}

export interface DeviceFlowPollRequest {
  device_code: string;
}

export interface DeviceFlowPollResponse {
  status: string;
  session_id?: string | null;
}

export interface AuthMeResponse {
  session_id: string;
  login: string;
  yandex_uid: number;
  expires_at: string;
  telegram_user_id?: number | null;
}
