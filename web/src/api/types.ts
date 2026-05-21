export type Provider = "jira" | "azuredevops";
export type RunMode = "all" | "mine" | "selected";
export type ColumnKey =
  | "backlog"
  | "planning"
  | "programming"
  | "testing"
  | "review"
  | "awaiting_deploy"
  | "blocked";

export type ApiErrorPayload = {
  detail?: unknown;
  message?: unknown;
  error?: unknown;
  [key: string]: unknown;
};

export type ProjectMode = "single" | "portfolio";

export type RepositoryRole =
  | "frontend"
  | "backend"
  | "fullstack"
  | "mobile"
  | "infra"
  | "docs"
  | "shared"
  | "other";

export type RepositoryRegistration = {
  id: string;
  name: string;
  repoPath: string;
  role: RepositoryRole;
  project: string;
  validationCommands: string[];
};

export type ProjectSetup = {
  mode: ProjectMode;
  branchPattern: string;
  commitPattern: string;
  deployTargetBranch: string;
  repositories: RepositoryRegistration[];
  updatedAt?: string | null;
};

export type CurrentSprint = {
  provider: Provider;
  sprintId: string;
  sprintName: string;
  sprintUrl?: string | null;
  portfolioName?: string | null;
  projectName?: string | null;
  teamName?: string | null;
};

export type Health = {
  ok: boolean;
  version: string;
  providers_configured: { jira: boolean; azuredevops: boolean };
};

export type VersionCheckResponse = {
  current_version: string;
  latest_version?: string | null;
  update_available: boolean;
  status: "ok" | "unavailable";
  source: string;
  source_url: string;
  message: string;
};

export type AuthResponse = {
  provider: Provider;
  account: string;
  ok: boolean;
  user_display_name?: string | null;
  ado_team_path?: string | null;
  ado_iteration_path?: string | null;
  fallback_used?: boolean;
  capture_transport?: string | null;
};

export type AppLoginResponse = {
  ok: boolean;
  email: string;
  active: boolean;
  display_name?: string | null;
  permissions?: {
    can_run_all_backlog?: boolean;
  } | null;
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
      user_email?: string | null;
      team_path?: string | null;
      iteration_path?: string | null;
    };
    github: { configured: boolean };
  };
};

export type AuthBootstrap = AuthStatus & {
  operator_token: string;
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
  description?: string | null;
  revision?: string | number | null;
  assignee?: string | null;
  assignee_email?: string | null;
  story_points?: number | null;
  parent_key?: string | null;
  labels: string[];
  links: Array<{
    type: string;
    target_key?: string | null;
    target_url?: string | null;
  }>;
  comments: Array<{
    author?: string | null;
    body?: string | null;
    created_at?: string | null;
  }>;
  attachments: Array<{
    filename?: string | null;
    url?: string | null;
    mime_type?: string | null;
    size_bytes?: number | null;
  }>;
  acceptance_criteria?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  source_url?: string | null;
  board_column?: ColumnKey | null;
  board_status?: string | null;
  board_updated_at?: string | null;
  board_updated_by?: string | null;
  archived: boolean;
  history: Array<{
    action?: string | null;
    actor_email?: string | null;
    observed_at?: string | null;
    from_column?: ColumnKey | null;
    to_column?: ColumnKey | null;
    archived?: boolean | null;
    note?: string | null;
  }>;
};

export type SprintDetail = {
  sprint: SprintSummary;
  items: SprintItem[];
  archived_count: number;
};

export type MoveSprintItemRequest = {
  provider: Provider;
  target_column: ColumnKey;
  actor_email?: string | null;
  note?: string | null;
};

export type ArchiveSprintItemRequest = {
  provider: Provider;
  actor_email?: string | null;
  archived: boolean;
  note?: string | null;
};

export type StartRunRequest = {
  provider: Provider;
  sprint_id: string;
  mode: RunMode;
  item_keys?: string[];
  repo_path?: string | null;
  workspace_path?: string | null;
  project_setup?: ProjectSetup | null;
  dry_run?: boolean;
  resume?: boolean;
  no_cache?: boolean;
  autonomy_level?: string;
  run_id?: string | null;
};

export type StartRunResponse = { run_id: string; status: "started" };

export type RouteConfidence = "high" | "medium" | "low";

export type RoutePreviewSummary = {
  text: string;
  task_count: number;
  planned_delivery_count: number;
  selected_repo_count: number;
  low_confidence_count: number;
  warning_count: number;
};

export type RoutePreviewTaskUnderstanding = {
  item_key: string;
  item_type: string;
  title: string;
  status: string;
  scopes: string[];
  scope_source: "label" | "inferred" | "none";
  relationship: string;
  selected_repos: string[];
  confidence?: RouteConfidence | null;
  reasons: string[];
};

export type RoutePreviewSelectedRepo = {
  item_key: string;
  item_type: string;
  title: string;
  repo: string;
  repo_name: string;
  repo_role?: string | null;
  branch: string;
  target_branch: string;
  confidence: RouteConfidence;
  reasons: string[];
  relationship: string;
  worktree_path?: string | null;
  validation_template?: string | null;
  validation_commands: string[];
};

export type RoutePreviewLowConfidenceItem = {
  item_key: string;
  title: string;
  repo?: string | null;
  repo_name?: string | null;
  confidence: RouteConfidence;
  reason: string;
  recommended_action: string;
};

export type RoutePreviewResponse = {
  schema_version: string;
  provider: Provider;
  sprint_id: string;
  sprint_name: string;
  mode: RunMode;
  item_keys: string[];
  autonomy_level: string;
  side_effects: Record<string, boolean>;
  summary: RoutePreviewSummary;
  task_understanding: RoutePreviewTaskUnderstanding[];
  selected_repos: RoutePreviewSelectedRepo[];
  low_confidence_items: RoutePreviewLowConfidenceItem[];
  warnings: string[];
};

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
  item_keys: string[];
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

export type ActionRequest = {
  operator?: string;
  confirmed?: boolean;
  payload?: Record<string, unknown>;
};

export type ActionResponse = {
  run_id: string;
  action: string;
  result: string;
  detail: Record<string, unknown>;
};

export type AuditEntry = {
  operator: string;
  action: string;
  run_id: string;
  timestamp?: string | null;
  result: string;
  detail: Record<string, unknown>;
};

export type AuditQueryResponse = {
  entries: AuditEntry[];
  total: number;
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

export type AgentDashboardEntry = {
  key: string;
  name: string;
  runtime: string;
  capabilities: string[];
  active_runs: number;
  notes: string[];
};

export type AgentDashboardResponse = {
  agents: AgentDashboardEntry[];
  total_active_runs: number;
};

export type TupleDashboardEntry = {
  run_id: string;
  state: string;
  sprint_id: string;
  provider: string;
  started_at?: string | null;
  finished_at?: string | null;
  failed: boolean;
  event_count: number;
  last_event_type?: string | null;
  progress?: number | null;
};

export type TupleDashboardResponse = {
  tuples: TupleDashboardEntry[];
  total_runs: number;
  active_runs: number;
  failed_runs: number;
};

export type YoolDashboardEntry = {
  yool_id: string;
  total_invocations: number;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate: number;
  total_retries: number;
  total_cost_usd: number;
  total_duration_ms: number;
  avg_duration_ms: number;
  last_status: string;
  errors: string[];
};

export type YoolDashboardResponse = {
  yools: YoolDashboardEntry[];
  cache_stats: Record<string, unknown>;
  registered_contracts: number;
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
