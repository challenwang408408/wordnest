import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SyllableTrack } from "../components/SyllableTrack";
import { BottomNav } from "../components/BottomNav";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProfileProvider } from "../hooks/useProfile";
import { SelectProfilePage } from "../features/auth/SelectProfilePage";
import { QuizPage } from "../features/quiz/QuizPage";
import { AddWordPage } from "../features/words/AddWordPage";
import { ScanPage } from "../features/words/ScanPage";
import { MePage } from "../features/me/MePage";
import { voiceAvailabilityMessage } from "../hooks/useSpeech";
import App, { AppLayout, RequireAuth } from "../App";
import { LoginPage } from "../features/auth/LoginPage";
import { HomePage } from "../features/home/HomePage";
import { WordsPage } from "../features/words/WordsPage";

const enrichMock = vi.fn();
const enrichBatchMock = vi.fn();
const createWordMock = vi.fn();
const createWordsBatchMock = vi.fn();
const startQuizMock = vi.fn();
const rateQuizMock = vi.fn();
const librariesMock = vi.fn();
const profilesMock = vi.fn();
const scanMock = vi.fn();
const transcribeVoiceMock = vi.fn();
const loginMock = vi.fn();
const dashboardMock = vi.fn();
const quizPreviewMock = vi.fn();
const wordsMock = vi.fn();
const updateWordMock = vi.fn();
const deleteWordMock = vi.fn();
const deleteLibraryMock = vi.fn();
const sessionMock = vi.fn();
const logoutMock = vi.fn();

vi.mock("../api/client", () => ({
  AUTH_EXPIRED_EVENT: "wordnest:auth-expired",
  api: {
    profiles: (...args: unknown[]) => profilesMock(...args),
    libraries: (...args: unknown[]) => librariesMock(...args),
    enrich: (...args: unknown[]) => enrichMock(...args),
    enrichBatch: (...args: unknown[]) => enrichBatchMock(...args),
    createWord: (...args: unknown[]) => createWordMock(...args),
    createWordsBatch: (...args: unknown[]) => createWordsBatchMock(...args),
    startQuiz: (...args: unknown[]) => startQuizMock(...args),
    rateQuiz: (...args: unknown[]) => rateQuizMock(...args),
    scan: (...args: unknown[]) => scanMock(...args),
    transcribeVoice: (...args: unknown[]) => transcribeVoiceMock(...args),
    login: (...args: unknown[]) => loginMock(...args),
    dashboard: (...args: unknown[]) => dashboardMock(...args),
    quizPreview: (...args: unknown[]) => quizPreviewMock(...args),
    words: (...args: unknown[]) => wordsMock(...args),
    updateWord: (...args: unknown[]) => updateWordMock(...args),
    deleteWord: (...args: unknown[]) => deleteWordMock(...args),
    deleteLibrary: (...args: unknown[]) => deleteLibraryMock(...args),
    session: (...args: unknown[]) => sessionMock(...args),
    logout: (...args: unknown[]) => logoutMock(...args),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

const originalMediaDevicesDescriptor = Object.getOwnPropertyDescriptor(
  navigator,
  "mediaDevices",
);

afterEach(() => {
  if (originalMediaDevicesDescriptor) {
    Object.defineProperty(navigator, "mediaDevices", originalMediaDevicesDescriptor);
  } else {
    Reflect.deleteProperty(navigator, "mediaDevices");
  }
});

function wrap(
  ui: React.ReactNode,
  path = "/select",
  state?: Record<string, unknown>,
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={client}>
      <ProfileProvider>
        <MemoryRouter initialEntries={[state ? { pathname: path, state } : path]}>
          <Routes>
            <Route path="/select" element={ui} />
            <Route path="/app/:profileId" element={<div>home</div>} />
            <Route path="/app/:profileId/quiz" element={<QuizPage />} />
            <Route path="/app/:profileId/add" element={<AddWordPage />} />
            <Route path="/app/:profileId/scan" element={<ScanPage />} />
            <Route path="/app/:profileId/words" element={<div>words-list</div>} />
          </Routes>
        </MemoryRouter>
      </ProfileProvider>
    </QueryClientProvider>,
  );
  return { ...result, client };
}

function renderRoute(ui: React.ReactNode, path: string, routePath: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={client}>
      <ProfileProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={routePath} element={ui} />
            <Route path="/select" element={<div>profile-select</div>} />
            <Route path="/app/:profileId/quiz" element={<QuizRouteProbe />} />
          </Routes>
        </MemoryRouter>
      </ProfileProvider>
    </QueryClientProvider>,
  );
  return { ...result, client };
}

function QuizRouteProbe() {
  const location = useLocation();
  return (
    <>
      <div>quiz-route</div>
      <output aria-label="测试路由状态">{JSON.stringify(location.state)}</output>
    </>
  );
}

function renderApp(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
}

beforeEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  profilesMock.mockResolvedValue([
    { id: 1, slug: "brother", display_name: "哥哥" },
    { id: 2, slug: "sister", display_name: "妹妹" },
  ]);
  librariesMock.mockResolvedValue([
    {
      id: 10,
      profile_id: 1,
      name: "日常阅读",
      is_default: true,
      word_count: 0,
      due_count: 0,
    },
  ]);
  enrichMock.mockResolvedValue({
    spelling: "beautiful",
    meaning_zh: "美丽的",
    part_of_speech: "adj.",
    ipa: "/ˈbjuːtɪfl/",
    syllables: "beau·ti·ful",
    example_en: "What a beautiful day.",
    example_zh: "多美好的一天。",
  });
  enrichBatchMock.mockResolvedValue({
    items: [
      {
        spelling: "beautiful",
        meaning_zh: "美丽的",
        part_of_speech: "adj.",
        ipa: "/ˈbjuːtɪfl/",
        syllables: "beau·ti·ful",
        example_en: "What a beautiful day.",
        example_zh: "多美好的一天。",
      },
      {
        spelling: "happy",
        meaning_zh: "高兴的",
        part_of_speech: "adj.",
        ipa: "/ˈhæpi/",
        syllables: "hap·py",
        example_en: "I am happy.",
        example_zh: "我很高兴。",
      },
    ],
  });
  createWordMock.mockResolvedValue({
    id: 99,
    profile_id: 1,
    spelling: "beautiful",
    normalized_spelling: "beautiful",
    meaning_zh: "美丽的",
    part_of_speech: "adj.",
    ipa: "/ˈbjuːtɪfl/",
    syllables: "beau·ti·ful",
    example_en: "",
    example_zh: "",
    is_mastered: false,
    library_ids: [10],
    progress: null,
    created_at: "",
    updated_at: "",
  });
  createWordsBatchMock.mockResolvedValue({ items: [] });
  startQuizMock.mockResolvedValue({
    words: [
      {
        id: 11,
        spelling: "apple",
        meaning_zh: "苹果",
        ipa: "/ˈæpl/",
        syllables: "ap·ple",
        part_of_speech: "n.",
        example_en: "I eat an apple every morning.",
        example_zh: "我每天早上吃一个苹果。",
        options: ["小狗", "苹果", "学校", "桌子"],
      },
      {
        id: 12,
        spelling: "moon",
        meaning_zh: "月亮",
        ipa: "/muːn/",
        syllables: "moon",
        part_of_speech: "n.",
        example_en: "The moon is bright tonight.",
        example_zh: "今晚月亮很亮。",
        options: ["月亮", "水", "朋友", "红色的"],
      },
    ],
    total: 2,
  });
  rateQuizMock.mockResolvedValue({
    word_id: 11,
    familiarity: 2,
    correct_streak: 1,
    review_count: 1,
    next_review_at: null,
    is_mastered: false,
  });
  scanMock.mockResolvedValue({
    candidates: [{ spelling: "apple", meaning_zh: null }],
  });
  transcribeVoiceMock.mockResolvedValue({
    words: ["apple", "banana"],
    text: "apple, banana",
    request_id: "mock-voice-request",
  });
  loginMock.mockResolvedValue({ authenticated: true });
  dashboardMock.mockResolvedValue({
    profile: { id: 1, slug: "brother", display_name: "哥哥" },
    libraries: [
      {
        id: 10,
        profile_id: 1,
        name: "日常阅读",
        is_default: true,
        word_count: 4,
        due_count: 4,
      },
    ],
    total_words: 4,
    due_words: 4,
    mastered_words: 0,
    reviews_7d: 2,
    known_reviews_7d: 1,
    steady_accuracy_7d: 50,
    active_days_7d: 1,
    weak_words: [
      {
        id: 11,
        spelling: "home",
        meaning_zh: "家",
        review_count: 1,
        unknown_count: 1,
        last_rating: "unknown",
      },
    ],
  });
  quizPreviewMock.mockResolvedValue({ available_count: 4, challenge_count: 4 });
  wordsMock.mockResolvedValue([
    {
      id: 11,
      profile_id: 1,
      spelling: "home",
      normalized_spelling: "home",
      meaning_zh: "家",
      part_of_speech: "n.",
      ipa: "/hoʊm/",
      syllables: "home",
      example_en: "I am home.",
      example_zh: "我到家了。",
      is_mastered: false,
      library_ids: [10],
      progress: { familiarity: 1, review_count: 2 },
    },
  ]);
  updateWordMock.mockResolvedValue({});
  deleteWordMock.mockResolvedValue({ message: "已删除" });
  deleteLibraryMock.mockResolvedValue({ message: "已删除" });
  sessionMock.mockResolvedValue({ authenticated: true });
  logoutMock.mockResolvedValue({ message: "已退出" });
});

describe("LoginPage", () => {
  it("keeps a single brand lockup on the login screen", () => {
    renderRoute(<LoginPage />, "/login", "/login");

    expect(screen.getAllByText("WORDNEST")).toHaveLength(1);
  });

  it("only accepts four digits and announces a failed login", async () => {
    const user = userEvent.setup();
    loginMock.mockResolvedValueOnce({
      authenticated: false,
      message: "访问码不对，请再试一次",
    });
    renderRoute(<LoginPage />, "/login", "/login");

    const input = screen.getByLabelText("家庭访问码");
    await user.type(input, "12ab349");
    expect(input).toHaveValue("1234");
    expect(input).toHaveAttribute("maxLength", "4");
    await user.click(screen.getByRole("button", { name: /进入词芽/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("访问码不对");
  });
});

describe("HomePage", () => {
  it("makes the real-sized daily challenge the primary task", async () => {
    renderApp("/app/1");

    expect(await screen.findByRole("heading", { name: "今日挑战" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "切换孩子" })).toHaveAttribute(
      "aria-label",
      "切换孩子",
    );
    expect(
      await screen.findByRole("button", { name: "开始 4 词挑战" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "家长工具" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /批量录词/ })).toBeInTheDocument();
    await waitFor(() => {
      expect(quizPreviewMock).toHaveBeenCalledWith(1, [10], 10);
    });
  });

  it("keeps a preview failure distinct from a truly empty library", async () => {
    const user = userEvent.setup();
    quizPreviewMock
      .mockRejectedValueOnce(new Error("网络中断"))
      .mockResolvedValueOnce({ available_count: 4, challenge_count: 4 });
    renderRoute(<HomePage />, "/app/1", "/app/:profileId");

    expect(await screen.findByRole("alert")).toHaveTextContent("题数准备失败");
    expect(screen.queryByText("先请家长录入单词")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "请先重试准备" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "重新准备题目" }));
    expect(
      await screen.findByRole("button", { name: "开始 4 词挑战" }),
    ).toBeEnabled();
  });

  it("describes a cleared challenge range instead of calling the library empty", async () => {
    const user = userEvent.setup();
    renderRoute(<HomePage />, "/app/1", "/app/:profileId");

    await screen.findByRole("button", { name: "开始 4 词挑战" });
    await user.click(screen.getByRole("button", { name: /调整挑战范围/ }));
    await user.click(screen.getByRole("checkbox", { name: /日常阅读/ }));

    expect(screen.getByText(/还没有选择挑战范围/)).toBeInTheDocument();
    expect(screen.queryByText(/词库还是空的/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "请先选择挑战范围" })).toBeDisabled();
  });

  it("excludes empty libraries from the default challenge range", async () => {
    const user = userEvent.setup();
    dashboardMock.mockResolvedValueOnce({
      profile: { id: 1, slug: "brother", display_name: "哥哥" },
      libraries: [
        {
          id: 10,
          profile_id: 1,
          name: "绘本",
          is_default: false,
          word_count: 0,
          due_count: 0,
        },
        {
          id: 11,
          profile_id: 1,
          name: "日常阅读",
          is_default: true,
          word_count: 4,
          due_count: 4,
        },
      ],
      total_words: 4,
      due_words: 4,
      mastered_words: 0,
      reviews_7d: 0,
      known_reviews_7d: 0,
      steady_accuracy_7d: 0,
      active_days_7d: 0,
      weak_words: [],
    });

    renderRoute(<HomePage />, "/app/1", "/app/:profileId");

    const scopeToggle = await screen.findByRole("button", { name: /调整挑战范围/ });
    expect(scopeToggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("checkbox", { name: /绘本/ })).not.toBeInTheDocument();
    expect(await screen.findByText("全部可学词库 · 4 词")).toBeInTheDocument();

    await user.click(scopeToggle);
    expect(scopeToggle).toHaveAttribute("aria-expanded", "true");
    const emptyLibrary = screen.getByRole("checkbox", { name: /绘本/ });
    const activeLibrary = screen.getByRole("checkbox", { name: /日常阅读/ });
    expect(emptyLibrary).toBeDisabled();
    expect(emptyLibrary).not.toBeChecked();
    expect(activeLibrary).toBeChecked();
    await waitFor(() => {
      expect(quizPreviewMock).toHaveBeenCalledWith(1, [11], 10);
    });
  });

  it("keeps a manually cleared range after the dashboard refreshes", async () => {
    const user = userEvent.setup();
    const { client } = renderRoute(<HomePage />, "/app/1", "/app/:profileId");

    await screen.findByRole("button", { name: "开始 4 词挑战" });
    await user.click(screen.getByRole("button", { name: /调整挑战范围/ }));
    const library = screen.getByRole("checkbox", { name: /日常阅读/ });
    await user.click(library);
    expect(library).not.toBeChecked();

    await act(async () => {
      await client.invalidateQueries({ queryKey: ["dashboard", 1] });
    });

    await waitFor(() => expect(dashboardMock).toHaveBeenCalledTimes(2));
    expect(library).not.toBeChecked();
    expect(screen.getByRole("button", { name: "请先选择挑战范围" })).toBeDisabled();
  });
});

describe("RequireAuth", () => {
  it("shows a recoverable state for network failure instead of redirecting", async () => {
    const user = userEvent.setup();
    sessionMock
      .mockRejectedValueOnce(new Error("网络中断"))
      .mockResolvedValueOnce({ authenticated: true });
    renderRoute(
      <RequireAuth><div>受保护内容</div></RequireAuth>,
      "/secure",
      "/secure",
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("登录状态检查失败");
    expect(screen.queryByText("受保护内容")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重新检查" }));
    expect(await screen.findByText("受保护内容")).toBeInTheDocument();
  });

  it("returns an active family session to login when a protected request expires", async () => {
    localStorage.setItem("wordnest.activeProfileId", "1");
    const { client } = renderApp("/app/1");
    client.setQueryData(["private-draft"], { spelling: "home" });
    await screen.findByRole("heading", { name: "今日挑战" });

    await act(async () => {
      window.dispatchEvent(new Event("wordnest:auth-expired"));
    });

    expect(await screen.findByRole("heading", { name: "回到词芽" })).toBeInTheDocument();
    expect(client.getQueryData(["private-draft"])).toBeUndefined();
    expect(localStorage.getItem("wordnest.activeProfileId")).toBeNull();
  });
});

describe("MePage parent insights", () => {
  it("shows seven-day metrics and real weak words", async () => {
    renderRoute(<MePage />, "/app/1/me", "/app/:profileId/me");

    expect(await screen.findByText("50%")).toBeInTheDocument();
    const heading = screen.getByRole("heading", { name: "家长看板" });
    expect(heading).toBeInTheDocument();
    expect(
      within(heading.closest("header") as HTMLElement).getByRole("button", {
        name: "切换孩子，当前哥哥",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("home")).toBeInTheDocument();
    expect(screen.getByText("家")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /批量录词/ })).toHaveAttribute(
      "href",
      "/app/1/add",
    );
    expect(screen.getByRole("link", { name: /拍照找词/ })).toHaveAttribute(
      "href",
      "/app/1/scan",
    );
    expect(screen.getByRole("button", { name: "退出登录" })).toHaveClass("btn-ghost");
  });

  it("turns today's due-word advice into a direct review action", async () => {
    const user = userEvent.setup();
    renderRoute(<MePage />, "/app/1/me", "/app/:profileId/me");

    await user.click(await screen.findByRole("button", { name: "让哥哥开始复习" }));

    expect(await screen.findByText("quiz-route")).toBeInTheDocument();
    expect(screen.getByLabelText("测试路由状态")).toHaveTextContent(
      JSON.stringify({ libraryIds: [10] }),
    );
  });

  it("keeps a failed library deletion inside the dialog", async () => {
    const user = userEvent.setup();
    deleteLibraryMock.mockRejectedValueOnce(new Error("词库暂时删不掉"));
    dashboardMock.mockResolvedValueOnce({
      profile: { id: 1, slug: "brother", display_name: "哥哥" },
      libraries: [
        {
          id: 10,
          profile_id: 1,
          name: "日常阅读",
          is_default: true,
          word_count: 4,
          due_count: 4,
        },
        {
          id: 11,
          profile_id: 1,
          name: "绘本",
          is_default: false,
          word_count: 0,
          due_count: 0,
        },
      ],
      total_words: 4,
      due_words: 4,
      mastered_words: 0,
      reviews_7d: 2,
      known_reviews_7d: 1,
      steady_accuracy_7d: 50,
      active_days_7d: 1,
      weak_words: [],
    });
    renderRoute(<MePage />, "/app/1/me", "/app/:profileId/me");

    await user.click(await screen.findByRole("button", { name: "删除" }));
    const dialog = screen.getByRole("alertdialog", { name: "删除 绘本？" });
    await user.click(within(dialog).getByRole("button", { name: "确认删除" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("词库暂时删不掉");
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    expect(deleteLibraryMock).toHaveBeenCalledWith(1, 11, false);
  });

  it("does not turn a loading failure into a false learning recommendation", async () => {
    const user = userEvent.setup();
    dashboardMock
      .mockRejectedValueOnce(new Error("网络中断"))
      .mockResolvedValueOnce({
        profile: { id: 1, slug: "brother", display_name: "哥哥" },
        libraries: [],
        total_words: 0,
        due_words: 0,
        mastered_words: 0,
        reviews_7d: 0,
        known_reviews_7d: 0,
        steady_accuracy_7d: 0,
        active_days_7d: 0,
        weak_words: [],
      });

    renderRoute(<MePage />, "/app/1/me", "/app/:profileId/me");

    expect(await screen.findByRole("alert")).toHaveTextContent("加载失败");
    expect(screen.queryByText("今天可以轻松一点")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重新加载" }));
    expect(await screen.findByText("今天可以轻松一点")).toBeInTheDocument();
  });
});

describe("WordsPage compact management", () => {
  it("makes the compact row expandable and keeps pronunciation one tap away", async () => {
    const user = userEvent.setup();
    renderRoute(<WordsPage />, "/app/1/words", "/app/:profileId/words");

    expect(await screen.findByText("home")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "录新词" })).toHaveAttribute(
      "aria-label",
      "录新词",
    );
    const details = screen.getByRole("button", { name: "查看 home 详情" });
    expect(details).toHaveAttribute("aria-expanded", "false");
    expect(details).toHaveClass("word-summary-toggle");
    expect(screen.getByRole("button", { name: "朗读 home" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "朗读单词" })).not.toBeInTheDocument();

    await user.click(details);
    expect(details).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "朗读单词" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "编辑 home" })).toBeInTheDocument();
  });

  it("uses an in-product confirmation before deleting a word", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", vi.fn(() => false));
    renderRoute(<WordsPage />, "/app/1/words", "/app/:profileId/words");

    await user.click(await screen.findByRole("button", { name: "查看 home 详情" }));
    await user.click(screen.getByRole("button", { name: "删除" }));

    const dialog = screen.getByRole("alertdialog", { name: "删除 home？" });
    const cancel = screen.getByRole("button", { name: "先不删" });
    const confirmDelete = screen.getByRole("button", { name: "确认删除" });
    expect(dialog).toBeInTheDocument();
    expect(cancel).toHaveFocus();
    await user.tab({ shift: true });
    expect(confirmDelete).toHaveFocus();
    await user.tab();
    expect(cancel).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(dialog).not.toBeInTheDocument();
    expect(deleteWordMock).not.toHaveBeenCalled();
  });

  it("keeps a failed deletion visible inside the dialog and restores page scrolling", async () => {
    const user = userEvent.setup();
    const previousOverflow = document.body.style.overflow;
    let scrollY = 240;
    const scrollYSpy = vi.spyOn(window, "scrollY", "get").mockImplementation(() => scrollY);
    const scrollToSpy = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    let rejectDelete: (reason: Error) => void = () => undefined;
    deleteWordMock.mockImplementationOnce(() => new Promise((_, reject) => {
      rejectDelete = reject;
    }));
    renderRoute(<WordsPage />, "/app/1/words", "/app/:profileId/words");

    await user.click(await screen.findByRole("button", { name: "查看 home 详情" }));
    const deleteTrigger = screen.getByRole("button", { name: "删除" });
    await user.click(deleteTrigger);
    const dialog = screen.getByRole("alertdialog", { name: "删除 home？" });
    expect(document.body.style.overflow).toBe("hidden");

    await user.click(within(dialog).getByRole("button", { name: "确认删除" }));
    document.body.tabIndex = -1;
    document.body.focus();
    expect(document.body).toHaveFocus();
    await act(async () => {
      rejectDelete(new Error("服务器正忙，请稍后重试"));
    });

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("服务器正忙");
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "先不删" })).toHaveFocus();
    scrollY = 315;
    await user.click(within(dialog).getByRole("button", { name: "先不删" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe(previousOverflow);
    expect(deleteTrigger).toHaveFocus();
    expect(scrollToSpy).toHaveBeenLastCalledWith({
      left: 0,
      top: 240,
      behavior: "auto",
    });
    scrollYSpy.mockRestore();
    scrollToSpy.mockRestore();
    document.body.removeAttribute("tabindex");
  });

  it("discards an unfinished edit when the parent opens another word", async () => {
    const user = userEvent.setup();
    wordsMock.mockResolvedValueOnce([
      {
        id: 11,
        profile_id: 1,
        spelling: "home",
        normalized_spelling: "home",
        meaning_zh: "家",
        part_of_speech: "n.",
        ipa: "/hoʊm/",
        syllables: "home",
        example_en: "I am home.",
        example_zh: "我到家了。",
        is_mastered: false,
        library_ids: [10],
        progress: { familiarity: 1, review_count: 2 },
      },
      {
        id: 12,
        profile_id: 1,
        spelling: "moon",
        normalized_spelling: "moon",
        meaning_zh: "月亮",
        part_of_speech: "n.",
        ipa: "/muːn/",
        syllables: "moon",
        example_en: "The moon is bright.",
        example_zh: "月亮很亮。",
        is_mastered: false,
        library_ids: [10],
        progress: { familiarity: 0, review_count: 0 },
      },
    ]);
    renderRoute(<WordsPage />, "/app/1/words", "/app/:profileId/words");

    await user.click(await screen.findByRole("button", { name: "查看 home 详情" }));
    await user.click(screen.getByRole("button", { name: "编辑 home" }));
    const meaning = screen.getByLabelText("中文意思");
    await user.clear(meaning);
    await user.type(meaning, "房子");

    await user.click(screen.getByRole("button", { name: "查看 moon 详情" }));
    await user.click(screen.getByRole("button", { name: "查看 home 详情" }));

    expect(screen.queryByLabelText("中文意思")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "编辑 home" }));
    expect(screen.getByLabelText("中文意思")).toHaveValue("家");
  });

  it("does not describe a request failure as an empty word library", async () => {
    wordsMock.mockRejectedValueOnce(new Error("网络中断"));
    renderRoute(<WordsPage />, "/app/1/words", "/app/:profileId/words");

    expect(await screen.findByRole("alert")).toHaveTextContent("加载失败");
    expect(screen.queryByText("还没有单词")).not.toBeInTheDocument();
  });
});

describe("SyllableTrack", () => {
  it("renders syllable chips", () => {
    render(
      <SyllableTrack syllables="beau·ti·ful" fallback="beautiful" playing={false} />,
    );
    expect(screen.getByLabelText("音节声轨")).toBeInTheDocument();
    expect(screen.getByText("beau")).toBeInTheDocument();
    expect(screen.getByText("ti")).toBeInTheDocument();
    expect(screen.getByText("ful")).toBeInTheDocument();
  });

  it("can use the whole syllable track as the pronunciation target", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(
      <SyllableTrack
        syllables="home"
        fallback="home"
        playing={false}
        onActivate={onActivate}
        ariaLabel="朗读 home 音节"
      />,
    );

    const track = screen.getByRole("button", { name: "朗读 home 音节" });
    expect(track).toHaveClass("is-single");
    await user.click(track);
    expect(onActivate).toHaveBeenCalledTimes(1);
  });
});

describe("SelectProfilePage", () => {
  it("shows brother and sister cards", async () => {
    wrap(<SelectProfilePage />);
    expect(await screen.findByText("哥哥")).toBeInTheDocument();
    expect(screen.getByText("妹妹")).toBeInTheDocument();
  });

  it("enters selected profile home", async () => {
    const user = userEvent.setup();
    wrap(<SelectProfilePage />);
    await user.click(await screen.findByRole("button", { name: /哥哥/ }));
    expect(await screen.findByText("home")).toBeInTheDocument();
  });
});

describe("BottomNav profile routing", () => {
  it("uses the route profile instead of a stale cached profile", () => {
    localStorage.setItem("wordnest.activeProfileId", "2");
    render(
      <ProfileProvider>
        <MemoryRouter initialEntries={["/app/1/words"]}>
          <Routes>
            <Route path="/app/:profileId/words" element={<BottomNav />} />
          </Routes>
        </MemoryRouter>
      </ProfileProvider>,
    );

    expect(screen.getByRole("link", { name: /首页/ })).toHaveAttribute(
      "href",
      "/app/1",
    );
    expect(screen.getByRole("link", { name: /词库/ })).toHaveAttribute(
      "href",
      "/app/1/words",
    );
  });

  it("loads the route profile details on a direct nested link", async () => {
    localStorage.setItem("wordnest.activeProfileId", "1");
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <ProfileProvider>
          <MemoryRouter initialEntries={["/app/2/me"]}>
            <Routes>
              <Route path="/app/:profileId" element={<AppLayout />}>
                <Route path="me" element={<MePage />} />
              </Route>
            </Routes>
          </MemoryRouter>
        </ProfileProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/当前：妹妹/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /首页/ })).toHaveAttribute(
      "href",
      "/app/2",
    );
  });

  it("places the main content before mobile navigation in keyboard order", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { container } = render(
      <QueryClientProvider client={client}>
        <ProfileProvider>
          <MemoryRouter initialEntries={["/app/1"]}>
            <Routes>
              <Route path="/app/:profileId" element={<AppLayout />}>
                <Route index element={<div>主内容</div>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </ProfileProvider>
      </QueryClientProvider>,
    );

    const main = container.querySelector("main");
    const nav = container.querySelector(".bottom-nav");
    expect(main).not.toBeNull();
    expect(nav).not.toBeNull();
    expect(
      Boolean(main!.compareDocumentPosition(nav!) & Node.DOCUMENT_POSITION_FOLLOWING),
    ).toBe(true);
  });
});

describe("AddWordPage", () => {
  it("enriches and saves take off as one phrase", async () => {
    const user = userEvent.setup();
    enrichBatchMock.mockResolvedValueOnce({
      items: [{
        spelling: "take off", meaning_zh: "起飞", part_of_speech: "phr. v.",
        ipa: "/teɪk ɔːf/", syllables: "take off",
        example_en: "The plane will take off.", example_zh: "飞机将要起飞。",
      }],
    });
    wrap(<AddWordPage />, "/app/1/add");
    await user.type(await screen.findByLabelText("英语单词"), "take off");
    await user.click(screen.getByRole("button", { name: "统一补全" }));
    expect(await screen.findByDisplayValue("起飞")).toBeInTheDocument();
    expect(enrichBatchMock).toHaveBeenCalledWith(1, ["take off"]);
    expect(screen.getAllByRole("checkbox", { name: /^保存 / })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: /保存勾选的 1 个词/ }));
    await waitFor(() => expect(createWordsBatchMock).toHaveBeenCalledWith(1, [
      expect.objectContaining({ spelling: "take off", meaning_zh: "起飞", library_ids: [10] }),
    ]));
    expect(await screen.findByText("words-list")).toBeInTheDocument();
  });

  it("keeps the whole phrase editable and saveable if enrichment fails", async () => {
    const user = userEvent.setup();
    enrichBatchMock.mockRejectedValueOnce(new Error("补全失败"));
    wrap(<AddWordPage />, "/app/1/add");
    await user.type(await screen.findByLabelText("英语单词"), "take off");
    await user.click(screen.getByRole("button", { name: "统一补全" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("补全失败");
    expect(screen.getByRole("checkbox", { name: "保存 take off" })).toBeChecked();
    expect(screen.getAllByRole("checkbox", { name: /^保存 / })).toHaveLength(1);
    await user.type(screen.getByLabelText("中文意思"), "起飞");
    await user.click(screen.getByRole("button", { name: /保存勾选的 1 个词/ }));
    await waitFor(() => expect(createWordsBatchMock).toHaveBeenCalledWith(1, [
      expect.objectContaining({ spelling: "take off", meaning_zh: "起飞" }),
    ]));
  });

  it("batch enriches then saves selected words", async () => {
    const user = userEvent.setup();
    wrap(<AddWordPage />, "/app/1/add");
    await user.type(
      await screen.findByLabelText("英语单词"),
      "beautiful{Enter}happy",
    );
    await user.click(screen.getByRole("button", { name: "统一补全" }));
    expect(await screen.findByDisplayValue("美丽的")).toBeInTheDocument();
    await waitFor(() => {
      expect(enrichBatchMock).toHaveBeenCalledWith(1, ["beautiful", "happy"]);
    });
    await user.click(screen.getByRole("button", { name: /保存勾选的 2 个词/ }));
    await waitFor(() => {
      expect(createWordsBatchMock).toHaveBeenCalledTimes(1);
      expect(createWordsBatchMock).toHaveBeenCalledWith(1, [
        expect.objectContaining({
          spelling: "beautiful",
          meaning_zh: "美丽的",
          library_ids: [10],
        }),
        expect.objectContaining({
          spelling: "happy",
          meaning_zh: "高兴的",
          library_ids: [10],
        }),
      ]);
    });
    expect(await screen.findByText("words-list")).toBeInTheDocument();
  });

  it("records English words and merges comma-separated results into the input", async () => {
    let trackWasStopped = false;
    let startTimeslice: number | undefined;

    class MockMediaRecorder {
      static isTypeSupported() {
        return true;
      }

      state: "inactive" | "recording" = "inactive";
      mimeType: string;
      ondataavailable: ((event: BlobEvent) => void) | null = null;
      onstop: ((event: Event) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
        this.mimeType = options?.mimeType ?? "audio/webm";
      }

      start(timeslice?: number) {
        startTimeslice = timeslice;
        this.state = "recording";
      }

      stop() {
        this.state = "inactive";
        queueMicrotask(() => {
          this.ondataavailable?.({
            data: new Blob([trackWasStopped ? "" : "recorded-audio"], {
              type: this.mimeType,
            }),
          } as BlobEvent);
          this.onstop?.(new Event("stop"));
        });
      }
    }

    const stopTrack = vi.fn(() => {
      trackWasStopped = true;
    });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: stopTrack }],
        }),
      },
    });
    vi.stubGlobal("MediaRecorder", MockMediaRecorder);

    const user = userEvent.setup();
    wrap(<AddWordPage />, "/app/1/add");
    const input = await screen.findByLabelText("英语单词");
    await user.type(input, "beautiful");
    await user.click(screen.getByRole("button", { name: "开始语音录词" }));
    expect(await screen.findByRole("button", { name: "停止录音" })).toBeEnabled();
    expect(startTimeslice).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "停止录音" }));

    await waitFor(() => {
      expect(transcribeVoiceMock).toHaveBeenCalledWith(1, expect.any(Blob));
      expect(input).toHaveValue("beautiful, apple, banana");
      expect(stopTrack).toHaveBeenCalled();
    });
    expect(await screen.findByText("已识别 2 个单词，请核对后统一补全")).toBeInTheDocument();
  });

  it("shows an actionable message when microphone permission is denied", async () => {
    class MockMediaRecorder {
      static isTypeSupported() {
        return true;
      }
    }

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockRejectedValue({ name: "NotAllowedError" }),
      },
    });
    vi.stubGlobal("MediaRecorder", MockMediaRecorder);

    const user = userEvent.setup();
    wrap(<AddWordPage />, "/app/1/add");
    await user.click(await screen.findByRole("button", { name: "开始语音录词" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "请在浏览器设置中允许后重试",
    );
    expect(transcribeVoiceMock).not.toHaveBeenCalled();
  });
});

describe("ScanPage", () => {
  it("does not save a placeholder when enrichment fails", async () => {
    const user = userEvent.setup();
    enrichBatchMock.mockRejectedValueOnce(new Error("补全失败"));
    wrap(<ScanPage />, "/app/1/scan");

    const file = new File(["image"], "page.png", { type: "image/png" });
    await user.upload(await screen.findByLabelText("选择书页照片"), file);
    expect(await screen.findByLabelText("候选 1 英文拼写")).toHaveValue("apple");
    expect(screen.getByLabelText("保存候选 1：apple")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认并保存勾选的词" }));
    expect(await screen.findByText(/请补上中文意思/)).toBeInTheDocument();
    expect(createWordMock).not.toHaveBeenCalled();
    expect(createWordsBatchMock).not.toHaveBeenCalled();
  });

  it("batch enriches selected photo candidates before one atomic save", async () => {
    const user = userEvent.setup();
    scanMock.mockResolvedValueOnce({
      candidates: [
        { spelling: "apple", meaning_zh: null },
        { spelling: "home", meaning_zh: "家" },
      ],
    });
    enrichBatchMock.mockResolvedValueOnce({
      items: [
        {
          spelling: "apple",
          meaning_zh: "苹果",
          part_of_speech: "n.",
          ipa: "/ˈæpl/",
          syllables: "ap·ple",
          example_en: "I eat an apple.",
          example_zh: "我吃一个苹果。",
        },
        {
          spelling: "home",
          meaning_zh: "家",
          part_of_speech: "n.",
          ipa: "/hoʊm/",
          syllables: "home",
          example_en: "I am home.",
          example_zh: "我到家了。",
        },
      ],
    });
    wrap(<ScanPage />, "/app/1/scan");

    const file = new File(["image"], "page.png", { type: "image/png" });
    await user.upload(await screen.findByLabelText("选择书页照片"), file);
    await screen.findByLabelText("候选 2 英文拼写");
    await user.click(screen.getByRole("button", { name: "确认并保存勾选的词" }));

    await waitFor(() => {
      expect(enrichBatchMock).toHaveBeenCalledTimes(1);
      expect(enrichBatchMock).toHaveBeenCalledWith(1, ["apple", "home"]);
      expect(createWordsBatchMock).toHaveBeenCalledTimes(1);
    });
  });

  it("requires explicit confirmation before saving only basic fields", async () => {
    const user = userEvent.setup();
    scanMock.mockResolvedValueOnce({
      candidates: [{ spelling: "apple", meaning_zh: "苹果" }],
    });
    enrichBatchMock.mockRejectedValueOnce(new Error("补全失败"));
    wrap(<ScanPage />, "/app/1/scan");

    const file = new File(["image"], "page.png", { type: "image/png" });
    await user.upload(await screen.findByLabelText("选择书页照片"), file);
    await user.click(screen.getByRole("button", { name: "确认并保存勾选的词" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("自动补全失败");
    expect(createWordsBatchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "重试自动补全" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "只保存基础字段" }));
    await waitFor(() => {
      expect(createWordsBatchMock).toHaveBeenCalledTimes(1);
      expect(createWordsBatchMock).toHaveBeenCalledWith(1, [
        expect.objectContaining({
          spelling: "apple",
          meaning_zh: "苹果",
          ipa: "",
          example_en: "",
          library_ids: [10],
        }),
      ]);
    });
  });
});

describe("QuizPage", () => {
  it("gives options, feedback and an explicit next button", async () => {
    const user = userEvent.setup();
    const { client } = wrap(<QuizPage />, "/app/1/quiz");
    const invalidateQueries = vi.spyOn(client, "invalidateQueries");

    expect(await screen.findByText("apple")).toBeInTheDocument();
    const options = screen.getByRole("group", { name: "选择中文意思" });
    expect(options.querySelectorAll("button")).toHaveLength(4);
    // 没作答前不能泄题：例句和"下一个"都还不出现
    expect(
      screen.queryByText("I eat an apple every morning."),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "下一个" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "苹果" }));
    expect(screen.getByText(/答对了/)).toBeInTheDocument();
    expect(screen.getByText("I eat an apple every morning.")).toBeInTheDocument();
    expect(screen.getByText("我每天早上吃一个苹果。")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveFocus();
    });

    await user.click(screen.getByRole("button", { name: "下一个" }));
    await waitFor(() => {
      expect(rateQuizMock).toHaveBeenCalledWith(1, 11, "known");
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["dashboard", 1] });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["quiz-preview", 1] });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["words", 1] });
    });

    // 自动进入下一题，且选项恢复可点
    expect(await screen.findByRole("heading", { name: "moon" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "下一个" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "月亮" }));
    await user.click(screen.getByRole("button", { name: "看看结果" }));
    expect(await screen.findByText(/本轮 2 题，答对 2 题/)).toBeInTheDocument();
  });

  it("marks a wrong pick as unknown and shows the real meaning", async () => {
    const user = userEvent.setup();
    wrap(<QuizPage />, "/app/1/quiz");

    await user.click(await screen.findByRole("button", { name: "小狗" }));
    expect(screen.getByText(/它的意思是「苹果」/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下一个" }));
    await waitFor(() => {
      expect(rateQuizMock).toHaveBeenCalledWith(1, 11, "unknown");
    });
  });

  it("lets a lucky guess be downgraded to familiar", async () => {
    const user = userEvent.setup();
    wrap(<QuizPage />, "/app/1/quiz");

    await user.click(await screen.findByRole("button", { name: "苹果" }));
    await user.click(screen.getByRole("button", { name: /其实是蒙的/ }));
    await user.click(screen.getByRole("button", { name: "下一个" }));
    await waitFor(() => {
      expect(rateQuizMock).toHaveBeenCalledWith(1, 11, "familiar");
    });
  });

  it("protects an in-progress challenge from accidental exit", async () => {
    const user = userEvent.setup();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    wrap(<QuizPage />, "/app/1/quiz");

    await user.click(await screen.findByRole("button", { name: "苹果" }));
    await user.click(screen.getByRole("button", { name: "退出" }));
    expect(confirm).toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "apple" })).toBeInTheDocument();
  });

  it("starts a focused retry with only the words that need another look", async () => {
    const user = userEvent.setup();
    wrap(<QuizPage />, "/app/1/quiz");

    await user.click(await screen.findByRole("button", { name: "小狗" }));
    await user.click(screen.getByRole("button", { name: "下一个" }));
    await user.click(await screen.findByRole("button", { name: "月亮" }));
    await user.click(screen.getByRole("button", { name: "看看结果" }));
    await user.click(
      await screen.findByRole("button", { name: "只练需要再看 1 个" }),
    );

    await waitFor(() => {
      expect(startQuizMock).toHaveBeenLastCalledWith(1, [], 10, [11]);
    });
  });
});

describe("speech voice fallback", () => {
  it("returns visible hint when API missing or no English voice", () => {
    expect(voiceAvailabilityMessage(false, [])).toMatch(/暂时不能朗读/);
    expect(voiceAvailabilityMessage(true, [])).toMatch(/还没有可用的美式英语发音/);
    expect(
      voiceAvailabilityMessage(true, [{ lang: "en-US" }]),
    ).toBeNull();
  });
});
