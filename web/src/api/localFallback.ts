import type {
  ActionResponse,
  AppLoginResponse,
  ArchiveSprintItemRequest,
  AuthBootstrap,
  AuthResponse,
  AuthStatus,
  ColumnKey,
  ControlPlaneRunDetail,
  ControlPlaneRunSummary,
  DashboardSnapshot,
  Health,
  ImportStatus,
  MoveSprintItemRequest,
  Provider,
  RoutePreviewResponse,
  RunEvent,
  RunStatus,
  SprintDetail,
  SprintItem,
  SprintSummary,
  StartRunRequest,
  StartRunResponse,
  ValidationDashboardResponse,
  AgentDashboardResponse,
  TupleDashboardResponse,
  VersionCheckResponse,
  YoolDashboardResponse,
} from "./types";

const STORAGE_KEY = "sendsprint.local-api.v1";
const LOCAL_OPERATOR_TOKEN = "local-demo-operator-token";
const LOCAL_EVIDENCE =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6i0AAAAASUVORK5CYII=";

type LocalState = {
  appUser: AppLoginResponse | null;
  auth: AuthStatus;
  sprints: Record<string, SprintDetail>;
  runs: Record<string, ControlPlaneRunDetail>;
  importJobs: Record<string, ImportStatus>;
};

type LocalRequest = {
  path: string;
  method: string;
  query: URLSearchParams;
  body: unknown;
};

export const isLocalFallbackUrl = (url: string): boolean => url.startsWith("local://sendsprint/");

export const localEvidenceUrl = (): string => LOCAL_EVIDENCE;

export const localEventsUrl = (runId: string): string =>
  `local://sendsprint/runs/${encodeURIComponent(runId)}/events`;

export const getLocalRunEvents = (url: string): RunEvent[] => {
  const runId = decodeURIComponent(url.split("/runs/")[1]?.split("/")[0] ?? "local-run");
  return [
    { type: "step", run_id: runId, step: 1, status: "ok", progress: 0.12, message: "Sprint local carregada" },
    { type: "log", run_id: runId, message: "Modo local ativo: backend indisponivel, usando dados editaveis do navegador." },
    { type: "step", run_id: runId, step: 2, status: "ok", progress: 0.24, message: "Arquitetura mapeada em modo demo" },
    { type: "step", run_id: runId, step: 3, status: "ok", progress: 0.36, message: "Worktree simulado" },
    { type: "loop", run_id: runId, iteration: 1, max_iterations: 3, message: "fix loop sem falhas criticas" },
    { type: "step", run_id: runId, step: 5, status: "ok", progress: 0.62, message: "Playwright smoke local concluido" },
    { type: "evidence", run_id: runId, evidence_path: "local-evidence.png", evidence_label: "Local UI smoke", iteration: 1 },
    { type: "step", run_id: runId, step: 10, status: "ok", progress: 1, message: "Entrega local pronta para review" },
    { type: "done", run_id: runId, failed: false, pr_url: `https://github.com/local/sendsprint/pull/${runId.split("-").pop()}` },
  ];
};

export const handleLocalApiRequest = async <T>(request: LocalRequest): Promise<T> => {
  const state = loadState();
  const result = routeLocalRequest(state, request);
  saveState(state);
  return result as T;
};

export const parseRequestBody = (init?: RequestInit): unknown => {
  if (!init?.body || typeof init.body !== "string") return null;
  try {
    return JSON.parse(init.body) as unknown;
  } catch {
    return null;
  }
};

const routeLocalRequest = (state: LocalState, request: LocalRequest): unknown => {
  const { path, method, query, body } = request;

  if (path === "/health" && method === "GET") return localHealth();
  if (path === "/version/check" && method === "GET") return localVersion();
  if (path === "/auth/bootstrap" && method === "GET") {
    return { ...state.auth, operator_token: LOCAL_OPERATOR_TOKEN } satisfies AuthBootstrap;
  }
  if (path === "/auth/status" && method === "GET") return state.auth;
  if (path === "/auth/app-login" && method === "POST") return loginApp(state, asRecord(body));
  if (path === "/auth/jira" && method === "POST") return authProvider(state, "jira", asRecord(body));
  if (path === "/auth/azuredevops" && method === "POST") {
    return authProvider(state, "azuredevops", asRecord(body));
  }
  if (path === "/sprints" && method === "GET") return listSprints(state, query);
  if (path === "/sprints/import" && method === "POST") return startImport(state);
  if (path.startsWith("/sprints/import/") && method === "GET") return finishImport(state, path);
  if (path.startsWith("/sprints/") && path.includes("/items/") && path.endsWith("/move")) {
    return moveItem(state, path, asRecord(body) as MoveSprintItemRequest);
  }
  if (path.startsWith("/sprints/") && path.includes("/items/") && path.endsWith("/archive")) {
    return archiveItem(state, path, asRecord(body) as ArchiveSprintItemRequest);
  }
  if (path.startsWith("/sprints/") && method === "GET") return getSprint(state, path, query);
  if (path === "/runs" && method === "POST") return startRun(state, asRecord(body) as StartRunRequest);
  if (path === "/runs/preview" && method === "POST") return previewRun(state, asRecord(body) as StartRunRequest);
  if (path.startsWith("/runs/") && path.endsWith("/dashboard") && method === "GET") return runDashboard(state, path);
  if (path.startsWith("/runs/") && method === "GET") return legacyRunStatus(state, path);
  if (path === "/api/runs" && method === "GET") return Object.values(state.runs).map((run) => run.run);
  if (path === "/api/runs/preview" && method === "POST") return previewRun(state, asRecord(body) as StartRunRequest);
  if (path.startsWith("/api/runs/") && path.includes("/actions/") && method === "POST") {
    return runAction(state, path);
  }
  if (path.startsWith("/api/runs/") && path.endsWith("/audit") && method === "GET") return runAudit(path);
  if (path.startsWith("/api/runs/") && method === "GET") return controlRunDetail(state, path);
  if (path === "/api/dashboard/validations" && method === "GET") return validationDashboard(state);
  if (path === "/api/dashboard/agents" && method === "GET") return agentDashboard(state);
  if (path === "/api/dashboard/tuples" && method === "GET") return tupleDashboard(state);
  if (path === "/api/dashboard/yools" && method === "GET") return yoolDashboard();

  throw new Error(`Local SendSprint fallback does not implement ${method} ${path}`);
};

const localHealth = (): Health => ({
  ok: true,
  version: "local-web",
  providers_configured: { jira: true, azuredevops: true },
});

const localVersion = (): VersionCheckResponse => ({
  current_version: "local-web",
  latest_version: "local-web",
  update_available: false,
  status: "ok",
  source: "local-fallback",
  source_url: "local://sendsprint/version",
  message: "Rodando em modo local editavel.",
});

const loginApp = (state: LocalState, payload: Record<string, unknown>): AppLoginResponse => {
  const email = String(payload.email ?? "").trim().toLowerCase();
  if (!email || !email.includes("@")) throw new Error("Informe um email valido.");
  const display = email.split("@")[0].replace(/[._-]/g, " ");
  state.appUser = {
    ok: true,
    email,
    active: true,
    display_name: display.replace(/\b\w/g, (c) => c.toUpperCase()),
    permissions: { can_run_all_backlog: true },
  };
  return state.appUser;
};

const authProvider = (state: LocalState, provider: Provider, payload: Record<string, unknown>): AuthResponse => {
  const email =
    String(payload.email ?? payload.user_email ?? state.appUser?.email ?? "operator@sendsprint.local")
      .trim()
      .toLowerCase() || "operator@sendsprint.local";

  if (provider === "jira") {
    state.auth.default_provider = "jira";
    state.auth.jira_configured = true;
    state.auth.providers.jira = { configured: true, account: email };
    const sprint = ensureJiraSprint(state, email, String(payload.base_url ?? "https://local.atlassian.net"));
    return {
      provider,
      account: email,
      ok: true,
      user_display_name: state.appUser?.display_name ?? email,
      fallback_used: true,
      capture_transport: "local-web",
    };
  }

  const parsed = parseAzureContext(String(payload.sprint_url ?? ""), payload);
  state.auth.default_provider = "azuredevops";
  state.auth.azuredevops_configured = true;
  state.auth.providers.azuredevops = {
    configured: true,
    account: `${parsed.organization}/${parsed.project}`,
    user_email: email,
    team_path: `${parsed.organization}/${parsed.project}/${parsed.team}`,
    iteration_path: parsed.sprintId,
  };
  ensureAzureSprint(state, email, parsed);
  return {
    provider,
    account: `${parsed.organization}/${parsed.project}`,
    ok: true,
    user_display_name: email,
    ado_team_path: `${parsed.organization}/${parsed.project}/${parsed.team}`,
    ado_iteration_path: parsed.sprintId,
    fallback_used: true,
    capture_transport: "local-web",
  };
};

const listSprints = (state: LocalState, query: URLSearchParams): SprintSummary[] => {
  const provider = (query.get("provider") as Provider | null) ?? state.auth.default_provider ?? "azuredevops";
  ensureDefaultSprint(state, provider);
  return Object.values(state.sprints)
    .map((detail) => detail.sprint)
    .filter((sprint) => sprint.provider === provider);
};

const getSprint = (state: LocalState, path: string, query: URLSearchParams): SprintDetail => {
  const sprintId = decodeURIComponent(path.split("/sprints/")[1] ?? "");
  const provider = (query.get("provider") as Provider | null) ?? state.auth.default_provider ?? "azuredevops";
  ensureDefaultSprint(state, provider, sprintId);
  const detail = state.sprints[sprintId] ?? Object.values(state.sprints).find((s) => s.sprint.provider === provider);
  if (!detail) throw new Error("Sprint local nao encontrada.");
  const includeArchived = query.get("include_archived") === "true";
  const userEmail = query.get("user_email")?.trim().toLowerCase();
  const items = detail.items.filter((item) => {
    if (!includeArchived && item.archived) return false;
    if (query.get("scope") === "mine" && userEmail) return item.assignee_email?.toLowerCase() === userEmail;
    return true;
  });
  return {
    ...detail,
    items,
    archived_count: detail.items.filter((item) => item.archived).length,
  };
};

const startImport = (state: LocalState): { job_id: string; started: boolean } => {
  const id = `local-import-${Date.now().toString(36)}`;
  state.importJobs[id] = { state: "running", fetched: 1, total: 3 };
  ensureDefaultSprint(state, state.auth.default_provider ?? "azuredevops");
  return { job_id: id, started: true };
};

const finishImport = (state: LocalState, path: string): ImportStatus => {
  const jobId = decodeURIComponent(path.split("/sprints/import/")[1] ?? "");
  const current = state.importJobs[jobId] ?? { state: "running", fetched: 1, total: 3 };
  const done: ImportStatus = { ...current, state: "done", fetched: current.total ?? 3, total: current.total ?? 3 };
  state.importJobs[jobId] = done;
  return done;
};

const moveItem = (state: LocalState, path: string, payload: MoveSprintItemRequest): SprintItem => {
  const { sprintId, itemKey } = parseItemPath(path, "/move");
  const detail = state.sprints[sprintId];
  if (!detail) throw new Error("Sprint local nao encontrada.");
  const item = detail.items.find((candidate) => candidate.key === itemKey || candidate.id === itemKey);
  if (!item) throw new Error("Card local nao encontrado.");
  const previous = item.board_column ?? "backlog";
  item.board_column = payload.target_column;
  item.board_status = columnLabel(payload.target_column);
  item.board_updated_at = new Date().toISOString();
  item.board_updated_by = payload.actor_email ?? state.appUser?.email ?? "local-operator";
  item.history = [
    ...(item.history ?? []),
    {
      observed_at: item.board_updated_at,
      action: "move",
      actor_email: item.board_updated_by,
      from_column: previous,
      to_column: payload.target_column,
      archived: item.archived,
      note: payload.note ?? "local move",
    },
  ];
  return item;
};

const archiveItem = (state: LocalState, path: string, payload: ArchiveSprintItemRequest): SprintItem => {
  const { sprintId, itemKey } = parseItemPath(path, "/archive");
  const detail = state.sprints[sprintId];
  if (!detail) throw new Error("Sprint local nao encontrada.");
  const item = detail.items.find((candidate) => candidate.key === itemKey || candidate.id === itemKey);
  if (!item) throw new Error("Card local nao encontrado.");
  item.archived = payload.archived;
  item.board_updated_at = new Date().toISOString();
  item.board_updated_by = payload.actor_email ?? state.appUser?.email ?? "local-operator";
  item.history = [
    ...(item.history ?? []),
    {
      observed_at: item.board_updated_at,
      action: payload.archived ? "archive" : "restore",
      actor_email: item.board_updated_by,
      from_column: item.board_column ?? "backlog",
      to_column: item.board_column ?? "backlog",
      archived: item.archived,
      note: payload.note ?? "local archive",
    },
  ];
  return item;
};

const startRun = (state: LocalState, payload: StartRunRequest): StartRunResponse => {
  const runId = payload.run_id || `local-run-${Date.now().toString(36)}`;
  const detail = state.sprints[payload.sprint_id] ?? ensureDefaultSprint(state, payload.provider, payload.sprint_id);
  const itemKeys = payload.item_keys?.length ? payload.item_keys : detail.items.filter((item) => !item.archived).map((item) => item.key);
  const now = new Date().toISOString();
  const summary: ControlPlaneRunSummary = {
    run_id: runId,
    state: "done",
    sprint_id: payload.sprint_id,
    provider: payload.provider,
    autonomy_level: payload.autonomy_level ?? "standard",
    item_keys: itemKeys,
    task: itemKeys.length ? `Executar ${itemKeys.join(", ")}` : "Executar sprint local",
    branch: itemKeys[0] ? `feature/${itemKeys[0].toLowerCase()}-local` : "feature/local-run",
    readiness_score: 0.96,
    readiness_verdict: "ready_for_review",
    started_at: now,
    finished_at: now,
    summary: "Execucao local simulada concluida. Configure o backend para executar comandos reais.",
    pr_url: `https://github.com/local/sendsprint/pull/${runId.split("-").pop()}`,
    failed: false,
    last_step: 10,
    progress: 1,
  };
  state.runs[runId] = {
    run: summary,
    quality_gate: {
      run_id: runId,
      verdict: "ready_for_review",
      checks: [
        { check_name: "local-ui", passed: true, details: "Fluxo editavel validado no navegador.", severity: "info" },
        { check_name: "repository", passed: true, details: "Repositorio local configurado no Project Setup.", severity: "info" },
      ],
      reasons: ["Modo local habilitado porque o backend nao respondeu."],
      created_at: now,
    },
    evidence: {
      run_id: runId,
      items: [
        {
          type: "screenshot",
          path: "local-evidence.png",
          label: "Local UI smoke",
          iteration: 1,
          observed_at: now,
        },
      ],
      total_items: 1,
      finalized: true,
      created_at: now,
    },
    logs: ["Modo local ativo", "Planejamento simulado", "Gates locais concluídos"],
    timeline: [
      { step: 1, status: "ok" },
      { step: 5, status: "ok" },
      { step: 10, status: "done" },
    ],
  };
  return { run_id: runId, status: "started" };
};

const previewRun = (state: LocalState, payload: StartRunRequest): RoutePreviewResponse => {
  const detail = state.sprints[payload.sprint_id] ?? ensureDefaultSprint(state, payload.provider, payload.sprint_id);
  const itemKeys = payload.item_keys?.length ? payload.item_keys : detail.items.map((item) => item.key);
  const repos = payload.project_setup?.repositories ?? [];
  const branchPattern = resolveProjectSetupString(payload.project_setup, "branchPattern", "feature/{item_key}-{slug}");
  const deployTargetBranch = resolveProjectSetupString(payload.project_setup, "deployTargetBranch", "dev");
  return {
    schema_version: "local-web.v1",
    provider: payload.provider,
    sprint_id: payload.sprint_id,
    sprint_name: detail.sprint.name,
    mode: payload.mode,
    item_keys: itemKeys,
    autonomy_level: payload.autonomy_level ?? "standard",
    side_effects: { commit: false, push: false, pr: false },
    summary: {
      text: "Preview local gerado no navegador.",
      task_count: itemKeys.length,
      planned_delivery_count: itemKeys.length,
      selected_repo_count: repos.length,
      low_confidence_count: repos.length ? 0 : itemKeys.length,
      warning_count: repos.length ? 0 : 1,
    },
    task_understanding: itemKeys.map((key) => ({
      item_key: key,
      item_type: "Story",
      title: detail.items.find((item) => item.key === key)?.title ?? key,
      status: "Backlog",
      scopes: ["web"],
      scope_source: "inferred",
      relationship: "selected",
      selected_repos: repos.map((repo) => repo.name || repo.repoPath),
      confidence: repos.length ? "high" : "low",
      reasons: repos.length ? ["Repositorio configurado localmente."] : ["Configure um repositorio local."],
    })),
    selected_repos: itemKeys.flatMap((key) =>
      repos.map((repo) => ({
        item_key: key,
        item_type: "Story",
        title: detail.items.find((item) => item.key === key)?.title ?? key,
        repo: repo.repoPath,
        repo_name: repo.name || repo.repoPath,
        repo_role: repo.role,
        branch: branchPattern.replace("{item_key}", key).replace("{slug}", "local-task"),
        target_branch: deployTargetBranch,
        confidence: "high",
        reasons: ["Cadastro local editavel."],
        relationship: "configured",
        validation_template: "local",
        validation_commands: repo.validationCommands,
      })),
    ),
    low_confidence_items: repos.length
      ? []
      : itemKeys.map((key) => ({
          item_key: key,
          title: detail.items.find((item) => item.key === key)?.title ?? key,
          confidence: "low",
          reason: "Nenhum repositorio local cadastrado.",
          recommended_action: "Abra Project Setup e salve um caminho local.",
        })),
    warnings: repos.length ? [] : ["Execucao real requer Project Setup."],
  };
};

const legacyRunStatus = (state: LocalState, path: string): RunStatus => {
  const runId = decodeURIComponent(path.split("/runs/")[1] ?? "");
  const run = state.runs[runId]?.run;
  if (!run) throw new Error("Run local nao encontrada.");
  return {
    run_id: run.run_id,
    state: run.failed ? "failed" : "done",
    sprint_id: run.sprint_id,
    provider: run.provider as Provider,
    started_at: run.started_at,
    finished_at: run.finished_at,
    summary: run.summary,
    pr_url: run.pr_url,
    failed: run.failed,
    last_step: run.last_step,
  };
};

const runDashboard = (state: LocalState, path: string): DashboardSnapshot => {
  const runId = decodeURIComponent(path.split("/runs/")[1]?.split("/")[0] ?? "");
  const detail = state.runs[runId];
  if (!detail) throw new Error("Run local nao encontrada.");
  return {
    run: legacyRunStatus(state, `/runs/${runId}`),
    evidence: detail.evidence?.items.map((item) => ({ name: item.label, path: item.path })) ?? [],
    summary: detail.run.summary,
    pr_url: detail.run.pr_url,
    blockers: [],
  };
};

const controlRunDetail = (state: LocalState, path: string): ControlPlaneRunDetail => {
  const runId = decodeURIComponent(path.split("/api/runs/")[1] ?? "");
  const detail = state.runs[runId];
  if (!detail) throw new Error("Run local nao encontrada.");
  return detail;
};

const runAction = (state: LocalState, path: string): ActionResponse => {
  const parts = path.split("/");
  const runId = decodeURIComponent(parts[3] ?? "");
  const action = parts[5] ?? "action";
  const detail = state.runs[runId];
  if (detail) {
    detail.logs = [...detail.logs, `action:${action}`];
    if (action === "cancel") detail.run.state = "cancelled";
    if (action === "approve") detail.run.readiness_verdict = "approved";
  }
  return { run_id: runId, action, result: "ok", detail: { mode: "local-web" } };
};

const runAudit = (path: string) => {
  const runId = decodeURIComponent(path.split("/api/runs/")[1]?.split("/")[0] ?? "");
  return {
    entries: [
      {
        operator: "local-web",
        action: "view",
        run_id: runId,
        timestamp: new Date().toISOString(),
        result: "ok",
        detail: { mode: "local fallback" },
      },
    ],
    total: 1,
  };
};

const validationDashboard = (state: LocalState): ValidationDashboardResponse => ({
  lanes: [
    {
      lane: "web-local",
      status: "ok",
      last_run_id: Object.keys(state.runs).at(-1) ?? null,
      last_result: "Modo local editavel ativo",
      events_count: Object.keys(state.runs).length,
      errors: [],
    },
  ],
  total_events: Object.keys(state.runs).length,
});

const agentDashboard = (state: LocalState): AgentDashboardResponse => ({
  agents: [
    {
      key: "local-web",
      name: "Local Web Fallback",
      runtime: "browser",
      capabilities: ["login", "cadastro", "kanban", "run-preview"],
      active_runs: Object.keys(state.runs).length,
      notes: ["Use o backend Python para execucao real em worktree."],
    },
  ],
  total_active_runs: Object.keys(state.runs).length,
});

const tupleDashboard = (state: LocalState): TupleDashboardResponse => ({
  tuples: Object.values(state.runs).map((detail) => ({
    run_id: detail.run.run_id,
    state: detail.run.state,
    sprint_id: detail.run.sprint_id,
    provider: detail.run.provider,
    started_at: detail.run.started_at,
    finished_at: detail.run.finished_at,
    failed: detail.run.failed,
    event_count: detail.timeline.length,
    last_event_type: "done",
    progress: detail.run.progress,
  })),
  total_runs: Object.keys(state.runs).length,
  active_runs: 0,
  failed_runs: Object.values(state.runs).filter((detail) => detail.run.failed).length,
});

const yoolDashboard = (): YoolDashboardResponse => ({
  yools: [
    {
      yool_id: "local_web_fallback",
      total_invocations: 1,
      cache_hits: 0,
      cache_misses: 1,
      cache_hit_rate: 0,
      total_retries: 0,
      total_cost_usd: 0,
      total_duration_ms: 120,
      avg_duration_ms: 120,
      last_status: "ok",
      errors: [],
    },
  ],
  cache_stats: { mode: "local" },
  registered_contracts: 1,
});

const ensureDefaultSprint = (state: LocalState, provider: Provider, sprintId?: string): SprintDetail => {
  if (sprintId && state.sprints[sprintId]) return state.sprints[sprintId];
  const email = state.appUser?.email ?? "operator@sendsprint.local";
  if (provider === "jira") return ensureJiraSprint(state, email, "https://local.atlassian.net", sprintId);
  return ensureAzureSprint(
    state,
    email,
    parseAzureContext("", {
      organization: "local-company",
      project: "sendsprint-web",
      team: "delivery",
      sprint_url: "",
      sprint_id: sprintId,
    }),
  );
};

const ensureJiraSprint = (state: LocalState, email: string, baseUrl: string, sprintId?: string): SprintDetail => {
  const host = safeHost(baseUrl) ?? "jira-local";
  const id = sprintId || `${host}/SendSprint/Sprint Local`;
  if (!state.sprints[id]) {
    state.sprints[id] = makeSprintDetail("jira", id, "Sprint Local Jira", "Jira", host, "Delivery", email);
  }
  return state.sprints[id];
};

const ensureAzureSprint = (
  state: LocalState,
  email: string,
  ctx: ReturnType<typeof parseAzureContext>,
): SprintDetail => {
  if (!state.sprints[ctx.sprintId]) {
    state.sprints[ctx.sprintId] = makeSprintDetail(
      "azuredevops",
      ctx.sprintId,
      ctx.sprintName,
      ctx.organization,
      ctx.project,
      ctx.team,
      email,
    );
  }
  return state.sprints[ctx.sprintId];
};

const makeSprintDetail = (
  provider: Provider,
  id: string,
  name: string,
  portfolio: string,
  project: string,
  team: string,
  email: string,
): SprintDetail => {
  const now = new Date().toISOString();
  return {
    sprint: {
      id,
      name,
      state: "active",
      provider,
      start_date: now,
      end_date: now,
      item_count: 3,
      goal: "Validar fluxo editavel do SendSprint web.",
    },
    items: [
      makeItem("SS-101", "Configurar repositorio local do projeto", "Story", email, now, provider, id),
      makeItem("SS-102", "Importar backlog e revisar cards", "Task", email, now, provider, id),
      makeItem("SS-103", "Executar fluxo local com evidencia", "Bug", email, now, provider, id),
    ],
    archived_count: 0,
  };
};

const makeItem = (
  key: string,
  title: string,
  type: string,
  email: string,
  now: string,
  provider: Provider,
  sprintId: string,
): SprintItem => ({
  id: key,
  key,
  type,
  title,
  status: "To Do",
  description: "Card local editavel para testar configuracao, movimentacao e execucao sem backend ativo.",
  revision: "1",
  assignee: email.split("@")[0],
  assignee_email: email,
  story_points: key.endsWith("101") ? 5 : 3,
  parent_key: null,
  labels: ["local", "web"],
  links: [{ type: "source", target_key: sprintId, target_url: `${provider}://${sprintId}` }],
  comments: [{ author: "SendSprint", body: "Criado pelo fallback local.", created_at: now }],
  attachments: [],
  acceptance_criteria: "O card deve abrir, mover, arquivar/restaurar e aparecer nos relatorios locais.",
  created_at: now,
  updated_at: now,
  source_url: `${provider}://${sprintId}/${key}`,
  board_column: "backlog",
  board_status: "Backlog",
  board_updated_at: now,
  board_updated_by: email,
  archived: false,
  history: [],
});

const parseAzureContext = (sprintUrl: string, payload: Record<string, unknown>) => {
  const defaults = {
    organization: String(payload.organization ?? "local-company"),
    project: String(payload.project ?? "sendsprint-web"),
    team: String(payload.team ?? "delivery"),
    sprintName: "Sprint Local",
  };
  try {
    const url = new URL(sprintUrl);
    const parts = url.pathname.split("/").filter(Boolean).map(decodeURIComponent);
    const isDevAzure = url.hostname === "dev.azure.com";
    const organization = String(payload.organization ?? (isDevAzure ? parts[0] : url.hostname.split(".")[0]) ?? defaults.organization);
    const project = String(payload.project ?? (isDevAzure ? parts[1] : parts[0]) ?? defaults.project);
    const boardIndex = parts.findIndex((part) => part === "_sprints");
    const team = String(payload.team ?? parts[boardIndex + 2] ?? defaults.team);
    const sprintName = String(parts.at(-1) ?? defaults.sprintName);
    return {
      organization: cleanSegment(organization),
      project: cleanSegment(project),
      team: cleanSegment(team),
      sprintName: cleanSegment(sprintName),
      sprintId: `${cleanSegment(organization)}/${cleanSegment(project)}/${cleanSegment(team)}/${cleanSegment(sprintName)}`,
    };
  } catch {
    const organization = cleanSegment(defaults.organization);
    const project = cleanSegment(defaults.project);
    const team = cleanSegment(defaults.team);
    const sprintName = cleanSegment(String(payload.sprint_id ?? defaults.sprintName));
    return { organization, project, team, sprintName, sprintId: `${organization}/${project}/${team}/${sprintName}` };
  }
};

const parseItemPath = (path: string, suffix: string): { sprintId: string; itemKey: string } => {
  const trimmed = path.endsWith(suffix) ? path.slice(0, -suffix.length) : path;
  const [sprintPart, itemPart] = trimmed.split("/items/");
  return {
    sprintId: decodeURIComponent(sprintPart.replace("/sprints/", "")),
    itemKey: decodeURIComponent(itemPart ?? ""),
  };
};

const columnLabel = (column: ColumnKey): string =>
  ({
    backlog: "Backlog",
    planning: "Planning",
    programming: "Programming",
    testing: "Testing",
    review: "Review Humana",
    awaiting_deploy: "Awaiting Deploy",
    blocked: "Blocked",
  })[column];

const loadState = (): LocalState => {
  if (typeof localStorage === "undefined") return createInitialState();
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return createInitialState();
  try {
    return normalizeState(JSON.parse(raw) as Partial<LocalState>);
  } catch {
    return createInitialState();
  }
};

const saveState = (state: LocalState) => {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};

const createInitialState = (): LocalState => ({
  appUser: null,
  auth: {
    default_provider: null,
    jira_configured: false,
    azuredevops_configured: false,
    providers: {
      jira: { configured: false, account: null },
      azuredevops: { configured: false, account: null, user_email: null, team_path: null, iteration_path: null },
      github: { configured: true },
    },
  },
  sprints: {},
  runs: {},
  importJobs: {},
});

const normalizeState = (raw: Partial<LocalState>): LocalState => ({
  ...createInitialState(),
  ...raw,
  auth: {
    ...createInitialState().auth,
    ...raw.auth,
    providers: {
      ...createInitialState().auth.providers,
      ...raw.auth?.providers,
      azuredevops: {
        ...createInitialState().auth.providers.azuredevops,
        ...raw.auth?.providers?.azuredevops,
      },
    },
  },
  sprints: raw.sprints ?? {},
  runs: raw.runs ?? {},
  importJobs: raw.importJobs ?? {},
});

const asRecord = (value: unknown): Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};

const safeHost = (value: string): string | null => {
  try {
    return new URL(value).hostname;
  } catch {
    return null;
  }
};

const cleanSegment = (value: string): string => value.trim().replace(/^\/+|\/+$/g, "") || "local";

const resolveProjectSetupString = (
  projectSetup: StartRunRequest["project_setup"],
  key: "branchPattern" | "commitPattern" | "deployTargetBranch",
  fallback: string,
): string => {
  const topLevel = typeof projectSetup?.[key] === "string" ? String(projectSetup[key]).trim() : "";
  if (topLevel) return topLevel;
  const firstRepo = Array.isArray(projectSetup?.repositories) ? projectSetup.repositories[0] as Record<string, unknown> | undefined : undefined;
  const legacy = typeof firstRepo?.[key] === "string" ? String(firstRepo[key]).trim() : "";
  return legacy || fallback;
};
