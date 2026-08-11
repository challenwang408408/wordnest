import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useProfile } from "../../hooks/useProfile";
import {
  Activity,
  AlertCircle,
  Camera,
  CalendarCheck2,
  CheckCircle2,
  Gauge,
  PenLine,
  RefreshCw,
} from "lucide-react";

export function MePage() {
  const { profileId: raw } = useParams();
  const profileId = Number(raw);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { clearProfile, activeProfile } = useProfile();
  const [newName, setNewName] = useState("");
  const [renameId, setRenameId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{
    id: number;
    name: string;
    wordCount: number;
  } | null>(null);

  const dashboard = useQuery({
    queryKey: ["dashboard", profileId],
    queryFn: () => api.dashboard(profileId),
  });

  const createLib = useMutation({
    mutationFn: (name: string) => api.createLibrary(profileId, name),
    onSuccess: async () => {
      setNewName("");
      await qc.invalidateQueries({ queryKey: ["libraries", profileId] });
      await qc.invalidateQueries({ queryKey: ["dashboard", profileId] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "创建失败"),
  });

  const renameLib = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      api.renameLibrary(profileId, id, name),
    onSuccess: async () => {
      setRenameId(null);
      await qc.invalidateQueries({ queryKey: ["libraries", profileId] });
      await qc.invalidateQueries({ queryKey: ["dashboard", profileId] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "重命名失败"),
  });

  const deleteLib = useMutation({
    mutationFn: ({ id, force }: { id: number; force: boolean }) =>
      api.deleteLibrary(profileId, id, force),
    onSuccess: async () => {
      setDeleteError(null);
      await qc.invalidateQueries({ queryKey: ["libraries", profileId] });
      await qc.invalidateQueries({ queryKey: ["dashboard", profileId] });
    },
    onError: (err) => setDeleteError(err instanceof Error ? err.message : "删除失败"),
  });

  function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setError(null);
    createLib.mutate(newName.trim());
  }

  async function onLogout() {
    await api.logout();
    clearProfile();
    navigate("/login", { replace: true });
  }

  const displayName = activeProfile?.display_name
    ?? dashboard.data?.profile.display_name
    ?? "孩子";

  const header = (
    <header className="parent-dashboard-header">
      <div className="parent-dashboard-header__copy">
        <p className="eyebrow">家长视角</p>
        <h1 className="page-title">家长看板</h1>
        <p className="page-sub">当前：{displayName} · 先看趋势，再决定要不要加练。</p>
      </div>
      <button
        type="button"
        className="btn btn-ghost parent-switch"
        aria-label={`切换孩子，当前${displayName}`}
        onClick={() => navigate("/select")}
      >
        <RefreshCw size={16} aria-hidden="true" />
        <span>切换孩子</span>
      </button>
    </header>
  );

  if (dashboard.isLoading) {
    return (
      <div className="stack">
        {header}
        <section className="surface parent-loading" role="status" aria-live="polite">
          <strong>正在整理学习记录</strong>
          <p>马上给出近 7 天趋势和今天的复习建议。</p>
        </section>
      </div>
    );
  }

  if (dashboard.isError || !dashboard.data) {
    return (
      <div className="stack">
        {header}
        <section className="surface parent-load-error" role="alert">
          <AlertCircle size={24} aria-hidden="true" />
          <div>
            <strong>学习记录加载失败</strong>
            <p>现在还不能判断今天是否需要复习，请重新加载。</p>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            disabled={dashboard.isFetching}
            onClick={() => void dashboard.refetch()}
          >
            {dashboard.isFetching ? "正在加载…" : "重新加载"}
          </button>
        </section>
      </div>
    );
  }

  const data = dashboard.data;
  const libraries = data.libraries;
  const weakWords = data.weak_words;
  const availableLibraryIds = libraries
    .filter((library) => library.word_count > 0)
    .map((library) => library.id);

  return (
    <div className="stack">
      {header}

      {error ? <div className="error-banner" role="alert">{error}</div> : null}

      <section className="parent-metrics" aria-label="近 7 天学习概况">
        <article className="parent-metric parent-metric--primary">
          <Activity size={20} aria-hidden="true" />
          <span>近 7 天答题</span>
          <strong>{data.reviews_7d}<small>次</small></strong>
        </article>
        <article className="parent-metric">
          <Gauge size={20} aria-hidden="true" />
          <span>稳答正确率</span>
          <strong>{data.steady_accuracy_7d}%</strong>
        </article>
        <article className="parent-metric">
          <CalendarCheck2 size={20} aria-hidden="true" />
          <span>活跃天数</span>
          <strong>{data.active_days_7d}<small>天</small></strong>
        </article>
      </section>

      <section className="surface parent-attention">
        <div>
          <p className="eyebrow">今天建议</p>
          <h2>{data.due_words > 0 ? "按计划复习就够了" : "今天可以轻松一点"}</h2>
          <p>
            {data.due_words > 0
              ? `还有 ${data.due_words} 个词到复习时间，不用额外加量。`
              : "当前没有到期词，让孩子自由读几分钟英文也很好。"}
          </p>
        </div>
        {data.due_words > 0 && availableLibraryIds.length > 0 ? (
          <button
            type="button"
            className="btn btn-primary parent-attention__action"
            onClick={() => navigate(`/app/${profileId}/quiz`, {
              state: { libraryIds: availableLibraryIds },
            })}
          >
            让{displayName}开始复习
          </button>
        ) : null}
      </section>

      <section className="surface parent-panel" aria-labelledby="weak-words-title">
        <div className="parent-panel__heading">
          <div>
            <p className="eyebrow">近 7 天</p>
            <h2 id="weak-words-title">需要多看一眼</h2>
          </div>
          {weakWords.length > 0 ? (
            <AlertCircle size={22} aria-hidden="true" />
          ) : (
            <CheckCircle2 className="is-positive" size={22} aria-hidden="true" />
          )}
        </div>
        {weakWords.length > 0 ? (
          <>
            <ul className="weak-word-list">
              {weakWords.map((word) => (
                <li key={word.id}>
                  <div><strong>{word.spelling}</strong><span>{word.meaning_zh}</span></div>
                  <small>答错 {word.unknown_count} / 练习 {word.review_count}</small>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="btn btn-secondary parent-weak-action"
              onClick={() => navigate(`/app/${profileId}/quiz`, {
                state: { wordIds: weakWords.map((word) => word.id) },
              })}
            >
              只练这 {weakWords.length} 个词
            </button>
          </>
        ) : (
          <p className="parent-empty">近 7 天没有明显薄弱词，保持现在的节奏。</p>
        )}
      </section>

      <section className="surface parent-panel parent-quick-tools" aria-labelledby="parent-tools-title">
        <div className="parent-panel__heading">
          <div>
            <p className="eyebrow">快速录入</p>
            <h2 id="parent-tools-title">家长工具</h2>
          </div>
          <span>少走一步</span>
        </div>
        <div className="dual-entry">
          <Link className="entry-card" to={`/app/${profileId}/add`}>
            <PenLine size={22} aria-hidden="true" />
            <strong>批量录词</strong>
            <span>输入或语音说出新词</span>
          </Link>
          <Link className="entry-card" to={`/app/${profileId}/scan`}>
            <Camera size={22} aria-hidden="true" />
            <strong>拍照找词</strong>
            <span>拍下书页后勾选保存</span>
          </Link>
        </div>
      </section>

      <section className="surface stack library-manager">
        <div className="parent-panel__heading">
          <div>
            <p className="eyebrow">内容管理</p>
            <h2>子词库</h2>
          </div>
          <span>{data.total_words} 个词</span>
        </div>
        {libraries.map((lib) => (
          <div key={lib.id} className="list-item">
            <div>
              <strong>
                {lib.name}
                {lib.is_default ? "（默认）" : ""}
              </strong>
              <p className="muted" style={{ margin: "4px 0 0" }}>
                {lib.word_count} 个词 · 待复习 {lib.due_count}
              </p>
              {renameId === lib.id ? (
                <div className="row" style={{ marginTop: 8 }}>
                  <input
                    aria-label={`将${lib.name}改名为`}
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    style={{ minHeight: 44, borderRadius: 10, padding: "0 10px" }}
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() =>
                      renameLib.mutate({ id: lib.id, name: renameValue.trim() })
                    }
                  >
                    保存
                  </button>
                </div>
              ) : null}
            </div>
            <div className="row wrap">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  setRenameId(lib.id);
                  setRenameValue(lib.name);
                }}
              >
                改名
              </button>
              {!lib.is_default ? (
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => {
                    setDeleteError(null);
                    setDeleteTarget({
                      id: lib.id,
                      name: lib.name,
                      wordCount: lib.word_count,
                    });
                  }}
                >
                  删除
                </button>
              ) : null}
            </div>
          </div>
        ))}

        <form className="row library-create" onSubmit={onCreate}>
          <label className="grow field">
            <span>新词库名称</span>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="例如：学校阅读"
            />
          </label>
          <button className="btn btn-primary" type="submit">
            新建
          </button>
        </form>
      </section>

      <button type="button" className="btn btn-ghost" onClick={() => void onLogout()}>
        退出登录
      </button>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={`删除 ${deleteTarget?.name ?? "这个词库"}？`}
        description={deleteTarget && deleteTarget.wordCount > 0
          ? `词库里还有 ${deleteTarget.wordCount} 个词。删除只会解除词库关联，不会删掉单词本身。`
          : "这是一个空词库，删除后无法恢复。"}
        busy={deleteLib.isPending}
        error={deleteError}
        onCancel={() => {
          setDeleteError(null);
          setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (!deleteTarget) return;
          setDeleteError(null);
          deleteLib.mutate(
            { id: deleteTarget.id, force: deleteTarget.wordCount > 0 },
            { onSuccess: () => setDeleteTarget(null) },
          );
        }}
      />
    </div>
  );
}
