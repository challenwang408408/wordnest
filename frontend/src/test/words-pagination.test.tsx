import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { WordsPage } from "../features/words/WordsPage";
import type { Word } from "../types";

const wordsMock = vi.fn();
vi.mock("../api/client", () => ({ api: {
  libraries: async () => [],
  words: (...args: unknown[]) => wordsMock(...args),
} }));
vi.mock("../hooks/useSpeech", () => ({ useSpeech: () => ({ speak: vi.fn(), voiceHint: null }) }));

const entries: Word[] = Array.from({ length: 1587 }, (_, i) => ({
  id: i + 1, profile_id: 1, spelling: `word${i + 1}`, normalized_spelling: `word${i + 1}`,
  meaning_zh: `词条${i + 1}`, part_of_speech: "n.", ipa: "/wɝd/", syllables: "word",
  example_en: "Read this word.", example_zh: "读这个词。", is_mastered: false,
  library_ids: [3], progress: null, wrong_count: i === 1586 ? 5 : 0,
}));

describe("大词库分页", () => {
  it("限制同时渲染量，翻页可达所有词，搜索和错次排序覆盖完整词库", async () => {
    wordsMock.mockImplementation(async (_id: number, filters: { q?: string; sort?: string }) => {
      const filtered = entries.filter((word) => !filters.q || word.spelling === filters.q);
      return filters.sort === "wrong_count" ? [...filtered].reverse() : filtered;
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/app/1/words"]}>
      <Routes><Route path="/app/:profileId/words" element={<WordsPage />} /></Routes>
    </MemoryRouter></QueryClientProvider>);
    const user = userEvent.setup();
    expect(await screen.findByRole("button", { name: "查看 word1 详情" })).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(50);
    expect(screen.getByText("共 1587 个词条 · 第 1 / 32 页")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByRole("button", { name: "查看 word51 详情" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看 word1 详情" })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("搜索"), "word1587");
    expect(await screen.findByRole("button", { name: "查看 word1587 详情" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(1));
    await user.clear(screen.getByLabelText("搜索"));
    expect(await screen.findByText("共 1587 个词条 · 第 1 / 32 页")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看 word1 详情" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("单词排序"), "wrong_count");
    await waitFor(() => expect(screen.getAllByRole("article")[0]).toHaveTextContent("word1587"));
    expect(screen.getByText("共 1587 个词条 · 第 1 / 32 页")).toBeInTheDocument();
    client.clear();
  });
});
