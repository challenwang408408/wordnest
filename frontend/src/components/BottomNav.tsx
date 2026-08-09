import { NavLink, useParams } from "react-router-dom";
import { BookOpen, House, UserRound } from "lucide-react";

export function BottomNav() {
  const { profileId: rawProfileId } = useParams();
  const profileId = Number(rawProfileId);
  if (!Number.isFinite(profileId)) return null;
  const base = `/app/${profileId}`;
  return (
    <nav className="bottom-nav" aria-label="底部导航">
      <NavLink to={base} end>
        <House className="nav-ico" size={21} aria-hidden="true" />
        <span>首页</span>
      </NavLink>
      <NavLink to={`${base}/words`}>
        <BookOpen className="nav-ico" size={21} aria-hidden="true" />
        <span>词库</span>
      </NavLink>
      <NavLink to={`${base}/me`}>
        <UserRound className="nav-ico" size={21} aria-hidden="true" />
        <span>家长</span>
      </NavLink>
    </nav>
  );
}
