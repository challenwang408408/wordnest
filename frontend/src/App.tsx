import { useQuery } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom";
import { api, ApiError } from "./api/client";
import { BottomNav } from "./components/BottomNav";
import { LoginPage } from "./features/auth/LoginPage";
import { SelectProfilePage } from "./features/auth/SelectProfilePage";
import { HomePage } from "./features/home/HomePage";
import { MePage } from "./features/me/MePage";
import { QuizPage } from "./features/quiz/QuizPage";
import { AddWordPage } from "./features/words/AddWordPage";
import { ScanPage } from "./features/words/ScanPage";
import { WordsPage } from "./features/words/WordsPage";
import { ProfileProvider, useProfile } from "./hooks/useProfile";

export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: api.session,
    retry: false,
  });

  if (session.isLoading) {
    return (
      <div className="app-shell">
        <p className="muted">正在确认登录状态…</p>
      </div>
    );
  }

  if (session.error instanceof ApiError && session.error.status === 401) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (session.error) {
    return (
      <div className="app-shell">
        <div className="error-banner" role="alert">
          <span>登录状态检查失败，请检查网络后重试。</span>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={session.isFetching}
            onClick={() => void session.refetch()}
          >
            {session.isFetching ? "正在重试…" : "重新检查"}
          </button>
        </div>
      </div>
    );
  }

  if (!session.data?.authenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}

export function AppLayout() {
  const { profileId: rawProfileId } = useParams();
  const profileId = Number(rawProfileId);
  const { setProfileId, setProfiles } = useProfile();
  const location = useLocation();
  const focusMode = location.pathname.endsWith("/quiz");
  const profiles = useQuery({
    queryKey: ["profiles"],
    queryFn: api.profiles,
  });

  useEffect(() => {
    if (Number.isFinite(profileId)) setProfileId(profileId);
  }, [profileId, setProfileId]);

  useEffect(() => {
    if (profiles.data) setProfiles(profiles.data);
  }, [profiles.data, setProfiles]);

  return (
    <div className={focusMode ? "app-shell is-focus-mode" : "app-shell"}>
      <div className="app-frame">
        <main className="app-main">
          <Outlet />
        </main>
        {!focusMode ? <BottomNav /> : null}
      </div>
    </div>
  );
}

function SiteReturnBar() {
  const location = useLocation();
  if (location.pathname.endsWith("/quiz")) return null;

  return (
    <nav className="site-return" aria-label="个人网站导航">
      <div className="site-return__inner">
        <a className="site-return__brand" href="/">
          Challen 王
        </a>
        <a className="site-return__link" href="/#projects">
          <ArrowLeft size={16} aria-hidden="true" />
          返回项目档案
        </a>
      </div>
    </nav>
  );
}

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [pathname]);

  return null;
}

export default function App() {
  return (
    <ProfileProvider>
      <ScrollToTop />
      <SiteReturnBar />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/select"
          element={
            <RequireAuth>
              <SelectProfilePage />
            </RequireAuth>
          }
        />
        <Route
          path="/app/:profileId"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<HomePage />} />
          <Route path="add" element={<AddWordPage />} />
          <Route path="scan" element={<ScanPage />} />
          <Route path="quiz" element={<QuizPage />} />
          <Route path="words" element={<WordsPage />} />
          <Route path="me" element={<MePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </ProfileProvider>
  );
}
