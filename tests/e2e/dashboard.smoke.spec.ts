import { expect, test, type Page, type Route } from '@playwright/test';

const baseUrl = process.env.BASE_URL;
const SESSION_STORAGE_KEY = 'sendsprint.session.v1';
const SUPPORT_STORAGE_KEY = 'sendsprint.support-center.v1';
const LOCAL_API_STORAGE_KEY = 'sendsprint.local-api.v1';
const ONE_BY_ONE_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6i0AAAAASUVORK5CYII=',
  'base64',
);

type MockState = {
  operatorToken: string;
  health: {
    ok: boolean;
    version: string;
    providers_configured: { jira: boolean; azuredevops: boolean };
  };
  authStatus: {
    default_provider: 'jira' | 'azuredevops' | null;
    jira_configured: boolean;
    azuredevops_configured: boolean;
    providers: {
      jira: { configured: boolean; account: string | null };
      azuredevops: {
        configured: boolean;
        account: string | null;
        user_email?: string | null;
        team_path: string | null;
        iteration_path: string | null;
      };
      github: { configured: boolean };
    };
  };
  appUser: {
    ok: boolean;
    email: string;
    active: boolean;
    display_name: string;
    permissions: { can_run_all_backlog: boolean };
  };
  sprints: Array<{
    id: string;
    name: string;
    state: string;
    provider: 'jira' | 'azuredevops';
    start_date: string;
    end_date: string;
    item_count: number;
    goal: string;
  }>;
  items: Array<Record<string, unknown>>;
  runs: Array<Record<string, unknown>>;
  runDetails: Record<string, Record<string, unknown>>;
  runDashboards: Record<string, Record<string, unknown>>;
  validationDashboard: Record<string, unknown>;
  agentDashboard: Record<string, unknown>;
  tupleDashboard: Record<string, unknown>;
  yoolDashboard: Record<string, unknown>;
  versionCheck: Record<string, unknown>;
  azureAuthMode: 'direct' | 'sprints';
  jiraAuthMode: 'direct' | 'sprints';
  runCounter: number;
  importPollCount: number;
};

const createMockState = (): MockState => ({
  operatorToken: 'operator-token',
  health: {
    ok: true,
    version: '0.21.0',
    providers_configured: { jira: false, azuredevops: false },
  },
  authStatus: {
    default_provider: null,
    jira_configured: false,
    azuredevops_configured: false,
    providers: {
      jira: { configured: false, account: null },
      azuredevops: {
        configured: false,
        account: null,
        team_path: null,
        iteration_path: null,
      },
      github: { configured: true },
    },
  },
  appUser: {
    ok: true,
    email: 'operator@acme.com',
    active: true,
    display_name: 'Operator Local',
    permissions: { can_run_all_backlog: true },
  },
  sprints: [
    {
      id: 'Acme/Payments/Team Falcon/Sprint 7',
      name: 'Sprint 7 - Workspace Shell',
      state: 'active',
      provider: 'azuredevops',
      start_date: '2026-05-20T09:00:00Z',
      end_date: '2026-05-31T18:00:00Z',
      item_count: 3,
      goal: 'Fechar o shell operacional Console + Web',
    },
    {
      id: 'Acme/Payments/Team Falcon/Sprint 8',
      name: 'Sprint 8 - Governance',
      state: 'future',
      provider: 'azuredevops',
      start_date: '2026-06-01T09:00:00Z',
      end_date: '2026-06-14T18:00:00Z',
      item_count: 2,
      goal: 'Governanca e reports',
    },
  ],
  items: [
    {
      id: '1',
      key: 'AZ-101',
      type: 'Story',
      title: 'Implementar onboarding do SendSprint',
      status: 'To Do',
      description:
        '&lt;p&gt;Criar a jornada inicial com acentua&ccedil;&atilde;o, login e CTA Iniciar.&lt;/p&gt;',
      revision: '7',
      assignee: 'Operator Local',
      assignee_email: 'operator@acme.com',
      story_points: 5,
      parent_key: null,
      labels: ['onboarding', 'web'],
      links: [
        {
          type: 'parent',
          target_key: 'EPIC-7',
          target_url: 'https://dev.azure.com/acme/payments/_workitems/edit/7',
        },
      ],
      comments: [
        {
          author: 'PM',
          body: 'Precisamos alinhar a jornada com o storyboard de telas.',
          created_at: '2026-05-20T10:00:00Z',
        },
      ],
      attachments: [
        {
          filename: 'storyboard.png',
          url: 'https://example.invalid/storyboard.png',
          mime_type: 'image/png',
          size_bytes: 2048,
        },
      ],
      acceptance_criteria: 'Mostrar shell vazia, CTA Iniciar e provider picker.',
      created_at: '2026-05-20T09:00:00Z',
      updated_at: '2026-05-20T11:00:00Z',
      source_url: 'https://dev.azure.com/acme/payments/_workitems/edit/101',
      board_column: 'backlog',
      board_status: 'Backlog',
      board_updated_at: '2026-05-20T11:00:00Z',
      board_updated_by: 'operator@acme.com',
      archived: false,
      history: [],
    },
    {
      id: '2',
      key: 'AZ-102',
      type: 'Task',
      title: 'Conectar fallback do Azure DevOps',
      status: 'To Do',
      description: 'Ligar 401 ao fallback Playwright e browser agents.',
      revision: '3',
      assignee: 'Operator Local',
      assignee_email: 'operator@acme.com',
      story_points: 3,
      parent_key: 'AZ-101',
      labels: ['azure', 'fallback'],
      links: [],
      comments: [],
      attachments: [],
      acceptance_criteria: 'Ao receber 401, o backend deve tentar browser capture.',
      created_at: '2026-05-20T09:15:00Z',
      updated_at: '2026-05-20T11:15:00Z',
      source_url: 'https://dev.azure.com/acme/payments/_workitems/edit/102',
      board_column: 'backlog',
      board_status: 'Backlog',
      board_updated_at: '2026-05-20T11:15:00Z',
      board_updated_by: 'operator@acme.com',
      archived: false,
      history: [],
    },
    {
      id: '3',
      key: 'AZ-103',
      type: 'Bug',
      title: 'Ajustar card de resultados',
      status: 'To Do',
      description: 'Item de outro colaborador que nao deve aparecer em scope mine.',
      revision: '1',
      assignee: 'Teammate',
      assignee_email: 'teammate@acme.com',
      story_points: 2,
      parent_key: null,
      labels: ['result'],
      links: [],
      comments: [],
      attachments: [],
      acceptance_criteria: 'Exibir PR, quality gate e handoff.',
      created_at: '2026-05-20T09:30:00Z',
      updated_at: '2026-05-20T11:30:00Z',
      source_url: 'https://dev.azure.com/acme/payments/_workitems/edit/103',
      board_column: 'backlog',
      board_status: 'Backlog',
      board_updated_at: '2026-05-20T11:30:00Z',
      board_updated_by: 'teammate@acme.com',
      archived: false,
      history: [],
    },
  ],
  runs: [
    {
      run_id: 'run-done-100',
      state: 'done',
      sprint_id: 'Acme/Payments/Team Falcon/Sprint 7',
      provider: 'azuredevops',
      autonomy_level: 'standard',
      item_keys: ['AZ-110'],
      task: 'Fechar dashboard do gerente',
      branch: 'feature/AZ-110-manager-dashboard',
      readiness_score: 0.97,
      readiness_verdict: 'ready_for_review',
      started_at: '2026-05-20T12:00:00Z',
      finished_at: '2026-05-20T12:10:00Z',
      summary: 'Dashboard do gerente entregue',
      pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/999',
      failed: false,
      last_step: 10,
      progress: 1,
    },
  ],
  runDetails: {
    'run-done-100': {
      run: {
        run_id: 'run-done-100',
        state: 'done',
        sprint_id: 'Acme/Payments/Team Falcon/Sprint 7',
        provider: 'azuredevops',
        autonomy_level: 'standard',
        item_keys: ['AZ-110'],
        task: 'Fechar dashboard do gerente',
        branch: 'feature/AZ-110-manager-dashboard',
        readiness_score: 0.97,
        readiness_verdict: 'ready_for_review',
        started_at: '2026-05-20T12:00:00Z',
        finished_at: '2026-05-20T12:10:00Z',
        summary: 'Dashboard do gerente entregue',
        pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/999',
        failed: false,
        last_step: 10,
        progress: 1,
      },
      quality_gate: {
        run_id: 'run-done-100',
        verdict: 'ready_for_review',
        checks: [
          {
            check_name: 'lint',
            passed: true,
            details: 'ruff and typecheck green',
            severity: 'info',
          },
        ],
        reasons: ['Fluxo validado pela esteira local.'],
        created_at: '2026-05-20T12:10:00Z',
      },
      evidence: {
        run_id: 'run-done-100',
        items: [
          {
            type: 'screenshot',
            path: 'evidence/manager-dashboard.png',
            label: 'Manager dashboard',
            iteration: 1,
            observed_at: '2026-05-20T12:08:00Z',
          },
        ],
        total_items: 1,
        finalized: true,
        created_at: '2026-05-20T12:10:00Z',
      },
      logs: ['manager dashboard pronto'],
      timeline: [{ step: 10, status: 'done' }],
    },
  },
  runDashboards: {
    'run-done-100': {
      run: {
        run_id: 'run-done-100',
        state: 'done',
        sprint_id: 'Acme/Payments/Team Falcon/Sprint 7',
        provider: 'azuredevops',
        started_at: '2026-05-20T12:00:00Z',
        finished_at: '2026-05-20T12:10:00Z',
        summary: 'Dashboard do gerente entregue',
        pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/999',
        failed: false,
        last_step: 10,
      },
      evidence: [{ name: 'manager-dashboard.png', path: 'evidence/manager-dashboard.png' }],
      summary: 'Dashboard do gerente entregue',
      pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/999',
      blockers: [],
    },
  },
  validationDashboard: {
    lanes: [
      {
        lane: 'web',
        status: 'ok',
        last_run_id: 'run-done-100',
        last_result: 'all green',
        events_count: 4,
        errors: [],
      },
      {
        lane: 'backend',
        status: 'failed',
        last_run_id: 'run-done-100',
        last_result: 'needs attention',
        events_count: 2,
        errors: ['one flaky endpoint'],
      },
    ],
    total_events: 6,
  },
  agentDashboard: {
    agents: [
      {
        key: 'planner',
        name: 'Planner',
        runtime: 'codex',
        capabilities: ['plan', 'route'],
        active_runs: 1,
        notes: [],
      },
      {
        key: 'tester',
        name: 'Tester',
        runtime: 'playwright',
        capabilities: ['e2e', 'screenshots'],
        active_runs: 1,
        notes: [],
      },
    ],
    total_active_runs: 2,
  },
  tupleDashboard: {
    tuples: [],
    total_runs: 7,
    active_runs: 1,
    failed_runs: 1,
  },
  yoolDashboard: {
    yools: [
      {
        yool_id: 'spawn_agent',
        total_invocations: 42,
        cache_hits: 10,
        cache_misses: 32,
        cache_hit_rate: 0.24,
        total_retries: 3,
        total_cost_usd: 0,
        total_duration_ms: 4200,
        avg_duration_ms: 100,
        last_status: 'ok',
        errors: [],
      },
    ],
    cache_stats: {},
    registered_contracts: 12,
  },
  versionCheck: {
    current_version: '0.21.0',
    latest_version: '0.21.1',
    update_available: true,
    status: 'ok',
    source: 'pypi',
    source_url: 'https://pypi.org/project/sendsprint/',
    message: 'Update available',
  },
  azureAuthMode: 'direct',
  jiraAuthMode: 'direct',
  runCounter: 200,
  importPollCount: 0,
});

const makeSession = (overrides: Record<string, unknown> = {}) => ({
  backendUrl: 'http://localhost:8765',
  operatorToken: 'operator-token',
  appUser: {
    email: 'operator@acme.com',
    active: true,
    displayName: 'Operator Local',
    permissions: {
      canRunAllBacklog: true,
    },
  },
  provider: null,
  account: null,
  jiraBoardId: null,
  adoTeamPath: null,
  currentSprint: null,
  projectSetup: {
    mode: 'single',
    repositories: [],
    updatedAt: null,
  },
  ...overrides,
});

const makeSupportTickets = () => [
  {
    id: 'support-existing',
    category: 'bug',
    status: 'triaged',
    title: 'Erro no fallback do Azure',
    description: 'A captura caiu para o browser agent errado.',
    linkedRunId: 'run-done-100',
    createdBy: 'operator@acme.com',
    createdAt: '2026-05-20T13:00:00Z',
    updatedAt: '2026-05-20T13:30:00Z',
    backlogReason: 'Precisa de hardening no fallback chain.',
    diagnostics: {
      provider: 'azuredevops',
      sprintId: 'Acme/Payments/Team Falcon/Sprint 7',
      sprintName: 'Sprint 7 - Workspace Shell',
      repoCount: 1,
      runCount: 2,
    },
  },
];

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

const installBrowserGuards = async (page: Page) => {
  await page.addInitScript(([sessionKey, supportKey, localApiKey]) => {
    window.localStorage.removeItem(sessionKey);
    window.localStorage.removeItem(supportKey);
    window.localStorage.removeItem(localApiKey);
    window.alert = () => undefined;
    window.confirm = () => true;
  }, [SESSION_STORAGE_KEY, SUPPORT_STORAGE_KEY, LOCAL_API_STORAGE_KEY] as const);
};

const seedSession = async (page: Page, session: Record<string, unknown>) => {
  await page.addInitScript(
    ([storageKey, payload]) => {
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
    },
    [SESSION_STORAGE_KEY, session] as const,
  );
};

const seedSupportTickets = async (page: Page, tickets: Record<string, unknown>[]) => {
  await page.addInitScript(
    ([storageKey, payload]) => {
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
    },
    [SUPPORT_STORAGE_KEY, tickets] as const,
  );
};

const installMockEventSource = async (
  page: Page,
  streams: Record<string, Array<Record<string, unknown>>>,
) => {
  await page.addInitScript((streamMap) => {
    class MockEventSource {
      url: string;
      onopen: (() => void) | null = null;
      onerror: ((error: unknown) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;

      constructor(url: string) {
        this.url = url;
        const pathname = new URL(url, window.location.origin).pathname;
        const events = (streamMap as Record<string, Array<Record<string, unknown>>>)[pathname] ?? [];
        setTimeout(() => {
          this.onopen?.();
          events.forEach((event, index) => {
            setTimeout(() => {
              this.onmessage?.({ data: JSON.stringify(event) } as MessageEvent<string>);
            }, 20 * (index + 1));
          });
        }, 0);
      }

      close() {}
      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() {
        return true;
      }
    }

    Object.defineProperty(window, 'EventSource', {
      configurable: true,
      writable: true,
      value: MockEventSource,
    });
  }, streams);
};

const installMockBackend = async (page: Page, state: MockState) => {
  await page.route(/\/health$/, async (route) => {
    await fulfillJson(route, state.health);
  });

  await page.route(/\/auth\/bootstrap$/, async (route) => {
    await fulfillJson(route, {
      ...state.authStatus,
      operator_token: state.operatorToken,
    });
  });

  await page.route(/\/auth\/status$/, async (route) => {
    await fulfillJson(route, state.authStatus);
  });

  await page.route(/\/auth\/app-login$/, async (route) => {
    await fulfillJson(route, state.appUser);
  });

  await page.route(/\/auth\/azuredevops$/, async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}') as { user_email?: string };
    const userEmail = payload.user_email ?? state.appUser.email;
    state.authStatus.default_provider = 'azuredevops';
    state.authStatus.azuredevops_configured = true;
    state.authStatus.providers.azuredevops = {
      configured: true,
      account: 'Acme/Payments',
      user_email: userEmail,
      team_path: 'Acme/Payments/Team Falcon',
      iteration_path:
        state.azureAuthMode === 'direct' ? 'Acme/Payments/Team Falcon/Sprint 7' : null,
    };
    state.health.providers_configured.azuredevops = true;

    await fulfillJson(route, {
      provider: 'azuredevops',
      account: 'Acme/Payments',
      ok: true,
      user_display_name: userEmail,
      ado_team_path: 'Acme/Payments/Team Falcon',
      ado_iteration_path:
        state.azureAuthMode === 'direct' ? 'Acme/Payments/Team Falcon/Sprint 7' : null,
      fallback_used: true,
      capture_transport: 'playwright',
    });
  });

  await page.route(/\/auth\/jira$/, async (route) => {
    state.authStatus.default_provider = 'jira';
    state.authStatus.jira_configured = true;
    state.authStatus.providers.jira = {
      configured: true,
      account: state.appUser.email,
    };
    state.health.providers_configured.jira = true;

    await fulfillJson(route, {
      provider: 'jira',
      account: state.appUser.email,
      ok: true,
      user_display_name: state.appUser.display_name,
      fallback_used: state.jiraAuthMode === 'direct',
      capture_transport: state.jiraAuthMode === 'direct' ? 'playwright' : null,
    });
  });

  await page.route(/\/sprints\/import$/, async (route) => {
    state.importPollCount = 0;
    await fulfillJson(route, { job_id: 'job-import-1', started: true });
  });

  await page.route(/\/sprints\/import\/[^/]+$/, async (route) => {
    state.importPollCount += 1;
    if (state.importPollCount === 1) {
      await fulfillJson(route, { state: 'running', fetched: 1, total: 2 });
      return;
    }
    await fulfillJson(route, { state: 'done', fetched: 2, total: 2 });
  });

  await page.route(/\/sprints(\?.*)?$/, async (route) => {
    await fulfillJson(route, state.sprints);
  });

  await page.route(/\/sprints\/[^/]+$/, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/import')) {
      await route.fallback();
      return;
    }
    const requestedId = decodeURIComponent(url.pathname.split('/').pop() ?? state.sprints[0].id);
    const sprintMeta = state.sprints.find((entry) => entry.id === requestedId) ?? {
      ...state.sprints[0],
      id: requestedId,
      name: requestedId.split('/').pop() ?? state.sprints[0].name,
    };
    const includeArchived = url.searchParams.get('include_archived') === 'true';
    const scope = url.searchParams.get('scope');
    const userEmail = url.searchParams.get('user_email');
    const items = clone(state.items).filter((item) => {
      if (!includeArchived && item.archived) return false;
      if (scope === 'mine' && userEmail) return item.assignee_email === userEmail;
      return true;
    });
    await fulfillJson(route, {
      sprint: sprintMeta,
      items,
      archived_count: state.items.filter((item) => item.archived).length,
    });
  });

  await page.route(/\/sprints\/[^/]+\/items\/[^/]+\/move$/, async (route) => {
    const url = new URL(route.request().url());
    const itemKey = decodeURIComponent(url.pathname.split('/')[4] ?? '');
    const payload = route.request().postDataJSON() as {
      target_column: string;
      actor_email?: string | null;
      note?: string | null;
    };
    const item = state.items.find((entry) => entry.key === itemKey);
    if (!item) throw new Error(`missing item ${itemKey}`);
    const previous = item.board_column;
    item.board_column = payload.target_column;
    item.board_status = capitalize(payload.target_column.replace('_', ' '));
    item.board_updated_at = new Date().toISOString();
    item.board_updated_by = payload.actor_email ?? 'operator@acme.com';
    item.history.push({
      action: 'move',
      actor_email: payload.actor_email ?? 'operator@acme.com',
      observed_at: item.board_updated_at,
      from_column: previous,
      to_column: payload.target_column,
      archived: false,
      note: payload.note ?? null,
    });
    await fulfillJson(route, clone(item));
  });

  await page.route(/\/sprints\/[^/]+\/items\/[^/]+\/archive$/, async (route) => {
    const url = new URL(route.request().url());
    const itemKey = decodeURIComponent(url.pathname.split('/')[4] ?? '');
    const payload = route.request().postDataJSON() as {
      archived: boolean;
      actor_email?: string | null;
      note?: string | null;
    };
    const item = state.items.find((entry) => entry.key === itemKey);
    if (!item) throw new Error(`missing item ${itemKey}`);
    item.archived = payload.archived;
    item.board_updated_at = new Date().toISOString();
    item.board_updated_by = payload.actor_email ?? 'operator@acme.com';
    item.history.push({
      action: payload.archived ? 'archive' : 'restore',
      actor_email: payload.actor_email ?? 'operator@acme.com',
      observed_at: item.board_updated_at,
      from_column: item.board_column,
      to_column: item.board_column,
      archived: payload.archived,
      note: payload.note ?? null,
    });
    await fulfillJson(route, clone(item));
  });

  await page.route(/\/api\/runs$/, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await fulfillJson(route, state.runs);
  });

  await page.route(/\/api\/runs\/[^/]+$/, async (route) => {
    const runId = decodeURIComponent(new URL(route.request().url()).pathname.split('/').pop() ?? '');
    await fulfillJson(route, state.runDetails[runId] ?? state.runDetails['run-done-100']);
  });

  await page.route(/\/api\/dashboard\/validations$/, async (route) => {
    await fulfillJson(route, state.validationDashboard);
  });

  await page.route(/\/api\/dashboard\/agents$/, async (route) => {
    await fulfillJson(route, state.agentDashboard);
  });

  await page.route(/\/api\/dashboard\/tuples$/, async (route) => {
    await fulfillJson(route, state.tupleDashboard);
  });

  await page.route(/\/api\/dashboard\/yools$/, async (route) => {
    await fulfillJson(route, state.yoolDashboard);
  });

  await page.route(/\/version\/check$/, async (route) => {
    await fulfillJson(route, state.versionCheck);
  });

  await page.route(/\/runs$/, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.startsWith('/api/')) {
      await route.fallback();
      return;
    }
    const payload = route.request().postDataJSON() as {
      provider: 'jira' | 'azuredevops';
      sprint_id: string;
      item_keys?: string[];
    } | null;
    if (!payload) {
      await route.fallback();
      return;
    }
    const itemKeys = payload.item_keys?.length ? payload.item_keys : state.items.map((item) => String(item.key));
    const runId = `run-live-${state.runCounter++}`;
    const summary = {
      run_id: runId,
      state: 'running',
      sprint_id: payload.sprint_id,
      provider: payload.provider,
      autonomy_level: 'standard',
      item_keys: itemKeys,
      task: `Dispatch ${itemKeys.join(', ')}`,
      branch: `feature/${itemKeys[0].toLowerCase()}`,
      readiness_score: 0.64,
      readiness_verdict: 'needs_human_approval',
      started_at: '2026-05-20T14:00:00Z',
      finished_at: null,
      summary: 'Planejamento iniciado',
      pr_url: null,
      failed: false,
      last_step: 2,
      progress: 0.35,
    };
    state.runs.unshift(summary);
    state.runDetails[runId] = {
      run: summary,
      quality_gate: {
        run_id: runId,
        verdict: 'needs_human_approval',
        checks: [
          {
            check_name: 'mapper',
            passed: true,
            details: 'workspace mapeado',
            severity: 'info',
          },
          {
            check_name: 'tests',
            passed: false,
            details: 'aguardando a rodada de testes',
            severity: 'warning',
          },
        ],
        reasons: ['A run ainda esta em progresso.'],
        created_at: '2026-05-20T14:01:00Z',
      },
      evidence: {
        run_id: runId,
        items: [
          {
            type: 'screenshot',
            path: `evidence/${runId}-board.png`,
            label: 'Board capture',
            iteration: 1,
            observed_at: '2026-05-20T14:02:00Z',
          },
        ],
        total_items: 1,
        finalized: false,
        created_at: '2026-05-20T14:02:00Z',
      },
      logs: ['mapper iniciado', 'planning em progresso'],
      timeline: [{ step: 2, status: 'running' }],
    };
    state.runDashboards[runId] = {
      run: {
        run_id: runId,
        state: 'running',
        sprint_id: payload.sprint_id,
        provider: payload.provider,
        started_at: '2026-05-20T14:00:00Z',
        finished_at: null,
        summary: 'Planejamento iniciado',
        pr_url: null,
        failed: false,
        last_step: 2,
      },
      evidence: [{ name: `${runId}-board.png`, path: `evidence/${runId}-board.png` }],
      summary: 'Planejamento iniciado',
      pr_url: null,
      blockers: [],
    };
    await fulfillJson(route, { run_id: runId, status: 'started' });
  });

  await page.route(/\/runs\/[^/]+$/, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.startsWith('/api/')) {
      await route.fallback();
      return;
    }
    const runId = decodeURIComponent(new URL(route.request().url()).pathname.split('/').pop() ?? '');
    const detail = state.runDetails[runId] ?? state.runDetails['run-done-100'];
    await fulfillJson(route, detail.run);
  });

  await page.route(/\/runs\/[^/]+\/dashboard$/, async (route) => {
    const runId = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[2] ?? '');
    await fulfillJson(route, state.runDashboards[runId] ?? state.runDashboards['run-done-100']);
  });

  await page.route(/\/runs\/[^/]+\/evidence\/[^/]+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: ONE_BY_ONE_PNG,
    });
  });
};

const fulfillJson = async (route: Route, payload: unknown) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
};

const capitalize = (value: string) =>
  value
    .split(' ')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');

test.describe('SendSprint web flows', () => {
  test.skip(!baseUrl, 'BASE_URL not set - skipping Playwright UI suite.');

  test('login, empty shell and provider picker stay reachable', async ({ page }) => {
    const state = createMockState();
    await installBrowserGuards(page);
    await installMockBackend(page, state);

    await page.goto('/');

    await expect(page.getByText(/LOGIN SENDSPRINT/i)).toBeVisible();
    await page.getByLabel(/Email/i).fill('operator@acme.com');
    await page.getByLabel(/Senha/i).fill('super-secret');
    await page.getByText(/^Entrar$/i).click();

    await expect(page.getByText(/Nenhuma sprint ativa no shell web ainda/i)).toBeVisible();
    await page.getByText(/^Iniciar$/i).first().click();

    await expect(page.getByText(/^Jira \/ Atlassian$/i)).toBeVisible();
    await expect(page.getByText(/^Azure DevOps$/i)).toBeVisible();
    await expect(page.getByText(/GitHub Projects/i)).toBeVisible();
    await expect(page.getByText(/Em breve/i)).toBeVisible();

    await page.getByText(/^Jira \/ Atlassian$/i).click();
    await expect(page.getByText(/Sobre o fallback/i)).toBeVisible();
  });

  test('login restores Azure DevOps context saved for the app user', async ({ page }) => {
    const state = createMockState();
    await installBrowserGuards(page);
    await seedSession(
      page,
      makeSession({
        operatorToken: null,
        appUser: null,
        provider: null,
        account: null,
        adoTeamPath: null,
        currentSprint: null,
        userProfiles: {
          'operator@acme.com': {
            provider: 'azuredevops',
            account: 'Acme/Payments',
            adoTeamPath: 'Acme/Payments/Team Falcon',
            currentSprint: {
              provider: 'azuredevops',
              sprintId: 'Acme/Payments/Team Falcon/Sprint 7',
              sprintName: 'Sprint 7 - Workspace Shell',
              sprintUrl: 'https://dev.azure.com/acme/payments/_sprints/taskboard/Team%20Falcon/Sprint%207',
              portfolioName: 'Acme',
              projectName: 'Payments',
              teamName: 'Team Falcon',
            },
            projectSetup: {
              mode: 'single',
              branchPattern: 'feature/{item_key}-{slug}',
              commitPattern: 'feat: {summary}',
              deployTargetBranch: 'dev',
              repositories: [
                {
                  id: 'repo-profile',
                  name: 'web-shell',
                  repoPath: 'C:/workspace/sendsprint-web',
                  role: 'fullstack',
                  project: 'Workspace Shell',
                  validationCommands: ['npm run typecheck'],
                },
              ],
              updatedAt: '2026-05-20T15:00:00Z',
            },
          },
        },
      }),
    );
    await installMockBackend(page, state);

    await page.goto('/');

    await expect(page.getByText(/LOGIN SENDSPRINT/i)).toBeVisible();
    await page.getByLabel(/Email/i).fill('operator@acme.com');
    await page.getByLabel(/Senha/i).fill('super-secret');
    await page.getByText(/^Entrar$/i).click();

    await expect(page.getByText(/Sprint 7 - Workspace Shell/i).first()).toBeVisible();
    await expect(page.getByText(/ACTIVE DELIVERY CONTEXT/i)).toBeVisible();
    await expect(page.getByText(/Conectar Azure DevOps/i)).not.toBeVisible();
  });

  test('local fallback keeps login, setup, sprint cards and run flow editable without backend', async ({ page }) => {
    await installBrowserGuards(page);
    page.on('dialog', async (dialog) => {
      await dialog.accept();
    });

    await page.goto('/');

    await expect(page.getByText(/LOGIN SENDSPRINT/i)).toBeVisible();
    await page.getByLabel(/^API$/i).fill('local://sendsprint');
    await page.getByLabel(/Email/i).fill('operator@acme.com');
    await page.getByLabel(/Senha/i).fill('super-secret');
    await page.getByText(/^Entrar$/i).click();

    await expect(page.getByText(/Nenhuma sprint ativa no shell web ainda/i)).toBeVisible();
    await page.getByText(/^Configurar projeto$/i).last().click();
    await expect(page.getByText(/Configuracao do projeto/i)).toBeVisible();
    await page.getByLabel(/Repository name/i).fill('local-web');
    await page.getByLabel(/Local repository path/i).fill('C:/workspace/local-web');
    await page.getByLabel(/^Project$/i).fill('SendSprint Web');
    await page.getByText(/^Save setup$/i).click();
    await expect(page.getByText(/Repos active: 1/i)).toBeVisible();
    await page.getByText(/Back to dashboard/i).click();

    await page.getByText(/^Iniciar$/i).first().click();
    await page.getByText(/^Azure DevOps$/i).last().click();
    await expect(page.getByText(/Conectar Azure DevOps/i)).toBeVisible();
    await page.getByLabel(/URL da Sprint/i).fill('https://dev.azure.com/acme/payments/_sprints/taskboard/Team%20Falcon/Sprint%207');
    await expect(page.getByLabel(/Usuario \/ email Azure DevOps/i)).toHaveValue('operator@acme.com');
    await page.getByLabel(/Personal Access Token/i).fill('local-pat');
    await page.getByLabel(/Organizacao/i).fill('Acme');
    await page.getByLabel(/Projeto/i).fill('Payments');
    await page.getByLabel(/Equipe/i).fill('Team Falcon');
    await page.getByText(/^Conectar$/i).click();

    await expect(page.getByText(/SPRINT BACKLOG/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/SS-101/i)).toBeVisible();
    await page.getByText(/Play todos do backlog/i).click();
    await expect(page.getByText(/Awaiting Deploy/i)).toBeVisible({ timeout: 15_000 });

    await page.getByText(/Configurar repositorio local do projeto/i).click();
    await expect(page.getByText(/Card local editavel/i)).toBeVisible();
    await page.getByText(/^Arquivar$/i).click();
    await expect(page.getByText(/SPRINT BACKLOG/i)).toBeVisible();
    await page.getByText(/Mostrar arquivados/i).click();
    await expect(page.getByText(/SS-101/i)).toBeVisible();

    await page.goto('/?screen=Run&sprintId=Acme%2FPayments%2FTeam%20Falcon%2FSprint%207&mode=selected&itemKeys=SS-101');
    await expect(page.getByText(/Executando sprint/i)).toBeVisible();
    await expect(page.getByText(/Modo local ativo/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Ver resultado/i)).toBeVisible({ timeout: 15_000 });
  });

  test('project setup plus Azure auth imports the sprint and opens backlog detail tabs', async ({ page }) => {
    const state = createMockState();
    await installBrowserGuards(page);
    await seedSession(page, makeSession());
    await installMockBackend(page, state);

    await page.goto('/');

    await expect(page.getByText(/Nenhuma sprint ativa no shell web ainda/i)).toBeVisible();
    page.on('dialog', async (dialog) => {
      await dialog.accept();
    });

    await page.getByText(/^Configurar projeto$/i).last().click();
    await expect(page.getByText(/Configuracao do projeto/i)).toBeVisible();
    await page.getByLabel(/Repository name/i).fill('web-shell');
    await page.getByLabel(/Local repository path/i).fill('C:/workspace/sendsprint-web');
    await page.getByLabel(/^Project$/i).fill('Workspace Shell');
    await page.getByLabel(/Branch pattern/i).fill('feature/{item_key}-{slug}');
    await page.getByLabel(/Commit pattern/i).fill('feat: {summary}');
    await page.getByLabel(/Deploy target branch/i).fill('dev');
    await page.getByText(/^Save setup$/i).click();
    await page.getByText(/Back to dashboard/i).click();

    await page.getByText(/^Iniciar$/i).first().click();
    await page.getByText(/^Azure DevOps$/i).click();
    await expect(page.getByText(/Conectar Azure DevOps/i)).toBeVisible();
    await page.getByLabel(/URL da Sprint/i).fill('https://dev.azure.com/acme/payments/_sprints/taskboard/Team%20Falcon/Sprint%207');
    await expect(page.getByLabel(/Usuario \/ email Azure DevOps/i)).toHaveValue('operator@acme.com');
    await page.getByLabel(/Personal Access Token/i).fill('ado-token');
    await page.getByLabel(/Organizacao/i).fill('Acme');
    await page.getByLabel(/Projeto/i).fill('Payments');
    await page.getByLabel(/Equipe/i).fill('Team Falcon');
    await page.getByText(/^Conectar$/i).click();

    await expect(page.getByText(/SPRINT BACKLOG/i)).toBeVisible();
    await expect(page.getByText(/AZ-101/i)).toBeVisible();
    await expect(page.getByText(/AZ-103/i)).not.toBeVisible();

    await page.locator('#sprint-card-AZ-101').dragTo(page.locator('#sprint-column-planning'));
    await expect(page.getByText(/^Planning \(1\)$/i)).toBeVisible();
    await expect(page.getByText(/^Backlog \(1\)$/i)).toBeVisible();

    await page.getByText(/Play todos do backlog/i).click();

    await page.getByText(/Implementar onboarding do SendSprint/i).click();
    await expect(page.getByText(/Visao geral/i)).toBeVisible();
    await expect(page.getByText(/Criar a jornada inicial com acentua.*login e CTA Iniciar/i)).toBeVisible();
    await page.getByText(/^Logs$/i).click();
    await expect(page.getByText(/planning em progresso/i)).toBeVisible();
    await page.getByText(/^Readiness$/i).click();
    await expect(page.getByText(/Veredito:/i)).toBeVisible();
    await page.getByText(/^Evidencias$/i).click();
    await expect(page.getByText(/Board capture/i)).toBeVisible();
  });

  test('Azure flow without active iteration falls back to Sprints import progress', async ({ page }) => {
    const state = createMockState();
    state.azureAuthMode = 'sprints';
    await installBrowserGuards(page);
    await seedSession(page, makeSession());
    await installMockBackend(page, state);

    await page.goto('/');

    await page.getByText(/^Iniciar$/i).first().click();
    await page.getByText(/^Azure DevOps$/i).click();
    await page.getByLabel(/URL da Sprint/i).fill('https://dev.azure.com/acme/payments/_sprints/taskboard/Team%20Falcon/Sprint%207');
    await page.getByLabel(/Usuario \/ email Azure DevOps/i).fill('operator@acme.com');
    await page.getByLabel(/Personal Access Token/i).fill('ado-token');
    await page.getByLabel(/Organizacao/i).fill('Acme');
    await page.getByLabel(/Projeto/i).fill('Payments');
    await page.getByLabel(/Equipe/i).fill('Team Falcon');
    await page.getByText(/^Conectar$/i).click();

    await expect(page.getByText(/IMPORT CONTEXT/i)).toBeVisible();
    await expect(page.getByText(/IMPORT PIPELINE/i)).toBeVisible();
    await page.getByText(/Importar todas em background/i).click();
    await expect(page.getByText(/Importacao concluida/i)).toBeVisible({ timeout: 15_000 });

    await page.getByText(/Sprint 7 - Workspace Shell/i).first().evaluate((element: HTMLElement) => element.click());
    await expect(page.getByText(/SPRINT BACKLOG/i)).toBeVisible();
  });

  test('dashboard sidebar reaches settings, manager, health, support, reports and admin', async ({ page }) => {
    const state = createMockState();
    await installBrowserGuards(page);
    await seedSession(
      page,
      makeSession({
        provider: 'azuredevops',
        account: 'operator@acme.com',
        adoTeamPath: 'Acme/Payments/Team Falcon',
        currentSprint: {
          provider: 'azuredevops',
          sprintId: 'Acme/Payments/Team Falcon/Sprint 7',
          sprintName: 'Sprint 7 - Workspace Shell',
          sprintUrl: 'https://dev.azure.com/acme/payments/_sprints/taskboard/Team%20Falcon/Sprint%207',
          portfolioName: 'Acme',
          projectName: 'Payments',
          teamName: 'Team Falcon',
        },
        projectSetup: {
          mode: 'single',
          branchPattern: 'feature/{item_key}-{slug}',
          commitPattern: 'feat: {summary}',
          deployTargetBranch: 'dev',
          repositories: [
            {
              id: 'repo-1',
              name: 'web-shell',
              repoPath: 'C:/workspace/sendsprint-web',
              role: 'fullstack',
              project: 'Workspace Shell',
              validationCommands: ['npm run typecheck', 'npm test'],
            },
          ],
          updatedAt: '2026-05-20T15:00:00Z',
        },
      }),
    );
    await seedSupportTickets(page, makeSupportTickets());
    await installMockBackend(page, state);

    await page.goto('/');

    await expect(page.getByText(/Sprint 7 - Workspace Shell/i)).toBeVisible();

    await page.getByText(/^Configuracoes$/i).click();
    await expect(page.getByText(/Parametros locais, backend conectado/i)).toBeVisible();
    await page.getByText(/^Modelos$/i).click();
    await expect(page.getByText(/Playwright primeiro/i)).toBeVisible();

    await page.getByText(/^Manager$/i).last().click();
    await expect(page.getByText(/Minha equipe/i)).toBeVisible();

    await page.getByText(/^Saude$/i).last().click();
    await expect(page.getByText(/Overview/i)).toBeVisible();
    await page.getByText(/Governance/i).click();
    await expect(page.getByText(/ACTIVE RISKS/i)).toBeVisible();

    await page.getByText(/^Portfolio$/i).last().click();
    await expect(page.getByText(/Visao de portfolio/i)).toBeVisible();
    await expect(page.getByText(/VISAO POR PROJETO/i)).toBeVisible();

    await page.getByText(/^Suporte$/i).last().click();
    await expect(page.getByText(/ABRIR NOVO CASO/i)).toBeVisible();
    await page.getByPlaceholder(/Azure fallback nao importou a sprint/i).fill('Falha no card do backlog');
    await page.getByPlaceholder(/Descreva o problema, o impacto/i).fill('O card nao mostrou readiness ao abrir o modal.');
    await page.getByText(/Registrar suporte/i).click();
    await expect(page.getByText(/Falha no card do backlog/i).last()).toBeVisible();
    await page.getByText(/Virar backlog/i).click();
    await expect(page.getByText(/backlog:/i)).toBeVisible();

    await page.getByText(/^Reports$/i).last().click();
    await expect(page.getByText(/^Throughput$/i)).toBeVisible();
    await page.getByText(/^Yools$/i).click();
    await expect(page.getByText(/spawn_agent/i)).toBeVisible();

    await page.getByText(/^Admin$/i).last().click();
    await expect(page.getByText(/Visao geral/i)).toBeVisible();
    await expect(page.getByText(/DELIVERY POLICY/i)).toBeVisible();

    await page.getByTestId('logout-button').last().click();
    await expect(page.getByText(/LOGIN SENDSPRINT/i)).toBeVisible();
    await expect(page.getByLabel(/Email/i)).toBeVisible();
  });

  test('Run screen streams live execution events', async ({ page }) => {
    const state = createMockState();
    await installBrowserGuards(page);
    await seedSession(
      page,
      makeSession({
        provider: 'azuredevops',
        currentSprint: {
          provider: 'azuredevops',
          sprintId: 'Acme/Payments/Team Falcon/Sprint 7',
          sprintName: 'Sprint 7 - Workspace Shell',
          sprintUrl: 'https://dev.azure.com/acme/payments/_sprints/taskboard/Team%20Falcon/Sprint%207',
          portfolioName: 'Acme',
          projectName: 'Payments',
          teamName: 'Team Falcon',
        },
        projectSetup: {
          mode: 'single',
          branchPattern: 'feature/{item_key}-{slug}',
          commitPattern: 'feat: {summary}',
          deployTargetBranch: 'dev',
          repositories: [
            {
              id: 'repo-run',
              name: 'web-shell',
              repoPath: 'C:/workspace/sendsprint-web',
              role: 'fullstack',
              project: 'Workspace Shell',
              validationCommands: ['npm run typecheck'],
            },
          ],
          updatedAt: '2026-05-20T15:00:00Z',
        },
      }),
    );
    await installMockBackend(page, state);
    await installMockEventSource(page, {
      '/runs/run-live-200/events': [
        { type: 'step', run_id: 'run-live-200', step: 1, status: 'running', progress: 0.1 },
        { type: 'log', run_id: 'run-live-200', message: 'Lendo sprint e montando contexto...' },
        { type: 'loop', run_id: 'run-live-200', iteration: 1, max_iterations: 3, message: 'round 1' },
        { type: 'evidence', run_id: 'run-live-200', evidence_path: 'evidence/run-live-200-1.png', evidence_label: 'Board screenshot', iteration: 1 },
        { type: 'step', run_id: 'run-live-200', step: 5, status: 'running', progress: 0.6 },
        { type: 'done', run_id: 'run-live-200', failed: false, pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/200' },
      ],
    });

    await page.goto('/?screen=Run&sprintId=Acme%2FPayments%2FTeam%20Falcon%2FSprint%207&mode=selected&itemKeys=AZ-101');

    await expect(page.getByText(/Executando sprint/i)).toBeVisible();
    await page.getByText(/Lendo sprint e montando contexto/i).scrollIntoViewIfNeeded();
    await expect(page.getByText(/^LOG$/i)).toBeVisible();
    await expect(page.getByText(/^Board screenshot$/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Ver resultado/i)).toBeVisible({ timeout: 15_000 });
  });

  test('Result screen shows PR, review handoff, deploy state and quality gate', async ({ page }) => {
    const state = createMockState();
    state.runDetails['run-result-1'] = {
      run: {
        run_id: 'run-result-1',
        state: 'done',
        sprint_id: 'Acme/Payments/Team Falcon/Sprint 7',
        provider: 'azuredevops',
        autonomy_level: 'standard',
        item_keys: ['AZ-101'],
        task: 'Implementar onboarding do SendSprint',
        branch: 'feature/az-101-onboarding',
        readiness_score: 0.98,
        readiness_verdict: 'ready_for_review',
        started_at: '2026-05-20T16:00:00Z',
        finished_at: '2026-05-20T16:02:30Z',
        summary: 'Onboarding entregue e pronto para review',
        pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/321',
        failed: false,
        last_step: 10,
        progress: 1,
      },
      quality_gate: {
        run_id: 'run-result-1',
        verdict: 'ready_for_review',
        checks: [
          {
            check_name: 'lint',
            passed: true,
            details: 'ruff and typecheck green',
            severity: 'info',
          },
          {
            check_name: 'tests',
            passed: true,
            details: 'Playwright smoke green',
            severity: 'info',
          },
        ],
        reasons: ['Todos os gates obrigatorios passaram.'],
        created_at: '2026-05-20T16:02:30Z',
      },
      evidence: {
        run_id: 'run-result-1',
        items: [
          {
            type: 'screenshot',
            path: 'evidence/onboarding-shell.png',
            label: 'Onboarding shell',
            iteration: 1,
            observed_at: '2026-05-20T16:01:20Z',
          },
        ],
        total_items: 1,
        finalized: true,
        created_at: '2026-05-20T16:02:30Z',
      },
      logs: ['onboarding entregue'],
      timeline: [{ step: 10, status: 'done' }],
    };
    state.runDashboards['run-result-1'] = {
      run: {
        run_id: 'run-result-1',
        state: 'done',
        sprint_id: 'Acme/Payments/Team Falcon/Sprint 7',
        provider: 'azuredevops',
        started_at: '2026-05-20T16:00:00Z',
        finished_at: '2026-05-20T16:02:30Z',
        summary: 'Onboarding entregue e pronto para review',
        pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/321',
        failed: false,
        last_step: 10,
      },
      evidence: [{ name: 'onboarding-shell.png', path: 'evidence/onboarding-shell.png' }],
      summary: 'Onboarding entregue e pronto para review',
      pr_url: 'https://github.com/wesleysimplicio/SendSprint/pull/321',
      blockers: [],
    };
    await installBrowserGuards(page);
    await seedSession(
      page,
      makeSession({
        projectSetup: {
          mode: 'single',
          branchPattern: 'feature/{item_key}-{slug}',
          commitPattern: 'feat: {summary}',
          deployTargetBranch: 'dev',
          repositories: [
            {
              id: 'repo-result',
              name: 'web-shell',
              repoPath: 'C:/workspace/sendsprint-web',
              role: 'fullstack',
              project: 'Workspace Shell',
              validationCommands: ['npm run typecheck'],
            },
          ],
          updatedAt: '2026-05-20T15:00:00Z',
        },
      }),
    );
    await installMockBackend(page, state);

    await page.goto('/?screen=Result&runId=run-result-1');

    await expect(page.getByText('https://github.com/wesleysimplicio/SendSprint/pull/321').first()).toBeVisible();
    await expect(page.getByText(/Review Humana/i)).toBeVisible();
    await expect(page.getByText(/Handoff para Deploy/i)).toBeVisible();
    await page.getByText(/QUALITY GATE/i).scrollIntoViewIfNeeded();
    await expect(page.getByText(/QUALITY GATE/i)).toBeVisible();
    await expect(page.getByText(/Playwright smoke green/i)).toBeVisible();
    await expect(page.getByText(/Onboarding shell/i)).toBeVisible();
  });
});
