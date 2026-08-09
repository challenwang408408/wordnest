import { useMutation, useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { WordCard } from "../../components/WordCard";
import type { QuizWord, Rating } from "../../types";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  CircleX,
  Flame,
  RotateCcw,
  Trophy,
  X,
} from "lucide-react";

type LocationState = { libraryIds?: number[]; wordIds?: number[] };

export function QuizPage() {
  const { profileId: raw } = useParams();
  const profileId = Number(raw);
  const navigate = useNavigate();
  const location = useLocation();
  const libraryIds = (location.state as LocationState | null)?.libraryIds ?? [];
  const wordIds = (location.state as LocationState | null)?.wordIds ?? [];
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [rating, setRating] = useState<Rating | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [streak, setStreak] = useState(0);
  const [bestStreak, setBestStreak] = useState(0);
  const [mistakes, setMistakes] = useState<QuizWord[]>([]);
  const [done, setDone] = useState(false);
  const [words, setWords] = useState<QuizWord[]>([]);
  const titleRef = useRef<HTMLHeadingElement>(null);

  const start = useQuery({
    queryKey: ["quiz", profileId, libraryIds.join(","), wordIds.join(",")],
    queryFn: async () => {
      const result = await api.startQuiz(profileId, libraryIds, 10, wordIds);
      setWords(result.words);
      setIndex(0);
      setPicked(null);
      setRating(null);
      setCorrectCount(0);
      setStreak(0);
      setBestStreak(0);
      setMistakes([]);
      setDone(result.words.length === 0);
      return result;
    },
  });

  const current = words[index];
  const answered = picked !== null;
  const isCorrect = answered && picked === current?.meaning_zh;
  const isLast = index + 1 >= words.length;
  const progress = words.length
    ? Math.round(((index + (answered ? 1 : 0)) / words.length) * 100)
    : 0;
  const score = words.length ? Math.round((correctCount / words.length) * 100) : 0;
  const resultTitle = score >= 90
    ? "城市守护成功"
    : score >= 60
      ? "这轮长得不错"
      : "再浇一次水";

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    titleRef.current?.focus({ preventScroll: true });
  }, [index, done]);

  const submit = useMutation({
    mutationFn: ({ wordId, value }: { wordId: number; value: Rating }) =>
      api.rateQuiz(profileId, wordId, value),
    onSuccess: () => {
      if (isLast) {
        setDone(true);
      } else {
        setIndex((i) => i + 1);
      }
      setPicked(null);
      setRating(null);
    },
  });

  function pick(option: string) {
    if (answered || !current) return;
    setPicked(option);
    const right = option === current.meaning_zh;
    setRating(right ? "known" : "unknown");
    if (right) {
      setCorrectCount((c) => c + 1);
      const nextStreak = streak + 1;
      setStreak(nextStreak);
      setBestStreak((best) => Math.max(best, nextStreak));
    } else {
      setStreak(0);
      setMistakes((items) =>
        items.some((word) => word.id === current.id) ? items : [...items, current],
      );
    }
  }

  function goNext() {
    if (!current || rating === null) return;
    submit.mutate({ wordId: current.id, value: rating });
  }

  function exitChallenge() {
    const hasProgress = !done && (index > 0 || answered || correctCount > 0);
    if (
      hasProgress
      && !window.confirm("这轮挑战还没完成。已提交的题目会保留，当前题还没有记录，确定退出吗？")
    ) {
      return;
    }
    navigate(`/app/${profileId}`);
  }

  function markFamiliar() {
    if (!current) return;
    setRating("familiar");
    setMistakes((items) =>
      items.some((word) => word.id === current.id) ? items : [...items, current],
    );
  }

  function retryMistakes() {
    navigate(`/app/${profileId}/quiz`, {
      replace: true,
      state: { wordIds: mistakes.map((word) => word.id) },
    });
  }

  function optionClass(option: string) {
    if (!answered) return "quiz-option";
    if (option === current?.meaning_zh) return "quiz-option is-correct";
    if (option === picked) return "quiz-option is-wrong";
    return "quiz-option is-muted";
  }

  return (
    <div className="stack quiz-page">
      <header className="quiz-header">
        <div className="row quiz-header__topline">
          <div>
            <p className="eyebrow">今日挑战</p>
            <h1
              ref={titleRef}
              className="page-title"
              tabIndex={-1}
              aria-label={done
                ? "认读测试，本轮结束"
                : `认读测试，第 ${Math.min(index + 1, words.length || 1)} 题，共 ${words.length || 0} 题`}
            >
              认读测试
            </h1>
            <p className="page-sub" aria-live="polite" aria-atomic="true">
              {done
                ? "本轮结束"
                : `第 ${Math.min(index + 1, words.length || 1)} / ${words.length || 0} 题`}
            </p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={exitChallenge}>
            退出
          </button>
        </div>
        {!done && words.length > 0 ? (
          <div className="quiz-progress-wrap">
            <div
              className="quiz-progress"
              role="progressbar"
              aria-label="答题进度"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
            >
              <span style={{ width: `${progress}%` }} />
            </div>
            <div className="quiz-scoreline">
              <span><CheckCircle2 size={16} aria-hidden="true" />答对 {correctCount}</span>
              <span><Flame size={16} aria-hidden="true" />连续 {streak}</span>
            </div>
          </div>
        ) : null}
      </header>
      {start.isLoading ? <p className="muted">正在出题…</p> : null}
      {start.error ? (
        <div className="error-banner" role="alert">
          {start.error instanceof Error ? start.error.message : "出题失败"}
          <button type="button" className="btn btn-ghost" onClick={() => void start.refetch()}>
            重试
          </button>
        </div>
      ) : null}

      {done ? (
        <section className="surface result-card">
          {words.length === 0 ? (
            <div className="empty stack">
              <BookOpenEmpty />
              <h2>这个词库暂时没有可测的词</h2>
              <p>请返回首页换一个词库，或者请家长先录入新词。</p>
            </div>
          ) : (
            <>
              <div className="result-hero">
                <span className="result-trophy"><Trophy size={28} aria-hidden="true" /></span>
                <p className="eyebrow">挑战完成</p>
                <h2>{resultTitle}</h2>
                <p>本轮 {words.length} 题，答对 {correctCount} 题。</p>
                <strong className="result-score">{score}<small>分</small></strong>
              </div>
              <div className="result-stats" aria-label="本轮成绩">
                <div><strong>{correctCount}</strong><span>答对</span></div>
                <div><strong>{bestStreak}</strong><span>最长连对</span></div>
                <div><strong>{mistakes.length}</strong><span>需要再看</span></div>
              </div>
              {mistakes.length > 0 ? (
                <div className="mistake-review">
                  <h3>再看一眼</h3>
                  <p>这些词刚才选错了，或者还不太熟，再看一眼正确意思。</p>
                  <ul>
                    {mistakes.map((word) => (
                      <li key={word.id}><strong>{word.spelling}</strong><span>{word.meaning_zh}</span></li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="perfect-note"><CheckCircle2 size={18} aria-hidden="true" />这轮没有错词，状态很稳。</p>
              )}
            </>
          )}
          <div className="result-actions">
            {mistakes.length > 0 ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={retryMistakes}
              >
                <RotateCcw size={18} aria-hidden="true" />
                只练需要再看 {mistakes.length} 个
              </button>
            ) : null}
            {words.length > 0 ? (
              <button
                type="button"
                className={mistakes.length > 0 ? "btn btn-secondary" : "btn btn-primary"}
                disabled={start.isFetching}
                onClick={() => void start.refetch()}
              >
                <RotateCcw size={18} aria-hidden="true" />
                {start.isFetching ? "正在重新出题…" : "再练一轮"}
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(`/app/${profileId}`)}
            >
              回首页
            </button>
          </div>
        </section>
      ) : current ? (
        <section className="surface quiz-stage stack">
          <WordCard
            spelling={current.spelling}
            ipa={current.ipa}
            syllables={current.syllables}
            meaningZh={current.meaning_zh}
            showMeaning={answered}
            exampleEn={answered ? current.example_en : undefined}
            exampleZh={answered ? current.example_zh : undefined}
          />

          <p className="quiz-prompt">它是什么意思？选一个</p>
          <div className="quiz-options" role="group" aria-label="选择中文意思">
            {current.options.map((option) => (
              <button
                key={option}
                type="button"
                className={optionClass(option)}
                disabled={answered}
                onClick={() => pick(option)}
              >
                <span>{option}</span>
                {answered && option === current.meaning_zh ? (
                  <Check size={18} strokeWidth={3} aria-hidden="true" />
                ) : null}
                {answered && option === picked && option !== current.meaning_zh ? (
                  <X size={18} strokeWidth={3} aria-hidden="true" />
                ) : null}
              </button>
            ))}
          </div>

          {answered ? (
            <div className="stack quiz-answer-actions" style={{ gap: 10 }}>
              <div
                className={isCorrect ? "quiz-feedback is-ok" : "quiz-feedback is-no"}
                role="status"
                aria-live="polite"
              >
                {isCorrect ? <CheckCircle2 aria-hidden="true" /> : <CircleX aria-hidden="true" />}
                <div>
                  <strong>{isCorrect ? "答对了" : "没关系，记住它"}</strong>
                  <p className={isCorrect ? "quiz-verdict ok" : "quiz-verdict no"}>
                    {isCorrect
                      ? streak >= 2
                        ? `已经连续答对 ${streak} 个，继续保持。`
                        : "再读一遍这个词，然后继续。"
                      : `它的意思是「${current.meaning_zh}」。`}
                  </p>
                </div>
              </div>
              {isCorrect ? (
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={rating === "familiar"}
                  onClick={markFamiliar}
                >
                  {rating === "familiar" ? "已记为还不太熟" : "刚才是猜的，还不太熟"}
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-primary quiz-next"
                disabled={submit.isPending}
                onClick={goNext}
              >
                {submit.isPending ? "正在记录…" : isLast ? "看看结果" : "下一个"}
                {!submit.isPending ? <ArrowRight size={18} aria-hidden="true" /> : null}
              </button>
              {submit.error ? (
                <div className="error-banner" role="alert">
                  {submit.error instanceof Error
                    ? submit.error.message
                    : "记录失败，请再点一次"}
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function BookOpenEmpty() {
  return <span className="result-trophy"><CircleX size={28} aria-hidden="true" /></span>;
}
