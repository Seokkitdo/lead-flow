export type User = {
  id: string;
  login_id: string;
  name: string;
  phone?: string;
  role: 'ADMIN' | 'USER';
  status: 'ACTIVE' | 'INACTIVE' | 'DEPARTED';
  version?: string;
  created_at: string;
};
export const statuses = {
  NEW: '신규',
  CONTACTING: '연락 진행 중',
  CALLBACK: '재통화 예정',
  IN_PROGRESS: '상담 진행 중',
  HOLD: '보류',
  REJECTED: '거절',
  COMPLETED: '상담 완료',
} as const;
export const sources = {
  NAVER: '네이버',
  KAKAO: '카카오',
  HOMEPAGE: '홈페이지',
  FORM: '폼',
  PHONE: '전화',
  REFERRAL: '소개',
  ETC: '기타',
} as const;
export const activities = {
  CALL_ATTEMPT: '전화 시도',
  CALL_NO_ANSWER: '전화 부재',
  CALL_CONNECTED: '전화 연결',
  KAKAO_SENT: '카카오톡 전달 기록',
  CONSULTATION: '상담 진행',
  MEMO: '메모 작성',
  STATUS_CHANGE: '상태 변경',
} as const;
export type LeadStatus = keyof typeof statuses;
export type Lead = {
  id: string;
  name: string;
  phone: string;
  source: keyof typeof sources | null;
  source_detail: string | null;
  initial_memo: string | null;
  current_status: LeadStatus;
  assignee_id: string | null;
  assignee_name: string | null;
  assigned_at: string | null;
  callback_at: string | null;
  acquired_at: string;
  created_at: string;
  updated_at: string;
  last_activity_at: string | null;
  latest_memo: string | null;
  assignment_pending: boolean;
  version: number;
  timeline?: Timeline[];
};
export type Timeline = {
  id: string;
  kind: 'ACTIVITY' | 'ASSIGNMENT';
  created_at: string;
  actor_name: string;
  activity_type?: keyof typeof activities;
  memo?: string;
  previous_status?: LeadStatus;
  new_status?: LeadStatus;
  assignee_name?: string;
  reason?: string;
};
export type LeadPage = { items: Lead[]; total: number; page: number; page_size: number };
export type Dashboard = {
  total: number;
  today_new: number;
  unassigned: number;
  in_progress: number;
  callback: number;
  completed: number;
  status_counts: Record<string, number>;
  staff: { id: string; name: string; total: number; completed: number; callback: number }[];
};
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(
      typeof detail === 'string'
        ? detail
        : status === 409
          ? '다른 변경 사항이 있습니다. 최신 내용을 확인해 주세요.'
          : status === 422
            ? '입력 내용을 확인해 주세요.'
            : status === 401
              ? '로그인이 필요합니다.'
              : '요청을 처리하지 못했습니다. 다시 시도해 주세요.',
    );
  }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      credentials: 'include',
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, '서버에 연결하지 못했습니다. 연결 상태를 확인하고 다시 시도해 주세요.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: '서버에 연결하지 못했습니다.' }));
    if (response.status === 401 && path !== '/auth/login' && path !== '/auth/me')
      window.dispatchEvent(new Event('leadflow:unauthorized'));
    throw new ApiError(response.status, body.detail);
  }
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}
export function body(method: string, data?: unknown): RequestInit {
  return { method, ...(data === undefined ? {} : { body: JSON.stringify(data) }) };
}
export function date(value?: string | null, withTime = false): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    month: '2-digit',
    day: '2-digit',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  }).format(new Date(value));
}
export function localInput(value?: string | null): string {
  if (!value) return '';
  const d = new Date(value);
  return new Date(d.getTime() + 9 * 60 * 60 * 1000).toISOString().slice(0, 16);
}
export function fromLocal(value: string): string | null {
  return value ? new Date(`${value}:00+09:00`).toISOString() : null;
}
