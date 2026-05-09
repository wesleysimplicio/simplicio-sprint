import type {
  AuthResponse,
  Health,
  ImportSprintsResponse,
  ImportStatus,
  Provider,
  RunStatus,
  SprintDetail,
  SprintSummary,
  StartRunRequest,
  StartRunResponse,
} from "./types";

export class ApiClient {
  constructor(private baseUrl: string) {}

  setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, "");
  }

  getBaseUrl() {
    return this.baseUrl;
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
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new ApiError(resp.status, text || resp.statusText);
    }
    return (await resp.json()) as T;
  }

  health() {
    return this.req<Health>("/health");
  }

  authJira(input: { base_url: string; email: string; api_token: string }) {
    return this.req<AuthResponse>("/auth/jira", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  authAzure(input: { organization: string; project: string; pat: string }) {
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

  getSprint(sprintId: string, provider: Provider, scope?: "mine") {
    return this.req<SprintDetail>(`/sprints/${encodeURIComponent(sprintId)}`, {
      query: { provider, scope },
    });
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

  getRun(runId: string) {
    return this.req<RunStatus>(`/runs/${encodeURIComponent(runId)}`);
  }

  evidenceUrl(runId: string, name: string) {
    return `${this.baseUrl}/runs/${encodeURIComponent(runId)}/evidence/${encodeURIComponent(name)}`;
  }

  eventsUrl(runId: string) {
    return `${this.baseUrl}/runs/${encodeURIComponent(runId)}/events`;
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}
