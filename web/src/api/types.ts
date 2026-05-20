export type Provider = "jira" | "azuredevops";
export type RunMode = "all" | "mine" | "selected";

export type Health = {
  ok: boolean;
  version: string;
  providers_configured: { jira: boolean; azuredevops: boolean };
};

export type AuthResponse = {
  provider: Provider;
  account: string;
  ok: boolean;
  user_display_name?: string | null;
  ado_team_path?: string | null;
  ado_iteration_path?: string | null;
};

export type AuthStatus = {
  default_provider?: Provider | null;
  jira_configured: boolean;
  azuredevops_configured: boolean;
  providers: {
    jira: { configured: boolean; account?: string | null };
    azuredevops: {
      configured: boolean;
      account?: string | null;
      team_path?: string | null;
      iteration_path?: string | null;
    };
    github: { configured: boolean };
  };
};

export type SprintSummary = {
  id: string;
  name: string;
  state: string;
  provider: Provider;
  start_date?: string | null;
  end_date?: string | null;
  item_count?: number | null;
  goal?: string | null;
};

export type SprintItem = {
  id: string;
  key: string;
  type: string;
  title: string;
  status: string;
  assignee?: string | null;
  assignee_email?: string | null;
  story_points?: number | null;
};

export type SprintDetail = {
  sprint: SprintSummary;
  items: SprintItem[];
};

export type StartRunRequest = {
  provider: Provider;
  sprint_id: string;
  mode: RunMode;
  item_keys?: string[];
  repo_path?: string | null;
  workspace_path?: string | null;
};

export type StartRunResponse = { run_id: string; status: "started" };

export type RunStatus = {
  run_id: string;
  state: "queued" | "running" | "done" | "failed";
  sprint_id: string;
  provider: Provider;
  started_at?: string | null;
  finished_at?: string | null;
  summary?: string | null;
  pr_url?: string | null;
  failed: boolean;
  last_step?: number | null;
};

export type DashboardEvidence = {
  name: string;
  path: string;
};

export type DashboardSnapshot = {
  run: RunStatus;
  evidence: DashboardEvidence[];
  summary?: string | null;
  pr_url?: string | null;
  blockers: string[];
};

export type ControlPlaneRunSummary = {
  run_id: string;
  state: string;
  sprint_id: string;
  provider: string;
  autonomy_level: string;
  task?: string | null;
  branch?: string | null;
  readiness_score?: number | null;
  readiness_verdict?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  summary?: string | null;
  pr_url?: string | null;
  failed: boolean;
  last_step?: number | null;
  progress?: number | null;
};

export type QualityGateResponse = {
  run_id: string;
  verdict: string;
  checks: Array<{
    check_name: string;
    passed: boolean;
    details: string;
    severity: string;
  }>;
  reasons: string[];
  created_at?: string | null;
};

export type EvidenceBundleResponse = {
  run_id: string;
  items: Array<{
    type: string;
    path: string;
    label: string;
    iteration?: number | null;
    observed_at?: string | null;
  }>;
  total_items: number;
  finalized: boolean;
  created_at?: string | null;
};

export type ControlPlaneRunDetail = {
  run: ControlPlaneRunSummary;
  quality_gate?: QualityGateResponse | null;
  evidence?: EvidenceBundleResponse | null;
  logs: string[];
  timeline: Array<Record<string, unknown>>;
};

export type ValidationLane = {
  lane: string;
  status: string;
  last_run_id?: string | null;
  last_result?: string | null;
  events_count: number;
  errors: string[];
};

export type ValidationDashboardResponse = {
  lanes: ValidationLane[];
  total_events: number;
};

export type RunEvent = {
  type:
    | "step"
    | "log"
    | "evidence"
    | "loop"
    | "regression"
    | "summary"
    | "done"
    | "error";
  run_id: string;
  step?: number;
  name?: string;
  status?: string;
  message?: string;
  evidence_path?: string;
  evidence_label?: string;
  progress?: number;
  summary?: string;
  pr_url?: string;
  failed?: boolean;
  iteration?: number;
  max_iterations?: number;
  failing_tests?: string[];
};

export type ImportSprintsResponse = { job_id: string; started: boolean };

export type ImportStatus = {
  state: "running" | "done" | "failed";
  fetched: number;
  total: number | null;
  error?: string;
};
