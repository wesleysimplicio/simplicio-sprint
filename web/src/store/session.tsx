import AsyncStorage from "@react-native-async-storage/async-storage";
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Constants from "expo-constants";
import { ApiClient } from "../api/client";
import type {
  CurrentSprint,
  ProjectSetup,
  Provider,
  RepositoryRegistration,
} from "../api/types";

const STORAGE_KEY = "sendsprint.session.v1";

type AppUser = {
  email: string;
  active: boolean;
  displayName?: string | null;
  permissions?: {
    canRunAllBacklog: boolean;
  } | null;
};

type UserProfile = {
  provider?: Provider | null;
  account?: string | null;
  jiraBoardId?: string | null;
  adoTeamPath?: string | null;
  currentSprint?: CurrentSprint | null;
  projectSetup?: ProjectSetup | null;
};

type Session = {
  backendUrl: string;
  operatorToken?: string | null;
  appUser?: AppUser | null;
  provider: Provider | null;
  account: string | null;
  jiraBoardId?: string | null;
  adoTeamPath?: string | null;
  currentSprint?: CurrentSprint | null;
  projectSetup: ProjectSetup;
  userProfiles: Record<string, UserProfile>;
};

type Ctx = {
  session: Session;
  api: ApiClient;
  setBackendUrl: (url: string) => Promise<void>;
  setOperatorToken: (token: string | null) => Promise<void>;
  setAppUser: (user: AppUser | null) => Promise<void>;
  setProvider: (p: Provider | null) => Promise<void>;
  setAccount: (account: string | null) => Promise<void>;
  setJiraBoardId: (id: string | null) => Promise<void>;
  setAdoTeamPath: (path: string | null) => Promise<void>;
  setCurrentSprint: (sprint: CurrentSprint | null) => Promise<void>;
  setProjectSetup: (setup: ProjectSetup) => Promise<void>;
  reset: () => Promise<void>;
};

const defaultBackend =
  ((Constants.expoConfig?.extra as { defaultBackend?: string } | undefined) ?.defaultBackend) ??
  "http://localhost:8765";

const defaultProjectSetup: ProjectSetup = {
  mode: "single",
  branchPattern: "feature/{item_key}-{slug}",
  commitPattern: "{type}: {summary}",
  deployTargetBranch: "dev",
  repositories: [],
  updatedAt: null,
};

const initial: Session = {
  backendUrl: defaultBackend,
  operatorToken: null,
  appUser: null,
  provider: null,
  account: null,
  jiraBoardId: null,
  adoTeamPath: null,
  currentSprint: null,
  projectSetup: defaultProjectSetup,
  userProfiles: {},
};

const SessionContext = createContext<Ctx | null>(null);

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [session, setSession] = useState<Session>(initial);
  const [hydrated, setHydrated] = useState(false);
  const sessionRef = useRef<Session>(initial);

  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const next = normalizeSession(JSON.parse(raw) as Partial<Session>);
          sessionRef.current = next;
          setSession(next);
        }
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  const persist = async (nextOrUpdater: Session | ((current: Session) => Session)) => {
    const nextRaw =
      typeof nextOrUpdater === "function"
        ? nextOrUpdater(sessionRef.current)
        : nextOrUpdater;
    const next = normalizeSession(nextRaw);
    sessionRef.current = next;
    setSession(next);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const persistUserScoped = async (updater: (current: Session) => Session) => {
    await persist((current) => rememberCurrentUserProfile(updater(current)));
  };

  const api = useMemo(
    () => new ApiClient(session.backendUrl, session.operatorToken ?? undefined),
    [session.backendUrl, session.operatorToken],
  );

  const value: Ctx = {
    session,
    api,
    setBackendUrl: (url) => persistUserScoped((current) => ({ ...current, backendUrl: url })),
    setOperatorToken: (token) => persist((current) => ({ ...current, operatorToken: token })),
    setAppUser: (user) => persist((current) => applyAppUser(current, user)),
    setProvider: (p) => persistUserScoped((current) => ({ ...current, provider: p })),
    setAccount: (a) => persistUserScoped((current) => ({ ...current, account: a })),
    setJiraBoardId: (id) => persistUserScoped((current) => ({ ...current, jiraBoardId: id })),
    setAdoTeamPath: (p) => persistUserScoped((current) => ({ ...current, adoTeamPath: p })),
    setCurrentSprint: (sprint) =>
      persistUserScoped((current) => ({ ...current, currentSprint: sprint })),
    setProjectSetup: (setup) =>
      persistUserScoped((current) => ({
        ...current,
        projectSetup: {
          ...setup,
          repositories: setup.repositories.map(normalizeRepository),
          updatedAt: new Date().toISOString(),
        },
      })),
    reset: () => persist(initial),
  };

  if (!hydrated) return null;
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export const useSession = (): Ctx => {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be inside SessionProvider");
  return ctx;
};

const normalizeSession = (stored: Partial<Session>): Session => ({
  ...initial,
  ...stored,
  appUser: normalizeAppUser(stored.appUser),
  provider: normalizeProvider(stored.provider),
  account: cleanString(stored.account),
  jiraBoardId: cleanString(stored.jiraBoardId),
  adoTeamPath: cleanString(stored.adoTeamPath),
  currentSprint: normalizeCurrentSprint(stored.currentSprint),
  projectSetup: normalizeProjectSetup(stored.projectSetup),
  userProfiles: normalizeUserProfiles(stored.userProfiles),
});

const normalizeAppUser = (user?: AppUser | null): AppUser | null =>
  user
    ? {
        email: user.email ?? "",
        active: Boolean(user.active),
        displayName: user.displayName ?? null,
        permissions: {
          canRunAllBacklog: user.permissions?.canRunAllBacklog ?? true,
        },
      }
    : null;

const normalizeProjectSetup = (setup?: ProjectSetup | null): ProjectSetup => ({
  mode: setup?.mode === "portfolio" ? "portfolio" : "single",
  branchPattern:
    setup?.branchPattern?.trim() ||
    inferLegacyPattern(setup, "branchPattern") ||
    "feature/{item_key}-{slug}",
  commitPattern:
    setup?.commitPattern?.trim() ||
    inferLegacyPattern(setup, "commitPattern") ||
    "{type}: {summary}",
  deployTargetBranch:
    setup?.deployTargetBranch?.trim() ||
    inferLegacyPattern(setup, "deployTargetBranch") ||
    "dev",
  repositories: Array.isArray(setup?.repositories)
    ? setup.repositories.map(normalizeRepository)
    : [],
  updatedAt: setup?.updatedAt ?? null,
});

const normalizeProvider = (provider?: Provider | null): Provider | null =>
  provider === "jira" || provider === "azuredevops" ? provider : null;

const normalizeCurrentSprint = (sprint?: CurrentSprint | null): CurrentSprint | null => {
  const provider = normalizeProvider(sprint?.provider);
  const sprintId = cleanString(sprint?.sprintId);
  const sprintName = cleanString(sprint?.sprintName);
  if (!provider || !sprintId || !sprintName) return null;
  return {
    provider,
    sprintId,
    sprintName,
    sprintUrl: cleanString(sprint?.sprintUrl),
    portfolioName: cleanString(sprint?.portfolioName),
    projectName: cleanString(sprint?.projectName),
    teamName: cleanString(sprint?.teamName),
  };
};

const normalizeUserProfiles = (
  profiles?: Record<string, UserProfile> | null,
): Record<string, UserProfile> => {
  if (!profiles || typeof profiles !== "object") return {};
  return Object.entries(profiles).reduce<Record<string, UserProfile>>(
    (acc, [email, profile]) => {
      const key = normalizeUserProfileKey(email);
      const normalized = normalizeUserProfile(profile);
      if (key && normalized) acc[key] = normalized;
      return acc;
    },
    {},
  );
};

const normalizeUserProfile = (profile?: UserProfile | null): UserProfile | null => {
  if (!profile || typeof profile !== "object") return null;
  const normalized: UserProfile = {
    provider: normalizeProvider(profile.provider),
    account: cleanString(profile.account),
    jiraBoardId: cleanString(profile.jiraBoardId),
    adoTeamPath: cleanString(profile.adoTeamPath),
    currentSprint: normalizeCurrentSprint(profile.currentSprint),
    projectSetup: profile.projectSetup ? normalizeProjectSetup(profile.projectSetup) : undefined,
  };
  if (
    normalized.provider ||
    normalized.account ||
    normalized.jiraBoardId ||
    normalized.adoTeamPath ||
    normalized.currentSprint ||
    normalized.projectSetup
  ) {
    return normalized;
  }
  return null;
};

const applyAppUser = (current: Session, user: AppUser | null): Session => {
  const withSavedProfile = rememberCurrentUserProfile(current);
  const appUser = normalizeAppUser(user);
  const cleared = clearUserScopedSession(withSavedProfile);
  if (!appUser) return cleared;
  return restoreUserProfile({ ...cleared, appUser }, appUser);
};

const rememberCurrentUserProfile = (session: Session): Session => {
  const userKey = normalizeUserProfileKey(session.appUser?.email);
  const userProfiles = normalizeUserProfiles(session.userProfiles);
  if (!userKey) return { ...session, userProfiles };
  return {
    ...session,
    userProfiles: {
      ...userProfiles,
      [userKey]: buildUserProfile(session),
    },
  };
};

const restoreUserProfile = (session: Session, user: AppUser): Session => {
  const userProfiles = normalizeUserProfiles(session.userProfiles);
  const userKey = normalizeUserProfileKey(user.email);
  const profile = userKey ? userProfiles[userKey] : null;
  if (!profile) return { ...session, userProfiles };
  return {
    ...session,
    userProfiles,
    provider: profile.provider ?? null,
    account: profile.account ?? null,
    jiraBoardId: profile.jiraBoardId ?? null,
    adoTeamPath: profile.adoTeamPath ?? null,
    currentSprint: profile.currentSprint ?? null,
    projectSetup: profile.projectSetup ?? normalizeProjectSetup(null),
  };
};

const clearUserScopedSession = (session: Session): Session => ({
  ...session,
  appUser: null,
  provider: null,
  account: null,
  jiraBoardId: null,
  adoTeamPath: null,
  currentSprint: null,
  projectSetup: normalizeProjectSetup(null),
});

const buildUserProfile = (session: Session): UserProfile => ({
  provider: session.provider,
  account: session.account,
  jiraBoardId: session.jiraBoardId ?? null,
  adoTeamPath: session.adoTeamPath ?? null,
  currentSprint: session.currentSprint ?? null,
  projectSetup: session.projectSetup,
});

const normalizeUserProfileKey = (email?: string | null): string | null => {
  const value = email?.trim().toLowerCase();
  return value || null;
};

const cleanString = (value?: string | null): string | null => {
  const trimmed = value?.trim();
  return trimmed || null;
};

const normalizeRepository = (repo: RepositoryRegistration): RepositoryRegistration => ({
  id: repo.id || `repo-${Date.now().toString(36)}`,
  name: repo.name ?? "",
  repoPath: repo.repoPath ?? "",
  role: repo.role ?? "fullstack",
  project: repo.project ?? "",
  validationCommands: Array.isArray(repo.validationCommands)
    ? repo.validationCommands.filter(Boolean)
    : [],
});

const inferLegacyPattern = (
  setup: ProjectSetup | null | undefined,
  key: "branchPattern" | "commitPattern" | "deployTargetBranch",
): string | null => {
  const firstRepo = Array.isArray(setup?.repositories) ? setup.repositories[0] as Record<string, unknown> | undefined : undefined;
  const value = typeof firstRepo?.[key] === "string" ? String(firstRepo[key]).trim() : "";
  return value || null;
};
