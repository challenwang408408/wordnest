import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { api } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { WordCard } from "../../components/WordCard";
import { ChevronDown, Plus, Search, Volume2 } from "lucide-react";
import { useSpeech } from "../../hooks/useSpeech";

export function WordsPage() {
  const { profileId: raw } = useParams();
  const profileId = Number(raw);
  const qc = useQueryClient();
  const { speak, voiceHint } = useSpeech();
  const [q, setQ] = useState("");
  const [libraryId, setLibraryId] = useState<number | "">("");
  const [status, setStatus] = useState<string>("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editMeaning, setEditMeaning] = useState("");
  const [editIpa, setEditIpa] = useState("");
  const [editSyllables, setEditSyllables] = useState("");
  const [editExampleEn, setEditExampleEn] = useState("");
  const [editExampleZh, setEditExampleZh] = useState("");
  const [editLibraryIds, setEditLibraryIds] = useState<number[]>([]);
  const [enrichError, setEnrichError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; spelling: string } | null>(null);

  const libs = useQuery({
    queryKey: ["libraries", profileId],
    queryFn: () => api.libraries(profileId),
  });

  const words = useQuery({
    queryKey: ["words", profileId, q, libraryId, status],
    queryFn: () =>
      api.words(profileId, {
        q: q || undefined,
        library_id: libraryId === "" ? undefined : libraryId,
        status: status || undefined,
      }),
  });

  const update = useMutation({
    mutationFn: (payload: {
      wordId: number;
      body: {
        meaning_zh?: string;
        ipa?: string;
        syllables?: string;
        example_en?: string;
        example_zh?: string;
        is_mastered?: boolean;
        library_ids?: number[];
      };
    }) => api.updateWord(profileId, payload.wordId, payload.body),
    onSuccess: async () => {
      setActionError(null);
      setEditingId(null);
      await qc.invalidateQueries({ queryKey: ["words", profileId] });
      await qc.invalidateQueries({ queryKey: ["dashboard", profileId] });
      await qc.invalidateQueries({ queryKey: ["libraries", profileId] });
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : "修改失败，请重试");
    },
  });

  const fillExample = useMutation({
    mutationFn: (spelling: string) => api.enrich(profileId, spelling),
    onSuccess: (data) => {
      setEnrichError(null);
      if (data.example_en) setEditExampleEn(data.example_en);
      if (data.example_zh) setEditExampleZh(data.example_zh);
      if (data.ipa && !editIpa) setEditIpa(data.ipa);
      if (data.syllables && !editSyllables) setEditSyllables(data.syllables);
    },
    onError: (err) => {
      setEnrichError(err instanceof Error ? err.message : "补例句失败，可以手工填写");
    },
  });

  const remove = useMutation({
    mutationFn: (wordId: number) => api.deleteWord(profileId, wordId),
    onSuccess: async () => {
      setDeleteError(null);
      setExpandedId(null);
      await qc.invalidateQueries({ queryKey: ["words", profileId] });
      await qc.invalidateQueries({ queryKey: ["dashboard", profileId] });
    },
    onError: (err) => {
      setDeleteError(err instanceof Error ? err.message : "删除失败，请重试");
    },
  });

  function toggleEditLib(id: number) {
    setEditLibraryIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  return (
    <div className="stack">
      <div className="page-heading-actions">
        <div>
          <h1 className="page-title">词库</h1>
          <p className="page-sub">先快速找到词，需要时再展开管理。</p>
        </div>
        <Link
          className="btn btn-primary page-primary-action"
          to={`/app/${profileId}/add`}
          aria-label="录新词"
        >
          <Plus size={18} aria-hidden="true" />
          <span>录新词</span>
        </Link>
      </div>

      <section className="surface word-filters" aria-label="筛选单词">
        <div className="field word-search">
          <label htmlFor="q"><Search size={16} aria-hidden="true" />搜索</label>
          <input
            id="q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="拼写或中文"
          />
        </div>
        <div className="word-filter-grid">
          <label className="field" htmlFor="library-filter">
            <span>范围</span>
            <select
              id="library-filter"
              aria-label="按词库筛选"
              value={libraryId}
              onChange={(e) =>
                setLibraryId(e.target.value ? Number(e.target.value) : "")
              }
            >
              <option value="">全部词库</option>
              {(libs.data ?? []).map((lib) => (
                <option key={lib.id} value={lib.id}>
                  {lib.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field" htmlFor="status-filter">
            <span>进度</span>
            <select
              id="status-filter"
              aria-label="按学习状态筛选"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">全部状态</option>
              <option value="learning">学习中</option>
              <option value="mastered">已掌握</option>
            </select>
          </label>
        </div>
      </section>

      {words.isLoading ? <p className="muted">正在加载单词…</p> : null}
      {words.isError ? (
        <div className="error-banner" role="alert">
          <span>单词列表加载失败，请重试。</span>
          <button type="button" className="btn btn-ghost" onClick={() => void words.refetch()}>
            重新加载
          </button>
        </div>
      ) : null}
      {actionError ? <div className="error-banner" role="alert">{actionError}</div> : null}
      {voiceHint ? <div className="error-banner" role="status">{voiceHint}</div> : null}
      {(words.data ?? []).length === 0 && !words.isLoading && !words.isError ? (
        <div className="surface empty">
          {q || libraryId !== "" || status
            ? "没有符合当前筛选的单词，换个条件试试。"
            : "还没有单词，去首页录一个吧。"}
        </div>
      ) : null}

      <div className="word-list">
        {(words.data ?? []).map((word) => {
          const expanded = expandedId === word.id;
          const detailId = `word-details-${word.id}`;
          return (
            <article key={word.id} className="surface word-list-item">
              <div className="word-list-summary">
                <button
                  type="button"
                  className="word-summary-toggle"
                  aria-label={`${expanded ? "收起" : "查看"} ${word.spelling} 详情`}
                  aria-expanded={expanded}
                  aria-controls={detailId}
                  onClick={() => {
                    setExpandedId(expanded ? null : word.id);
                    setEditingId(null);
                    setEnrichError(null);
                  }}
                >
                  <span className="word-list-copy">
                    <strong className="word-list-title">{word.spelling}</strong>
                    <span className="word-list-meta">
                      <b>{word.meaning_zh}</b>{word.ipa ? ` · ${word.ipa}` : ""}
                    </span>
                  </span>
                  <span className={word.is_mastered ? "status-pill is-mastered" : "status-pill"}>
                    {word.is_mastered ? "已掌握" : "学习中"}
                  </span>
                  <span className="word-expand-icon" aria-hidden="true">
                    <ChevronDown size={20} />
                  </span>
                </button>
                <button
                  type="button"
                  className="word-list-speak"
                  aria-label={`朗读 ${word.spelling}`}
                  onClick={() => void speak(word.spelling)}
                >
                  <Volume2 size={19} aria-hidden="true" />
                </button>
              </div>

              {expanded ? (
                <div id={detailId} className="word-list-detail">
                  <WordCard
                    spelling={word.spelling}
                    ipa={word.ipa}
                    syllables={word.syllables}
                    meaningZh={word.meaning_zh}
                    exampleEn={word.example_en}
                    exampleZh={word.example_zh}
                  />
                  <p className="word-progress-copy">
                    熟悉度 {word.progress?.familiarity ?? 0} · 已练习 {word.progress?.review_count ?? 0} 次
                  </p>
                  <div className="word-management-actions">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      aria-label={`编辑 ${word.spelling}`}
                      onClick={() => {
                        setEditingId(word.id);
                        setEditMeaning(word.meaning_zh);
                        setEditIpa(word.ipa);
                        setEditSyllables(word.syllables);
                        setEditExampleEn(word.example_en);
                        setEditExampleZh(word.example_zh);
                        setEditLibraryIds([...word.library_ids]);
                        setEnrichError(null);
                        setActionError(null);
                      }}
                    >
                      编辑资料
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={update.isPending}
                      onClick={() => {
                        setActionError(null);
                        update.mutate({
                          wordId: word.id,
                          body: { is_mastered: !word.is_mastered },
                        });
                      }}
                    >
                      {word.is_mastered ? "恢复测试" : "标记已掌握"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      disabled={remove.isPending}
                      onClick={() => {
                        setDeleteError(null);
                        setDeleteTarget({ id: word.id, spelling: word.spelling });
                      }}
                    >
                      删除
                    </button>
                  </div>

                  {editingId === word.id ? (
                    <section className="stack word-edit-form" aria-label={`编辑 ${word.spelling}`}>
                      {(
                        [
                          ["meaning", "中文意思", editMeaning, setEditMeaning],
                          ["ipa", "音标", editIpa, setEditIpa],
                          ["syllables", "音节", editSyllables, setEditSyllables],
                          ["ex-en", "英文例句", editExampleEn, setEditExampleEn],
                          ["ex-zh", "中文例句", editExampleZh, setEditExampleZh],
                        ] as const
                      ).map(([key, label, value, setter]) => (
                        <div className="field" key={key}>
                          <label htmlFor={`${key}-${word.id}`}>{label}</label>
                          <input
                            id={`${key}-${word.id}`}
                            value={value}
                            onChange={(event) => setter(event.target.value)}
                          />
                        </div>
                      ))}
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={fillExample.isPending}
                        onClick={() => fillExample.mutate(word.spelling)}
                      >
                        {fillExample.isPending ? "正在补例句…" : "用 AI 补例句"}
                      </button>
                      {enrichError ? <div className="error-banner" role="alert">{enrichError}</div> : null}
                      <fieldset className="word-library-fieldset">
                        <legend>词库归属</legend>
                        {(libs.data ?? []).map((lib) => (
                          <label key={lib.id} className="checkbox-row">
                            <input
                              type="checkbox"
                              checked={editLibraryIds.includes(lib.id)}
                              onChange={() => toggleEditLib(lib.id)}
                            />
                            {lib.name}
                          </label>
                        ))}
                      </fieldset>
                      <div className="word-edit-actions">
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => setEditingId(null)}
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={editLibraryIds.length === 0 || update.isPending}
                          onClick={() => {
                            setActionError(null);
                            update.mutate({
                              wordId: word.id,
                              body: {
                                meaning_zh: editMeaning,
                                ipa: editIpa,
                                syllables: editSyllables,
                                example_en: editExampleEn,
                                example_zh: editExampleZh,
                                library_ids: editLibraryIds,
                              },
                            });
                          }}
                        >
                          {update.isPending ? "正在保存…" : "保存修改"}
                        </button>
                      </div>
                    </section>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={`删除 ${deleteTarget?.spelling ?? "这个单词"}？`}
        description="单词、学习进度和复习记录都会被删除，这一步无法恢复。"
        busy={remove.isPending}
        error={deleteError}
        onCancel={() => {
          setDeleteError(null);
          setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (!deleteTarget) return;
          setDeleteError(null);
          remove.mutate(deleteTarget.id, {
            onSuccess: () => setDeleteTarget(null),
          });
        }}
      />
    </div>
  );
}
