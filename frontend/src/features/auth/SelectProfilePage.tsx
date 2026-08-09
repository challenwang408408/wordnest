import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useProfile } from "../../hooks/useProfile";
import { useEffect } from "react";
import { ArrowRight, Sparkles, Zap } from "lucide-react";
import { BrandLockup } from "../../components/BrandLockup";

export function SelectProfilePage() {
  const navigate = useNavigate();
  const { setProfileId, setProfiles } = useProfile();
  const { data, isLoading, error } = useQuery({
    queryKey: ["profiles"],
    queryFn: api.profiles,
  });

  useEffect(() => {
    if (data) setProfiles(data);
  }, [data, setProfiles]);

  return (
    <main className="app-shell profile-select stack">
      <BrandLockup />
      <header className="select-heading">
        <p className="eyebrow">选择学习档案</p>
        <h1 className="page-title">今晚谁来出发？</h1>
        <p className="page-sub">每个孩子都有独立的词库和成长记录，进入后也能随时切换。</p>
      </header>
      {isLoading ? <p className="muted">正在加载…</p> : null}
      {error ? (
        <div className="error-banner">
          {error instanceof Error ? error.message : "加载失败"}
        </div>
      ) : null}
      <div className="profile-grid">
        {(data ?? []).map((profile) => (
          <button
            key={profile.id}
            type="button"
            className={`profile-card profile-card--${profile.slug}`}
            onClick={() => {
              setProfileId(profile.id);
              navigate(`/app/${profile.id}`, { replace: true });
            }}
          >
            <span className="profile-card__icon" aria-hidden="true">
              {profile.slug === "brother" ? <Zap /> : <Sparkles />}
            </span>
            <span className="profile-card__copy">
              <small>{profile.slug === "brother" ? "城市阅读队" : "星光启蒙队"}</small>
              <h2>{profile.display_name}</h2>
              <p>{profile.slug === "brother" ? "小学阅读 · 独立词库" : "幼儿园起步 · 独立词库"}</p>
            </span>
            <ArrowRight className="profile-card__arrow" size={22} aria-hidden="true" />
          </button>
        ))}
      </div>
    </main>
  );
}
