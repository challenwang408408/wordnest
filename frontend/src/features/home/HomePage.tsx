import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ProfileHeader } from "../../components/ProfileHeader";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  Camera,
  ChevronDown,
  PenLine,
  Sparkles,
  Target,
} from "lucide-react";

export function HomePage() {
  const { profileId: raw } = useParams();
  const profileId = Number(raw);
  const navigate = useNavigate();
  const [selectedLibs, setSelectedLibs] = useState<number[]>([]);
  // 高频错题与按词库二选一：选中时只练长期错得多的词
  const [frequentMistakes, setFrequentMistakes] = useState(false);
  const [showLibraryPicker, setShowLibraryPicker] = useState(false);
  const initializedProfileId = useRef<number | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard", profileId],
    queryFn: () => api.dashboard(profileId),
    enabled: Number.isFinite(profileId),
  });

  const availableLibraries = data?.libraries.filter((library) => library.word_count > 0) ?? [];
  const hasAvailableLibraries = availableLibraries.length > 0;
  const hasScope = frequentMistakes || selectedLibs.length > 0;
  const quizScope = frequentMistakes
    ? { frequent_mistakes: true }
    : { library_ids: selectedLibs };
  const preview = useQuery({
    queryKey: [
      "quiz-preview",
      profileId,
      frequentMistakes ? "frequent" : selectedLibs.join(","),
      data?.daily_quiz_count,
    ],
    queryFn: () => api.quizPreview(profileId, quizScope),
    enabled: Number.isFinite(profileId) && Boolean(data) && hasScope,
  });

  useEffect(() => {
    if (data?.libraries && initializedProfileId.current !== profileId) {
      setSelectedLibs(data.libraries.filter((library) => library.word_count > 0).map((library) => library.id));
      initializedProfileId.current = profileId;
    }
  }, [data?.libraries, profileId]);

  function toggleLib(id: number) {
    setFrequentMistakes(false);
    setSelectedLibs((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  function toggleFrequentMistakes() {
    // 关掉高频错题时回到全部可学词库，避免范围突然变空
    if (frequentMistakes && selectedLibs.length === 0) {
      setSelectedLibs(availableLibraries.map((library) => library.id));
    }
    setFrequentMistakes(!frequentMistakes);
  }

  const challengeCount = preview.data?.challenge_count;
  const estimatedMinutes = Math.max(1, Math.ceil((challengeCount ?? 0) * 0.45));
  const isPreparing = hasScope && preview.isLoading;
  const previewFailed = Boolean(preview.error);
  const mistakeThreshold = data?.frequent_mistake_threshold ?? 2;
  const frequentWordCount = data?.frequent_mistake_words ?? 0;
  const countLabel = previewFailed ? "题数待定" : `${challengeCount ?? "…"} 词`;
  const scopeSummary = !hasAvailableLibraries
    ? "暂无可学词库"
    : frequentMistakes
      ? `高频错题 · ${countLabel}`
    : selectedLibs.length === 0
      ? "还没选择挑战范围"
      : selectedLibs.length === availableLibraries.length
        ? `全部可学词库 · ${countLabel}`
        : `已选 ${selectedLibs.length} 个词库 · ${countLabel}`;

  return (
    <div className="stack">
      <ProfileHeader onSwitch={() => navigate("/select")} />
      {isLoading ? <p className="muted">正在加载首页…</p> : null}
      {error ? (
        <div className="error-banner" role="alert">
          <span>{error instanceof Error ? error.message : "首页加载失败"}</span>
          <button type="button" className="btn btn-ghost" onClick={() => void refetch()}>
            重试
          </button>
        </div>
      ) : null}

      {data ? (
        <>
          <section className="mission-card" aria-labelledby="daily-challenge-title">
        <div className="mission-card__topline">
          <span className="mission-badge">
            <Sparkles size={15} aria-hidden="true" /> 城市任务
          </span>
          <span>
            {previewFailed
              ? "需要重试"
              : !hasAvailableLibraries
                ? "等待新词"
              : !hasScope
                ? "未选范围"
              : isPreparing
              ? "正在准备"
              : (challengeCount ?? 0) > 0
                ? `约 ${estimatedMinutes} 分钟`
                : "等待新词"}
          </span>
        </div>
        <div className="mission-card__title">
          <div>
            <p className="eyebrow">今天只做这一件事</p>
            <h2 id="daily-challenge-title">今日挑战</h2>
            <p>
              {previewFailed
                ? "题数暂时没有准备好，学习内容不会丢失。"
                : !hasAvailableLibraries
                  ? "词库还是空的，请家长先放入几个新词。"
                : !hasScope
                  ? "还没有选择挑战范围，请先勾选至少一个词库。"
                : frequentMistakes && (challengeCount ?? 0) > 0
                  ? `专练 ${challengeCount} 个错过 ${mistakeThreshold} 次以上的词，把老对手一个个拿下。`
                : frequentMistakes
                  ? `目前没有错过 ${mistakeThreshold} 次以上的词，换回词库练习吧。`
                : (challengeCount ?? 0) > 0
                ? `${challengeCount} 个词，完成就为词芽浇了一次水。`
                : "词库还是空的，请家长先放入几个新词。"}
            </p>
          </div>
          <BookOpenCheck size={44} strokeWidth={1.6} aria-hidden="true" />
        </div>

        <div className="mission-stats" aria-label="今日学习概况">
          <div>
            <strong>{previewFailed ? "待定" : isPreparing ? "…" : challengeCount ?? 0}</strong>
            <span>本轮词数</span>
          </div>
          <div><strong>{data?.mastered_words ?? 0}</strong><span>已掌握</span></div>
          <div><strong>{data?.total_words ?? 0}</strong><span>词库总量</span></div>
        </div>

        <div className="scope-disclosure">
          <button
            type="button"
            className="scope-disclosure__toggle"
            aria-label={`调整挑战范围，当前${scopeSummary}`}
            aria-expanded={showLibraryPicker}
            aria-controls="challenge-library-picker"
            onClick={() => setShowLibraryPicker((shown) => !shown)}
          >
            <span className="scope-disclosure__copy">
              <small>挑战范围</small>
              <strong>{scopeSummary}</strong>
            </span>
            <span className="scope-disclosure__action" aria-hidden="true">
              调整
              <ChevronDown size={18} />
            </span>
          </button>
          {showLibraryPicker ? (
            <fieldset id="challenge-library-picker" className="library-picker">
              <legend className="visually-hidden">选择挑战词库</legend>
              <label
                className={`checkbox-row scope-frequent${frequentWordCount === 0 ? " is-disabled" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={frequentMistakes}
                  disabled={frequentWordCount === 0 && !frequentMistakes}
                  onChange={toggleFrequentMistakes}
                />
                <span className="grow scope-frequent__copy">
                  <span><Target size={15} aria-hidden="true" />高频错题</span>
                  <small>错过 {mistakeThreshold} 次以上，单独专练</small>
                </span>
                <span>{frequentWordCount} 词</span>
              </label>
              {(data?.libraries ?? []).map((lib) => (
                <label
                  key={lib.id}
                  className={`checkbox-row${lib.word_count === 0 ? " is-disabled" : ""}${frequentMistakes ? " is-inactive" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={!frequentMistakes && selectedLibs.includes(lib.id)}
                    disabled={lib.word_count === 0}
                    onChange={() => toggleLib(lib.id)}
                  />
                  <span className="grow">
                    {lib.name}
                    {lib.is_default ? "（默认）" : ""}
                  </span>
                  <span>{lib.word_count} 词</span>
                </label>
              ))}
            </fieldset>
          ) : null}
        </div>
        {preview.error ? (
          <div className="error-banner" role="alert">
            <span>题数准备失败，当前词库状态未改变。</span>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={preview.isFetching}
              onClick={() => void preview.refetch()}
            >
              {preview.isFetching ? "正在重试…" : "重新准备题目"}
            </button>
          </div>
        ) : null}
        <button
          type="button"
          className="btn btn-primary mission-start"
          disabled={
            isPreparing
            || previewFailed
            || !hasScope
            || challengeCount === 0
          }
          onClick={() =>
            navigate(`/app/${profileId}/quiz`, {
              state: frequentMistakes
                ? { frequentMistakes: true }
                : { libraryIds: selectedLibs },
            })
          }
        >
          {isPreparing
            ? "正在准备挑战…"
            : previewFailed
              ? "请先重试准备"
              : !hasAvailableLibraries
                ? "先请家长录入单词"
              : (challengeCount ?? 0) > 0
              ? frequentMistakes
                ? `开始 ${challengeCount} 个错题专练`
                : `开始 ${challengeCount} 词挑战`
              : !hasScope
                ? "请先选择挑战范围"
                : frequentMistakes
                  ? "暂时没有高频错题"
                  : "先请家长录入单词"}
          <ArrowRight size={18} aria-hidden="true" />
        </button>
          </section>

          <section className="parent-tools" aria-labelledby="parent-tools-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">给家长</p>
            <h2 id="parent-tools-title">家长工具</h2>
          </div>
          <span>补充今天遇到的新词</span>
        </div>
        <div className="dual-entry">
          <Link className="entry-card" to={`/app/${profileId}/add`}>
            <PenLine size={22} aria-hidden="true" />
            <strong>批量录词</strong>
            <span>一次录多个，补全后确认保存</span>
          </Link>
          <Link className="entry-card" to={`/app/${profileId}/scan`}>
            <Camera size={22} aria-hidden="true" />
            <strong>拍照找词</strong>
            <span>拍书页，勾选需要的词</span>
          </Link>
        </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
