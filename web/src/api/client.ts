import type {
  ApiErrorPayload,
  ArchiveSprintItemRequest,
  AppLoginResponse,
  AuthBootstrap,
  AuthStatus,
  AuthResponse,
  AgentDashboardResponse,
  AuditQueryResponse,
  ActionRequest,
  ActionResponse,
  MoveSprintItemRequest,
  ControlPlaneRunDetail,
  ControlPlaneRunSummary,
  DashboardSnapshot,
  Health,
  ImportSprintsResponse,
  ImportStatus,
  Provider,
  RoutePreviewResponse,
  RunStatus,
  SprintItem,
  SprintDetail,
  SprintSummary,
  StartRunRequest,
  StartRunResponse,
  TupleDashboardResponse,
  ValidationDashboardResponse,
  VersionCheckResponse,
  YoolDashboardResponse,
} from "./types";

type ResponseBody = ApiErrorPayload | unknown[] | string | null;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const tryParseJson = (text: string): ResponseBody => {
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as ResponseBody;
  } catch {
    return text;
  }
};

const stringifyDetail = (detail: unknown): string | null => {
  if (detail == null) return null;
  if (typeof detail === "string") return detail.trim() || null;
  if (typeof detail === "number" || typeof detail === "boolean") return String(detail);
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => stringifyValidationItem(item)).filter(Boolean);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  if (isRecord(detail)) {
    const nested = stringifyDetail(detail.detail ?? detail.message ?? detail.error ?? detail.msg);
    if (nested) return nested;
    try {
      return JSON.stringify(detail);
    } catch {
      return "Unexpected backend error payload.";
    }
  }
  return String(detail);
};

const stringifyValidationItem = (item: unknown): string | null => {
  if (!isRecord(item)) return stringifyDetail(item);
  const message = stringifyDetail(item.msg ?? item.message ?? item.detail ?? item.error);
  const loc = Array.isArray(item.loc) ? item.loc.join(".") : null;
  if (message && loc) return `${loc}: ${message}`;
  if (message) return message;
  return stringifyDetail(item);
};

const extractBackendMessage = (body: ResponseBody): string | null => {
  if (typeof body === "string") return body.trim() || null;
  if (Array.isArray(body)) return stringifyDetail(body);
  if (isRecord(body)) return stringifyDetail(body.detail ?? body.message ?? body.error);
  return null;
};

export class ApiClient {
  constructor(
    private baseUrl: string,
    private operatorToken?: string,
  ) {}

  setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, "");
  }

  getBaseUrl() {
    return this.baseUrl;
  }

  setOperatorToken(token: string | null | undefined) {
    this.operatorToken = token ?? undefined;
  }

  private async req<T>(
    path: string,
    init?: RequestInit & { query?: Record<string, string | undefined> },
  ): Promise<T> {
    const url = new URL(this.baseUrl + path);
    if (init?.query) {
      for (const [k, v] of Object.entries(init.query)) {
        if (v !== undefined) url.searchParams.set(k, v);
      }
    }
    const resp = await fetch(url.toString(), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(this.operatorToken && init?.method && init.method.toUpperCase() !== "GET"
          ? { Authorization: `Bearer ${this.operatorToken}` }
          : {}),
        ...(init?.headers ?? {}),
      },
    });
    const raw = await resp.text();
    const body = tryParseJson(raw);
    if (!resp.ok) {
      throw new ApiError(resp.status, resp.statusText, body);
    }
    return body as T;
  }

  health() {
    return this.req<Health>("/health");
  }

  checkVersion() {
    return this.req<VersionCheckResponse>("/version/check");
  }

  authJira(input: {
    base_url: string;
    email: string;
    api_token: string;
    sprint_url?: string;
    sprint_id?: string;
  }) {
    return this.req<AuthResponse>("/auth/jira", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  authStatus() {
    return this.req<AuthStatus>("/auth/status");
  }

  authBootstrap() {
    return this.req<AuthBootstrap>("/auth/bootstrap");
  }

  loginApp(input: { email: string; password: string }) {
    return this.req<AppLoginResponse>("/auth/app-login", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  authAzure(input: {
    sprint_url: string;
    pat: string;
    organization?: string;
    project?: string;
    team?: string;
  }) {
    return this.req<AuthResponse>("/auth/azuredevops", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  listSprints(provider: Provider, opts: { board_id?: string; team_path?: string } = {}) {
    return this.req<SprintSummary[]>("/sprints", {
      query: {
        provider,
        board_id: opts.board_id,
        team_path: opts.team_path,
      },
    });
  }

  getSprint(
    sprintId: string,
    provider: Provider,
    opts: {
      scope?: "mine";
      user_email?: string;
      include_archived?: boolean;
    } = {},
  ) {
    return this.req<SprintDetail>(`/sprints/${encodeURIComponent(sprintId)}`, {
      query: {
        provider,
        scope: opts.scope,
        user_email: opts.user_email,
        include_archived: opts.include_archived ? "true" : undefined,
      },
    });
  }

  moveSprintItem(sprintId: string, itemKey: string, input: MoveSprintItemRequest) {
    return this.req<SprintItem>(
      `/sprints/${encodeURIComponent(sprintId)}/items/${encodeURIComponent(itemKey)}/move`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
    );
  }

  archiveSprintItem(sprintId: string, itemKey: string, input: ArchiveSprintItemRequest) {
    return this.req<SprintItem>(
      `/sprints/${encodeURIComponent(sprintId)}/items/${encodeURIComponent(itemKey)}/archive`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
    );
  }

  importSprints(provider: Provider, opts: { board_id?: string; team_path?: string } = {}) {
    return this.req<ImportSprintsResponse>("/sprints/import", {
      method: "POST",
      body: JSON.stringify({ provider, ...opts }),
    });
  }

  importStatus(jobId: string) {
    return this.req<ImportStatus>(`/sprints/import/${encodeURIComponent(jobId)}`);
  }

  startRun(input: StartRunRequest) {
    return this.req<StartRunResponse>("/runs", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  previewRun(input: StartRunRequest) {
    return this.req<RoutePreviewResponse>("/runs/preview", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  getRun(runId: string) {
    return this.req<RunStatus>(`/runs/${encodeURIComponent(runId)}`);
  }

  previewControlPlaneRun(input: StartRunRequest) {
    return this.req<RoutePreviewResponse>("/api/runs/preview", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  listControlPlaneRuns() {
    return this.req<ControlPlaneRunSummary[]>("/api/runs");
  }

  getControlPlaneRun(runId: string) {
    return this.req<ControlPlaneRunDetail>(`/api/runs/${encodeURIComponent(runId)}`);
  }

  pauseRun(runId: string, input: ActionRequest = {}) {
    return this.req<ActionResponse>(`/api/runs/${encodeURIComponent(runId)}/actions/pause`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  resumeRun(runId: string, input: ActionRequest = {}) {
    return this.req<ActionResponse>(`/api/runs/${encodeURIComponent(runId)}/actions/resume`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  cancelRun(runId: string, input: ActionRequest = {}) {
    return this.req<ActionResponse>(`/api/runs/${encodeURIComponent(runId)}/actions/cancel`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  rerunRun(runId: string, input: ActionRequest = {}) {
    return this.req<ActionResponse>(`/api/runs/${encodeURIComponent(runId)}/actions/rerun`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  approveRun(runId: string, input: ActionRequest = {}) {
    return this.req<ActionResponse>(`/api/runs/${encodeURIComponent(runId)}/actions/approve`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  getRunAudit(runId: string) {
    return this.req<AuditQueryResponse>(`/api/runs/${encodeURIComponent(runId)}/audit`);
  }

  getRunDashboard(runId: string) {
    return this.req<DashboardSnapshot>(`/runs/${encodeURIComponent(runId)}/dashboard`);
  }

  getValidationDashboard() {
    return this.req<ValidationDashboardResponse>("/api/dashboard/validations");
  }

  getAgentDashboard() {
    return this.req<AgentDashboardResponse>("/api/dashboard/agents");
  }

  getTupleDashboard() {
    return this.req<TupleDashboardResponse>("/api/dashboard/tuples");
  }

  getYoolDashboard() {
    return this.req<YoolDashboardResponse>("/api/dashboard/yools");
  }

  evidenceUrl(runId: string, name: string) {
    return `${this.baseUrl}/runs/${encodeURIComponent(runId)}/evidence/${encodeURIComponent(name)}`;
  }

  eventsUrl(runId: string) {
    return `${this.baseUrl}/runs/${encodeURIComponent(runId)}/events`;
  }

  eventsStreamUrl(runId: string) {
    return `${this.baseUrl}/runs/${encodeURIComponent(runId)}/events/stream`;
  }
}

export class ApiError extends Error {
  readonly detail: string | null;

  constructor(
    public status: number,
    public statusText: string,
    public body: ResponseBody,
  ) {
    const detail = extractBackendMessage(body);
    const statusLine = [String(status), statusText].filter(Boolean).join(" ");
    super(detail ? `${detail} (${statusLine})` : statusLine || "Request failed");
    this.name = "ApiError";
    this.detail = detail;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export const getApiErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try {
    return JSON.stringify(error);
  } catch {
    return "Unexpected error.";
  }
};

export const getApiErrorStatusLine = (error: unknown): string | null => {
  if (!(error instanceof ApiError)) return null;
  return [String(error.status), error.statusText].filter(Boolean).join(" ") || null;
};
