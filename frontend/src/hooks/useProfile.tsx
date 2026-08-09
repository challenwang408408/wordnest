import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Profile } from "../types";

const PROFILE_KEY = "wordnest.activeProfileId";

type ProfileContextValue = {
  profileId: number | null;
  setProfileId: (id: number) => void;
  clearProfile: () => void;
  profiles: Profile[];
  setProfiles: (profiles: Profile[]) => void;
  activeProfile: Profile | null;
};

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileIdState] = useState<number | null>(() => {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? Number(raw) : null;
  });
  const [profiles, setProfiles] = useState<Profile[]>([]);

  const setProfileId = useCallback((id: number) => {
    setProfileIdState(id);
    localStorage.setItem(PROFILE_KEY, String(id));
  }, []);

  const clearProfile = useCallback(() => {
    setProfileIdState(null);
    localStorage.removeItem(PROFILE_KEY);
  }, []);

  useEffect(() => {
    if (profileId != null && profiles.length > 0) {
      const exists = profiles.some((p) => p.id === profileId);
      if (!exists) clearProfile();
    }
  }, [profileId, profiles, clearProfile]);

  const activeProfile = useMemo(
    () => profiles.find((p) => p.id === profileId) ?? null,
    [profiles, profileId],
  );

  const value = useMemo(
    () => ({
      profileId,
      setProfileId,
      clearProfile,
      profiles,
      setProfiles,
      activeProfile,
    }),
    [profileId, setProfileId, clearProfile, profiles, activeProfile],
  );

  return (
    <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile 必须在 ProfileProvider 内使用");
  return ctx;
}
