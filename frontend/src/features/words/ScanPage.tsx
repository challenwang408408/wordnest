import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { EnrichResult, ScanCandidate } from "../../types";
import { ImagePlus } from "lucide-react";

type DraftItem = ScanCandidate & { selected: boolean };
type SavePhase = "enriching" | "saving" | null;

export function ScanPage() {
  const { profileId: raw } = useParams();
  const profileId = Number(raw);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [items, setItems] = useState<DraftItem[]>([]);
  const [libraryIds, setLibraryIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [savePhase, setSavePhase] = useState<SavePhase>(null);
  const [canSaveBasicOnly, setCanSaveBasicOnly] = useState(false);

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

  const scan = useMutation({
    mutationFn: (file: File) => api.scan(profileId, file),
    onSuccess: (data) => {
      setItems(
        data.candidates.map((c) => ({
          ...c,
          selected: true,
        })),
      );
      setError(null);
      setCanSaveBasicOnly(false);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "识别失败，请换一张更清晰的照片");
    },
  });

  async function saveSelected(saveBasicOnly = false) {
    const selected = items.filter((i) => i.selected && i.spelling.trim());
    if (selected.length === 0) {
      setError("请至少勾选一个单词");
      return;
    }
    setSavePhase(saveBasicOnly ? "saving" : "enriching");
    setError(null);
    setCanSaveBasicOnly(false);
    try {
      let enrichedItems: EnrichResult[] = [];
      if (!saveBasicOnly) {
        try {
          const enriched = await api.enrichBatch(
            profileId,
            selected.map((item) => item.spelling.trim()),
          );
          enrichedItems = enriched.items;
        } catch {
          const missing = selected.find((item) => !item.meaning_zh?.trim());
          if (missing) {
            throw new Error(
              `「${missing.spelling.trim()}」自动补全失败，请补上中文意思后再保存`,
            );
          }
          setCanSaveBasicOnly(true);
          throw new Error(
            "自动补全失败。可以重试补全，或明确确认只保存拼写和中文意思。",
          );
        }
      }

      const enrichedBySpelling = new Map(
        enrichedItems.map((item) => [item.spelling.trim().toLowerCase(), item]),
      );
      const payloads = selected.map((item): EnrichResult => {
        const spelling = item.spelling.trim();
        const enriched = enrichedBySpelling.get(spelling.toLowerCase());
        const meaningZh = item.meaning_zh?.trim() || enriched?.meaning_zh.trim() || "";
        if (!meaningZh) {
          throw new Error(`「${spelling}」还缺中文意思，请补上后再保存`);
        }
        return {
          spelling,
          meaning_zh: meaningZh,
          part_of_speech: enriched?.part_of_speech ?? "",
          ipa: enriched?.ipa ?? "",
          syllables: enriched?.syllables || spelling,
          example_en: enriched?.example_en ?? "",
          example_zh: enriched?.example_zh ?? "",
        };
      });

      setSavePhase("saving");
      await api.createWordsBatch(
        profileId,
        payloads.map((payload) => ({
          ...payload,
          library_ids: libraryIds,
        })),
      );
      await qc.invalidateQueries({ queryKey: ["dashboard", profileId] });
      await qc.invalidateQueries({ queryKey: ["words", profileId] });
      navigate(`/app/${profileId}/words`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSavePhase(null);
    }
  }

  const saving = savePhase !== null;

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">拍照找词</h1>
          <p className="page-sub">识别结果只是候选，确认后才会保存。</p>
        </div>
        <Link className="btn btn-ghost" to={`/app/${profileId}`}>
          返回
        </Link>
      </div>

      <ol className="workflow-steps" aria-label="拍照找词步骤">
        <li
          className={items.length > 0 ? "is-done" : "is-active"}
          aria-current={items.length === 0 ? "step" : undefined}
        >
          <span>1</span><strong>选择照片</strong>
        </li>
        <li
          className={items.length > 0 && !saving ? "is-active" : ""}
          aria-current={items.length > 0 && !saving ? "step" : undefined}
        >
          <span>2</span><strong>核对候选</strong>
        </li>
        <li
          className={saving ? "is-active" : ""}
          aria-current={saving ? "step" : undefined}
        >
          <span>3</span><strong>保存词库</strong>
        </li>
      </ol>

      <label className="surface scan-upload">
        <input
          className="visually-hidden"
          type="file"
          aria-label="选择书页照片"
          accept="image/*"
          capture="environment"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) scan.mutate(file);
          }}
        />
        <span className="scan-upload__icon" aria-hidden="true">
          <ImagePlus size={24} strokeWidth={1.8} />
        </span>
        <span className="scan-upload__copy">
          <strong>{scan.isPending ? "正在识别，请稍候…" : "选择一张书页照片"}</strong>
          <small>支持相机或相册，确认候选后才会保存</small>
        </span>
        <span className="btn btn-secondary" aria-hidden="true">
          选择照片
        </span>
      </label>

      {error ? (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          {canSaveBasicOnly ? (
            <div className="row wrap">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void saveSelected()}
              >
                重试自动补全
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => void saveSelected(true)}
              >
                只保存基础字段
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
      {libs.isError ? (
        <div className="error-banner" role="alert">
          <span>词库加载失败，暂时不能保存识别结果。</span>
          <button type="button" className="btn btn-ghost" onClick={() => void libs.refetch()}>
            重新加载词库
          </button>
        </div>
      ) : null}

      {items.length > 0 ? (
        <section className="surface stack" style={{ padding: 18 }}>
          <p className="page-sub" style={{ margin: 0 }}>
            勾选要保存的词，也可以改拼写和中文提示
          </p>
          {items.map((item, index) => (
            <div key={`${item.spelling}-${index}`} className="row wrap">
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  aria-label={`保存候选 ${index + 1}：${item.spelling || "未命名"}`}
                  checked={item.selected}
                  onChange={() =>
                    setItems((prev) =>
                      prev.map((x, i) =>
                        i === index ? { ...x, selected: !x.selected } : x,
                      ),
                    )
                  }
                />
              </label>
              <input
                className="grow"
                aria-label={`候选 ${index + 1} 英文拼写`}
                style={{ minHeight: 48, borderRadius: 12, border: "1px solid #c9d8dd", padding: "0 12px" }}
                value={item.spelling}
                onChange={(e) =>
                  setItems((prev) =>
                    prev.map((x, i) =>
                      i === index ? { ...x, spelling: e.target.value } : x,
                    ),
                  )
                }
              />
              <input
                className="grow"
                aria-label={`候选 ${index + 1} 中文意思`}
                placeholder="中文意思（补全失败时用）"
                style={{ minHeight: 48, borderRadius: 12, border: "1px solid #c9d8dd", padding: "0 12px" }}
                value={item.meaning_zh ?? ""}
                onChange={(e) =>
                  setItems((prev) =>
                    prev.map((x, i) =>
                      i === index ? { ...x, meaning_zh: e.target.value } : x,
                    ),
                  )
                }
              />
            </div>
          ))}

          <div className="stack" style={{ gap: 6 }}>
            <p className="muted" style={{ margin: 0 }}>
              保存到词库
            </p>
            {(libs.data ?? []).map((lib) => (
              <label key={lib.id} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={libraryIds.includes(lib.id)}
                  onChange={() =>
                    setLibraryIds((prev) =>
                      prev.includes(lib.id)
                        ? prev.filter((x) => x !== lib.id)
                        : [...prev, lib.id],
                    )
                  }
                />
                {lib.name}
              </label>
            ))}
          </div>

          <button
            type="button"
            className="btn btn-primary"
            disabled={saving || libraryIds.length === 0 || libs.isError}
            onClick={() => void saveSelected()}
          >
            {savePhase === "enriching"
              ? `正在统一补全 ${items.filter((item) => item.selected).length} 个词…`
              : savePhase === "saving"
                ? "正在写入词库…"
                : "确认并保存勾选的词"}
          </button>
        </section>
      ) : null}
    </div>
  );
}
