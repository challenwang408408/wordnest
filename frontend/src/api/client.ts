import type {
  Dashboard,
  EnrichResult,
  Library,
  Profile,
  QuizPreview,
  QuizScope,
  QuizWord,
  Rating,
  ScanCandidate,
  SessionResponse,
  Word,
  WordSort,
  VoiceTranscription,
} from "../types";

const API = "/api/wordnest";
export const AUTH_EXPIRED_EVENT = "wordnest:auth-expired";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = "请求失败，请稍后再试";
    try {
      const data = (await response.json()) as { detail?: string | { msg: string }[] };
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) {
        message = data.detail[0].msg;
      }
    } catch {
      // keep default
    }
    if (response.status === 401 && path !== "/auth/login") {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  login: (access_code: string) =>
    request<SessionResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ access_code }),
    }),
  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),
  session: () => request<SessionResponse>("/auth/session"),
  profiles: () => request<Profile[]>("/profiles"),
  dashboard: (profileId: number) =>
    request<Dashboard>(`/profiles/${profileId}/dashboard`),
  updateSettings: (profileId: number, daily_quiz_count: number) =>
    request<{ daily_quiz_count: number }>(`/profiles/${profileId}/settings`, {
      method: "PATCH",
      body: JSON.stringify({ daily_quiz_count }),
    }),
  libraries: (profileId: number) =>
    request<Library[]>(`/profiles/${profileId}/libraries`),
  createLibrary: (profileId: number, name: string) =>
    request<Library>(`/profiles/${profileId}/libraries`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  renameLibrary: (profileId: number, libraryId: number, name: string) =>
    request<Library>(`/profiles/${profileId}/libraries/${libraryId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteLibrary: (profileId: number, libraryId: number, force = false) =>
    request<{ message: string }>(
      `/profiles/${profileId}/libraries/${libraryId}?force=${force}`,
      { method: "DELETE" },
    ),
  words: (
    profileId: number,
    params?: { q?: string; library_id?: number; status?: string; sort?: WordSort },
  ) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.library_id != null) qs.set("library_id", String(params.library_id));
    if (params?.status) qs.set("status", params.status);
    if (params?.sort && params.sort !== "recent") qs.set("sort", params.sort);
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<Word[]>(`/profiles/${profileId}/words${suffix}`);
  },
  createWord: (
    profileId: number,
    body: EnrichResult & { library_ids: number[]; is_mastered?: boolean },
  ) =>
    request<Word>(`/profiles/${profileId}/words`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createWordsBatch: (
    profileId: number,
    items: Array<EnrichResult & { library_ids: number[]; is_mastered?: boolean }>,
  ) =>
    request<{ items: Word[] }>(`/profiles/${profileId}/words/batch`, {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  updateWord: (
    profileId: number,
    wordId: number,
    body: Partial<EnrichResult> & {
      library_ids?: number[];
      is_mastered?: boolean;
    },
  ) =>
    request<Word>(`/profiles/${profileId}/words/${wordId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteWord: (profileId: number, wordId: number) =>
    request<{ message: string }>(`/profiles/${profileId}/words/${wordId}`, {
      method: "DELETE",
    }),
  enrich: (profileId: number, spelling: string) =>
    request<EnrichResult>(`/profiles/${profileId}/words/enrich`, {
      method: "POST",
      body: JSON.stringify({ spelling }),
    }),
  enrichBatch: (profileId: number, spellings: string[]) =>
    request<{ items: EnrichResult[] }>(
      `/profiles/${profileId}/words/enrich-batch`,
      {
        method: "POST",
        body: JSON.stringify({ spellings }),
      },
    ),
  scan: async (profileId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ candidates: ScanCandidate[] }>(
      `/profiles/${profileId}/words/scan`,
      { method: "POST", body: form },
    );
  },
  transcribeVoice: async (profileId: number, audio: Blob) => {
    const bytes = await audio.arrayBuffer();
    if (bytes.byteLength === 0) {
      throw new ApiError(
        400,
        "录音没有生成有效音频，请用 Safari 打开后重试",
      );
    }
    const mime = audio.type.split(";", 1)[0] || "application/octet-stream";
    return request<VoiceTranscription>(
      `/profiles/${profileId}/words/transcribe-voice`,
      {
        method: "POST",
        body: bytes,
        headers: { "Content-Type": mime },
      },
    );
  },
  // 不传题量：后端按家长设置的每日题量出题，指定词重练时按词数出题
  startQuiz: (profileId: number, scope: QuizScope) =>
    request<{ words: QuizWord[]; total: number }>(
      `/profiles/${profileId}/quiz/start`,
      {
        method: "POST",
        body: JSON.stringify(scope),
      },
    ),
  quizPreview: (profileId: number, scope: QuizScope) =>
    request<QuizPreview>(`/profiles/${profileId}/quiz/preview`, {
      method: "POST",
      body: JSON.stringify(scope),
    }),
  rateQuiz: (profileId: number, wordId: number, rating: Rating) =>
    request<{
      word_id: number;
      familiarity: number;
      correct_streak: number;
      review_count: number;
      next_review_at: string | null;
      is_mastered: boolean;
    }>(`/profiles/${profileId}/quiz/${wordId}/rate`, {
      method: "POST",
      body: JSON.stringify({ rating }),
    }),
};
