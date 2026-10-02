export type Profile = {
  id: number;
  slug: "brother" | "sister" | string;
  display_name: string;
};

export type Library = {
  id: number;
  profile_id: number;
  name: string;
  is_default: boolean;
  word_count: number;
  due_count: number;
};

export type WordProgress = {
  familiarity: number;
  correct_streak: number;
  review_count: number;
  last_rating: string | null;
  last_reviewed_at: string | null;
  next_review_at: string | null;
};

export type Word = {
  id: number;
  profile_id: number;
  spelling: string;
  normalized_spelling: string;
  meaning_zh: string;
  part_of_speech: string;
  ipa: string;
  syllables: string;
  example_en: string;
  example_zh: string;
  is_mastered: boolean;
  library_ids: number[];
  progress: WordProgress | null;
  /** 长期累计答错次数，不限时间窗口 */
  wrong_count: number;
};

export type WordSort = "recent" | "wrong_count";

export type EnrichResult = {
  spelling: string;
  meaning_zh: string;
  part_of_speech: string;
  ipa: string;
  syllables: string;
  example_en: string;
  example_zh: string;
};

export type ScanCandidate = {
  spelling: string;
  meaning_zh: string | null;
};

export type VoiceTranscription = {
  words: string[];
  text: string;
  request_id: string;
};

export type QuizWord = {
  id: number;
  spelling: string;
  meaning_zh: string;
  ipa: string;
  syllables: string;
  part_of_speech: string;
  example_en: string;
  example_zh: string;
  options: string[];
};

export type Rating = "unknown" | "familiar" | "known";

export const DAILY_QUIZ_COUNTS = [10, 20, 30, 40, 50] as const;

/** 出题范围：按词库、指定词重练，或长期高频错题 */
export type QuizScope = {
  library_ids?: number[];
  word_ids?: number[];
  frequent_mistakes?: boolean;
};

export type Dashboard = {
  profile: Profile;
  libraries: Library[];
  daily_quiz_count: number;
  frequent_mistake_threshold: number;
  frequent_mistake_words: number;
  total_words: number;
  due_words: number;
  mastered_words: number;
  reviews_7d: number;
  known_reviews_7d: number;
  steady_accuracy_7d: number;
  active_days_7d: number;
  weak_words: WeakWord[];
};

export type WeakWord = {
  id: number;
  spelling: string;
  meaning_zh: string;
  review_count: number;
  unknown_count: number;
  last_rating: string;
};

export type QuizPreview = {
  available_count: number;
  challenge_count: number;
};

export type SessionResponse = {
  authenticated: boolean;
  message?: string | null;
};
