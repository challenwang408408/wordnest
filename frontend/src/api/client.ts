import type {
  Dashboard,
  EnrichResult,
  Library,
  Profile,
  QuizPreview,
  QuizWord,
  Rating,
  ScanCandidate,
  SessionResponse,
  Word,
} from "../types";

const API = "/api/wordnest";

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
    params?: { q?: string; library_id?: number; status?: string },
  ) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.library_id != null) qs.set("library_id", String(params.library_id));
    if (params?.status) qs.set("status", params.status);
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
  startQuiz: (
    profileId: number,
    library_ids: number[],
    count = 10,
    word_ids: number[] = [],
  ) =>
    request<{ words: QuizWord[]; total: number }>(
      `/profiles/${profileId}/quiz/start`,
      {
        method: "POST",
        body: JSON.stringify({ library_ids, word_ids, count }),
      },
    ),
  quizPreview: (
    profileId: number,
    library_ids: number[],
    count = 10,
    word_ids: number[] = [],
  ) =>
    request<QuizPreview>(`/profiles/${profileId}/quiz/preview`, {
      method: "POST",
      body: JSON.stringify({ library_ids, word_ids, count }),
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
