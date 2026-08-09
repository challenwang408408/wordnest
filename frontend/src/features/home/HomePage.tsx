import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ProfileHeader } from "../../components/ProfileHeader";
import { useEffect, useState } from "react";
import { ArrowRight, BookOpenCheck, Camera, PenLine, Sparkles } from "lucide-react";

export function HomePage() {
  const { profileId: raw } = useParams();
  const profileId = Number(raw);
  const navigate = useNavigate();
  const [selectedLibs, setSelectedLibs] = useState<number[]>([]);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard", profileId],
    queryFn: () => api.dashboard(profileId),
    enabled: Number.isFinite(profileId),
  });

  const preview = useQuery({
    queryKey: ["quiz-preview", profileId, selectedLibs.join(",")],
    queryFn: () => api.quizPreview(profileId, selectedLibs, 10),
    enabled: Number.isFinite(profileId) && selectedLibs.length > 0,
  });

  useEffect(() => {
    if (data?.libraries) {
      setSelectedLibs(data.libraries.map((l) => l.id));
    }
  }, [data]);

  function toggleLib(id: number) {
    setSelectedLibs((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  const challengeCount = preview.data?.challenge_count;
  const estimatedMinutes = Math.max(1, Math.ceil((challengeCount ?? 0) * 0.45));
  const isPreparing = selectedLibs.length > 0 && preview.isLoading;
  const previewFailed = Boolean(preview.error);

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
              : selectedLibs.length === 0
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
                : selectedLibs.length === 0
                  ? "还没有选择挑战范围，请先勾选至少一个词库。"
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

        <fieldset className="library-picker">
          <legend>挑战范围</legend>
          {(data?.libraries ?? []).map((lib) => (
            <label key={lib.id} className="checkbox-row">
              <input
                type="checkbox"
                checked={selectedLibs.includes(lib.id)}
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
            || selectedLibs.length === 0
            || challengeCount === 0
          }
          onClick={() =>
            navigate(`/app/${profileId}/quiz`, {
              state: { libraryIds: selectedLibs },
            })
          }
        >
          {isPreparing
            ? "正在准备挑战…"
            : previewFailed
              ? "请先重试准备"
              : (challengeCount ?? 0) > 0
              ? `开始 ${challengeCount} 词挑战`
              : selectedLibs.length === 0
                ? "请先选择挑战范围"
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
