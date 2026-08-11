import { useProfile } from "../hooks/useProfile";
import { RefreshCw } from "lucide-react";

type Props = {
  onSwitch?: () => void;
};

export function ProfileHeader({ onSwitch }: Props) {
  const { activeProfile } = useProfile();
  if (!activeProfile) return null;
  return (
    <header className="profile-header">
      <div>
        <p className="eyebrow">今日任务</p>
        <h1 className="page-title">{activeProfile.display_name}的词芽</h1>
      </div>
      <button
        type="button"
        className="btn btn-ghost"
        aria-label="切换孩子"
        onClick={onSwitch}
      >
        <RefreshCw size={16} aria-hidden="true" />
        <span>切换孩子</span>
      </button>
    </header>
  );
}
