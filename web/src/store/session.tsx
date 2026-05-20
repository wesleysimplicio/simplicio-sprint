import AsyncStorage from "@react-native-async-storage/async-storage";
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import Constants from "expo-constants";
import { ApiClient } from "../api/client";
import type { ProjectSetup, Provider, RepositoryRegistration } from "../api/types";

const STORAGE_KEY = "sendsprint.session.v1";

type Session = {
  backendUrl: string;
  provider: Provider | null;
  account: string | null;
  jiraBoardId?: string | null;
  adoTeamPath?: string | null;
  projectSetup: ProjectSetup;
};

type Ctx = {
  session: Session;
  api: ApiClient;
  setBackendUrl: (url: string) => Promise<void>;
  setProvider: (p: Provider | null) => Promise<void>;
  setAccount: (account: string | null) => Promise<void>;
  setJiraBoardId: (id: string | null) => Promise<void>;
  setAdoTeamPath: (path: string | null) => Promise<void>;
  setProjectSetup: (setup: ProjectSetup) => Promise<void>;
  reset: () => Promise<void>;
};

const defaultBackend =
  ((Constants.expoConfig?.extra as { defaultBackend?: string } | undefined) ?.defaultBackend) ??
  "http://localhost:8765";

const defaultProjectSetup: ProjectSetup = {
  mode: "single",
  repositories: [],
  updatedAt: null,
};

const initial: Session = {
  backendUrl: defaultBackend,
  provider: null,
  account: null,
  jiraBoardId: null,
  adoTeamPath: null,
  projectSetup: defaultProjectSetup,
};

const SessionContext = createContext<Ctx | null>(null);

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [session, setSession] = useState<Session>(initial);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) setSession(normalizeSession(JSON.parse(raw) as Partial<Session>));
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  const persist = async (next: Session) => {
    setSession(next);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const api = useMemo(() => new ApiClient(session.backendUrl), [session.backendUrl]);

  const value: Ctx = {
    session,
    api,
    setBackendUrl: (url) => persist({ ...session, backendUrl: url }),
    setProvider: (p) => persist({ ...session, provider: p }),
    setAccount: (a) => persist({ ...session, account: a }),
    setJiraBoardId: (id) => persist({ ...session, jiraBoardId: id }),
    setAdoTeamPath: (p) => persist({ ...session, adoTeamPath: p }),
    setProjectSetup: (setup) =>
      persist({
        ...session,
        projectSetup: {
          ...setup,
          repositories: setup.repositories.map(normalizeRepository),
          updatedAt: new Date().toISOString(),
        },
      }),
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
  provider:
    stored.provider === "jira" || stored.provider === "azuredevops"
      ? stored.provider
      : initial.provider,
  projectSetup: normalizeProjectSetup(stored.projectSetup),
});

const normalizeProjectSetup = (setup?: ProjectSetup | null): ProjectSetup => ({
  mode: setup?.mode === "portfolio" ? "portfolio" : "single",
  repositories: Array.isArray(setup?.repositories)
    ? setup.repositories.map(normalizeRepository)
    : [],
  updatedAt: setup?.updatedAt ?? null,
});

const normalizeRepository = (repo: RepositoryRegistration): RepositoryRegistration => ({
  id: repo.id || `repo-${Date.now().toString(36)}`,
  name: repo.name ?? "",
  repoPath: repo.repoPath ?? "",
  role: repo.role ?? "fullstack",
  project: repo.project ?? "",
  branchPattern: repo.branchPattern ?? "feature/{item_key}-{slug}",
  commitPattern: repo.commitPattern ?? "{type}: {summary}",
  validationCommands: Array.isArray(repo.validationCommands)
    ? repo.validationCommands.filter(Boolean)
    : [],
});
