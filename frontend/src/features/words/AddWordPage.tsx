import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import type { EnrichResult } from "../../types";
import { ChevronDown, LoaderCircle, Mic, Square } from "lucide-react";
import { MAX_VOICE_SECONDS, useWordVoiceInput } from "../../hooks/useWordVoiceInput";

type DraftItem = EnrichResult & { selected: boolean; key: string };

const emptyFields = {
  meaning_zh: "",
  part_of_speech: "",
  ipa: "",
  syllables: "",
  example_en: "",
  example_zh: "",
};

/** 按换行 / 逗号 / 空白拆词，去空去重，最多 20 个。 */
export function parseSpellings(raw: string): string[] {
  const parts = raw
    .split(/[\n,，;；\t ]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of parts) {
    const key = part.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(part);
    if (out.length >= 20) break;
  }
  return out;
}

export function mergeVoiceWords(current: string, words: string[]): string {
  return parseSpellings([current, ...words].join(", ")).join(", ");
}

export function AddWordPage() {
  const { profileId: raw } = useParams();
  const profileId = Number(raw);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [input, setInput] = useState("");
  const [drafts, setDrafts] = useState<DraftItem[]>([]);
  const [libraryIds, setLibraryIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const appendVoiceWords = useCallback((words: string[]) => {
    setInput((current) => mergeVoiceWords(current, words));
  }, []);
  const voice = useWordVoiceInput({ profileId, onWords: appendVoiceWords });

  const libs = useQuery({
    queryKey: ["libraries", profileId],
    queryFn: () => api.libraries(profileId),
  });

  useEffect(() => {
    if (libs.data && libraryIds.length === 0) {
      const defaults = libs.data.filter((l) => l.is_default).map((l) => l.id);
      setLibraryIds(defaults.length ? defaults : libs.data.map((l) => l.id));
    }
  }, [libs.data, libraryIds.length]);

  const enrich = useMutation({
    mutationFn: (spellings: string[]) => api.enrichBatch(profileId, spellings),
    onSuccess: (data) => {
      const items: DraftItem[] = data.items.map((item, index) => ({
        ...item,
        selected: Boolean(item.meaning_zh.trim()),
        key: `${item.spelling.toLowerCase()}-${index}`,
      }));
      setDrafts(items);
      setExpandedKey(items[0]?.key ?? null);
      setError(null);
    },
    onError: (err) => {
      const spellings = parseSpellings(input);
      setError(err instanceof ApiError ? err.message : "补全失败，可以手工填写");
      setDrafts(
        spellings.map((spelling, index) => ({
          spelling,
          ...emptyFields,
          selected: true,
          key: `${spelling.toLowerCase()}-${index}`,
        })),
      );
      setExpandedKey(spellings[0] ? `${spellings[0].toLowerCase()}-0` : null);
    },
  });

  const save = useMutation({
    mutationFn: async () => {
      const selected = drafts.filter((d) => d.selected);
      if (selected.length === 0) throw new Error("请至少勾选一个词");
      if (libraryIds.length === 0) throw new Error("请选择词库");
      const missing = selected.find((d) => !d.meaning_zh.trim());
      if (missing) {
        throw new Error(`「${missing.spelling}」还缺中文意思，请补上或取消勾选`);
      }
      await api.createWordsBatch(
        profileId,
        selected.map((item) => ({
          spelling: item.spelling.trim(),
          meaning_zh: item.meaning_zh.trim(),
          part_of_speech: item.part_of_speech,
          ipa: item.ipa,
          syllables: item.syllables,
          example_en: item.example_en,
          example_zh: item.example_zh,
          library_ids: libraryIds,
        })),
      );
      return selected.length;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["dashboard", profileId] });
      await qc.invalidateQueries({ queryKey: ["words", profileId] });
      navigate(`/app/${profileId}/words`);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "保存失败");
    },
  });

  function onEnrich(e: FormEvent) {
    e.preventDefault();
    const spellings = parseSpellings(input);
    if (spellings.length === 0) {
      setError("请至少输入一个英语单词");
      return;
    }
    enrich.mutate(spellings);
  }

  function toggleLib(id: number) {
    setLibraryIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  function updateDraft(key: string, patch: Partial<EnrichResult> & { selected?: boolean }) {
    setDrafts((prev) =>
      prev.map((item) => (item.key === key ? { ...item, ...patch } : item)),
    );
  }

  const selectedCount = drafts.filter((d) => d.selected).length;

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">录单词</h1>
          <p className="page-sub">可一次输入多个词，统一补全后再保存。</p>
        </div>
        <Link className="btn btn-ghost" to={`/app/${profileId}`}>
          返回
        </Link>
      </div>

      <ol className="workflow-steps" aria-label="批量录词步骤">
        <li
          className={drafts.length > 0 ? "is-done" : "is-active"}
          aria-current={drafts.length === 0 ? "step" : undefined}
        >
          <span>1</span><strong>输入单词</strong>
        </li>
        <li
          className={drafts.length > 0 && !save.isPending ? "is-active" : ""}
          aria-current={drafts.length > 0 && !save.isPending ? "step" : undefined}
        >
          <span>2</span><strong>核对资料</strong>
        </li>
        <li
          className={save.isPending ? "is-active" : ""}
          aria-current={save.isPending ? "step" : undefined}
        >
          <span>3</span><strong>保存词库</strong>
        </li>
      </ol>

      <form className="surface stack" style={{ padding: 18 }} onSubmit={onEnrich}>
        <div className="field">
          <label htmlFor="spellings">英语单词</label>
          <textarea
            id="spellings"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={"一行一个，或用逗号/空格分隔\n例如：\nbeautiful\nhappy\napple"}
            rows={5}
            required
          />
        </div>
        <div className="voice-entry-row">
          <button
            type="button"
            className={`voice-record-button${voice.isRecording ? " is-recording" : ""}`}
            aria-label={voice.isRecording ? "停止录音" : "开始语音录词"}
            aria-pressed={voice.isRecording}
            onClick={voice.isRecording ? voice.stopRecording : voice.startRecording}
            disabled={!voice.isSupported || voice.isBusy || enrich.isPending}
          >
            {voice.phase === "requesting" || voice.phase === "transcribing" ? (
              <LoaderCircle className="spin" size={19} aria-hidden="true" />
            ) : voice.isRecording ? (
              <Square size={17} fill="currentColor" aria-hidden="true" />
            ) : (
              <Mic size={20} aria-hidden="true" />
            )}
            <span>
              {voice.phase === "requesting"
                ? "准备话筒"
                : voice.phase === "transcribing"
                  ? "识别中"
                  : voice.isRecording
                    ? `停止 ${String(Math.floor(voice.elapsedSeconds / 60)).padStart(2, "0")}:${String(voice.elapsedSeconds % 60).padStart(2, "0")}`
                    : "语音录词"}
            </span>
          </button>
          <div className="voice-entry-copy" aria-live="polite">
            <strong>
              {voice.isRecording
                ? `正在听英文单词，最长 ${MAX_VOICE_SECONDS} 秒`
                : "说完自动按逗号整理"}
            </strong>
            <span>{voice.message ?? "适合一次录入多个单词"}</span>
          </div>
        </div>
        {!voice.isSupported ? (
          <p className="voice-message" role="status">
            当前浏览器不支持录音，请继续键盘输入。
          </p>
        ) : null}
        {voice.error ? (
          <p className="voice-message is-error" role="alert">{voice.error}</p>
        ) : null}
        <p className="muted" style={{ margin: 0 }}>
          最多 20 个；重复拼写会自动去掉。
        </p>
        <button className="btn btn-primary" type="submit" disabled={enrich.isPending}>
          {enrich.isPending ? "正在统一补全…" : "统一补全"}
        </button>
      </form>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {libs.isError ? (
        <div className="error-banner" role="alert">
          <span>词库加载失败，暂时不能保存。</span>
          <button type="button" className="btn btn-ghost" onClick={() => void libs.refetch()}>
            重新加载词库
          </button>
        </div>
      ) : null}

      {drafts.length > 0 ? (
        <div className="stack">
          <section className="surface stack" style={{ padding: 18 }}>
            <p className="muted" style={{ margin: 0 }}>
              已补全 {drafts.length} 个，勾选 {selectedCount} 个
            </p>
            {drafts.map((draft) => {
              const open = expandedKey === draft.key;
              return (
                <div key={draft.key} className="stack draft-item" style={{ gap: 8 }}>
                  <div className="draft-summary-row">
                    <label className="draft-checkbox">
                      <input
                        type="checkbox"
                        aria-label={`保存 ${draft.spelling}`}
                        checked={draft.selected}
                      onChange={() =>
                        updateDraft(draft.key, { selected: !draft.selected })
                      }
                    />
                    </label>
                    <button
                      type="button"
                      className="draft-expand"
                      aria-expanded={open}
                      onClick={() =>
                        setExpandedKey((prev) =>
                          prev === draft.key ? null : draft.key,
                        )
                      }
                    >
                      <span><strong>{draft.spelling || "（空）"}</strong><small>{draft.meaning_zh || "待补意思"}</small></span>
                      <ChevronDown size={20} aria-hidden="true" />
                    </button>
                  </div>
                  {open ? (
                    <div className="stack" style={{ paddingLeft: 8 }}>
                      {(
                        [
                          ["spelling", "拼写"],
                          ["meaning_zh", "中文意思"],
                          ["part_of_speech", "词性"],
                          ["ipa", "音标"],
                          ["syllables", "音节（用 · 分隔）"],
                          ["example_en", "英文例句"],
                          ["example_zh", "中文例句"],
                        ] as const
                      ).map(([field, label]) => (
                        <div className="field" key={field}>
                          <label htmlFor={`${draft.key}-${field}`}>{label}</label>
                          <input
                            id={`${draft.key}-${field}`}
                            value={draft[field]}
                            onChange={(e) =>
                              updateDraft(draft.key, { [field]: e.target.value })
                            }
                          />
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </section>

          <section className="surface stack" style={{ padding: 18 }}>
            <p className="muted" style={{ margin: 0 }}>
              放到哪些词库（勾选的词共用）
            </p>
            {(libs.data ?? []).map((lib) => (
              <label key={lib.id} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={libraryIds.includes(lib.id)}
                  onChange={() => toggleLib(lib.id)}
                />
                {lib.name}
              </label>
            ))}
            <button
              type="button"
              className="btn btn-primary"
              disabled={save.isPending || selectedCount === 0 || libraryIds.length === 0}
              onClick={() => save.mutate()}
            >
              {save.isPending
                ? "正在保存…"
                : `保存勾选的 ${selectedCount} 个词`}
            </button>
          </section>
        </div>
      ) : null}
    </div>
  );
}
