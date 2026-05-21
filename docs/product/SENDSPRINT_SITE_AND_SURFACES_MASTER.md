# SendSprint Site And Surfaces Master

Generated at: 2026-05-20 21:32:17 -03:00

## Purpose

This document is the master product snapshot for what SendSprint already has in the site/app surfaces and what it is planned to have next across Console, Web, Desktop, and Mobile. It also consolidates the current open GitHub issue backlog so product, design, and implementation can stay aligned.

## What SendSprint Is Becoming

SendSprint is evolving from a sprint automation CLI into a local-first delivery control plane with a chat-first operator shell, sprint import, backlog orchestration, task execution, evidence capture, review handoff, deploy staging, governance, and future company-grade administration.

## What Exists Now In Product Surfaces

- Connect / app login shell
- Provider picker
- Jira auth and Azure auth
- Sprints list
- Sprint detail backlog / kanban
- Run live execution
- Result screen
- Project setup
- Settings / connections
- Control-plane dashboard

## Current Console Plus Web Functional Slice

- app login with local active-user validation for now
- empty post-login shell with `Iniciar` and setup actions
- provider connection for Jira and Azure DevOps
- fallback chain for sprint capture: fixed transport order `mcp -> api -> playwright`, then browser-agent capture when browser-native capture fails
- sprint import into an internal backlog workspace
- kanban by task with play per card and play-all from the sprint workspace
- project setup with local repository paths, roles, branch patterns, commit patterns, validation commands, and deploy target branch
- live execution with logs, evidence, loops, and result handoff

## Planned Product Modules

- identity-and-subscription-login
- provider-connections-and-sprint-import
- chat-first-operator-shell
- kanban-backlog-and-task-play-controls
- live-run-logs-evidence-and-result-handoff
- project-setup-and-repository-routing
- manager-console-and-company-health
- support-center-reports-and-governance
- desktop-shells-for-windows-and-macos
- mobile-workflows-for-ios-and-android
- console-narrative-ux

## Platform Roadmap

- Console: keep as operator-first and narration-first execution surface
- Web: first sellable functional surface and the main control plane
- Desktop Windows: planned after Console + Web
- Desktop macOS: planned after Console + Web
- Desktop Linux: planned after the first desktop wave
- Mobile iPhone: future compact operator and manager workflows
- Mobile Android: future compact operator and manager workflows

## User Journeys

### Developer journey

1. Log into SendSprint.
2. Enter the empty shell.
3. Click `Iniciar`.
4. Connect Jira or Azure DevOps.
5. Import the sprint into the internal backlog.
6. Configure the repository path and execution rules.
7. Trigger play by task or play-all.
8. Observe logs, evidence, review state, and deploy handoff.

### Company / manager journey

1. Join the workspace with company-approved access.
2. Observe portfolio, project, team, and sprint delivery status.
3. Track who is working on what, which models are used, and what is blocked.
4. Review support items, reports, governance outputs, and deployment readiness.

## Visual Direction

- clean and premium, but operational
- Codex-like blue hierarchy and precise control-plane feel
- Claude-like whitespace, calm layout, and technical clarity
- light-theme-first, no purple bias, no generic AI dashboard styling
- strong separation between shell, backlog, detail panels, and logs

## Design Package In Repo

- `telas/README.md`
- `telas/SCREEN_INVENTORY.md`
- `telas/GPT_IMAGE_2_PROMPTS.md`
- `telas/manifest.json`
- `telas/exports/README.md`

## Backlog Snapshot

Open GitHub issues in this repository: 112

### Highlighted control-plane and design anchors

- #145 [epic: plan SendSprint vNext as a local delivery control plane](https://github.com/wesleysimplicio/SendSprint/issues/145)
- #149 [epic: chat-first multi-agent workspace for arbitrary project tasks](https://github.com/wesleysimplicio/SendSprint/issues/149)
- #160 [epic: plan developer-vs-company onboarding modes and multi-provider connection center](https://github.com/wesleysimplicio/SendSprint/issues/160)
- #169 [epic: plan subscription-gated distribution, entitlement enforcement, and managed LLM chat surfaces](https://github.com/wesleysimplicio/SendSprint/issues/169)
- #177 [epic: plan versioned updates and phased rollout from Console + Web to Desktop and Mobile](https://github.com/wesleysimplicio/SendSprint/issues/177)
- #199 [plan: define the functional Console + Web release scope without billing and re-sequence the open backlog](https://github.com/wesleysimplicio/SendSprint/issues/199)
- #200 [plan: [Sprint CW-2A] Build the first functional Console + Web release without billing](https://github.com/wesleysimplicio/SendSprint/issues/200)
- #202 [plan: [Sprint CW-F1] Zero-to-connected workspace and onboarding foundation](https://github.com/wesleysimplicio/SendSprint/issues/202)
- #203 [plan: [Sprint CW-F2] First chat-to-task execution baseline](https://github.com/wesleysimplicio/SendSprint/issues/203)
- #204 [plan: [Sprint CW-F3] External sync, mapping, and controlled execution](https://github.com/wesleysimplicio/SendSprint/issues/204)
- #205 [plan: [Sprint CW-F4] Visibility, diagnostics, support, and launch readiness](https://github.com/wesleysimplicio/SendSprint/issues/205)
- #241 [epic: align SendSprint surfaces with a clean Codex-Claude inspired operator UX](https://github.com/wesleysimplicio/SendSprint/issues/241)
- #242 [design: refine the login and empty-shell onboarding journey for Console + Web](https://github.com/wesleysimplicio/SendSprint/issues/242)
- #243 [design: redesign provider connection and sprint import UX with explicit fallback states](https://github.com/wesleysimplicio/SendSprint/issues/243)
- #244 [design: refine the sprint backlog Kanban, card detail, and play controls](https://github.com/wesleysimplicio/SendSprint/issues/244)
- #245 [design: redesign live execution, logs, evidence, and result-review-deploy surfaces](https://github.com/wesleysimplicio/SendSprint/issues/245)
- #246 [design: unify project setup, settings, manager, company health, support, and reporting shells](https://github.com/wesleysimplicio/SendSprint/issues/246)
- #247 [design: adapt the SendSprint design system to Windows and macOS desktop shells](https://github.com/wesleysimplicio/SendSprint/issues/247)
- #248 [design: adapt the SendSprint design system to iPhone and Android mobile workflows](https://github.com/wesleysimplicio/SendSprint/issues/248)
- #249 [design: polish the SendSprint console narrative UX and terminal command surfaces](https://github.com/wesleysimplicio/SendSprint/issues/249)

## Full Open Issue List

- #138 [feat: ship a reference internal developer portal on top of the local control plane](https://github.com/wesleysimplicio/SendSprint/issues/138)
- #139 [feat: formalize SendSprint agent sidecar mode across supported coding assistants](https://github.com/wesleysimplicio/SendSprint/issues/139)
- #140 [epic: operator queue, intervention, and recovery flow](https://github.com/wesleysimplicio/SendSprint/issues/140)
- #141 [feat: turn evidence and executive outputs into stakeholder-ready governance packs](https://github.com/wesleysimplicio/SendSprint/issues/141)
- #142 [feat: connect transcript ingestion to task understanding and delivery handoff](https://github.com/wesleysimplicio/SendSprint/issues/142)
- #143 [plan: decide whether SendSprint vNext stays software-first or expands into a general action engine](https://github.com/wesleysimplicio/SendSprint/issues/143)
- #144 [architecture: define the team-hosted and enterprise hardening path beyond localhost mode](https://github.com/wesleysimplicio/SendSprint/issues/144)
- #145 [epic: plan SendSprint vNext as a local delivery control plane](https://github.com/wesleysimplicio/SendSprint/issues/145)
- #146 [epic: onboarding wizard and preflight checklist for Web and Desktop](https://github.com/wesleysimplicio/SendSprint/issues/146)
- #147 [architecture: choose the Desktop shell, runtime boundary, and packaging strategy for macOS and Windows](https://github.com/wesleysimplicio/SendSprint/issues/147)
- #148 [feat: ship packaged Desktop builds for macOS Apple Silicon, macOS Intel, and Windows](https://github.com/wesleysimplicio/SendSprint/issues/148)
- #149 [epic: chat-first multi-agent workspace for arbitrary project tasks](https://github.com/wesleysimplicio/SendSprint/issues/149)
- #150 [epic: approved coding-agent routing through worktree and CLI execution adapters](https://github.com/wesleysimplicio/SendSprint/issues/150)
- #151 [epic: immutable audit logs and actor-attributed activity history](https://github.com/wesleysimplicio/SendSprint/issues/151)
- #152 [epic: manager operations console for employee workload, live activity, and approvals](https://github.com/wesleysimplicio/SendSprint/issues/152)
- #153 [epic: time spent, token usage, model-provider usage, and execution cost analytics](https://github.com/wesleysimplicio/SendSprint/issues/153)
- #154 [epic: company reports for throughput, effort, cost, model usage, and audit export](https://github.com/wesleysimplicio/SendSprint/issues/154)
- #155 [epic: identity and access with email-password, Azure SSO, and role-based approval flows](https://github.com/wesleysimplicio/SendSprint/issues/155)
- #156 [epic: company administration for employee approval, entitlements, approved agents, and workspace policies](https://github.com/wesleysimplicio/SendSprint/issues/156)
- #157 [feat: add subscription billing for per-user monthly and annual plans](https://github.com/wesleysimplicio/SendSprint/issues/157)
- #158 [feat: add i18n infrastructure and localized product copy for en, fr, it, es, zh-CN, de, pl, hi, pt-BR, and nl](https://github.com/wesleysimplicio/SendSprint/issues/158)
- #159 [epic: plan SendSprint team and commercial edition backlog in phased value slices](https://github.com/wesleysimplicio/SendSprint/issues/159)
- #160 [epic: plan developer-vs-company onboarding modes and multi-provider connection center](https://github.com/wesleysimplicio/SendSprint/issues/160)
- #161 [epic: Developer-vs-Company onboarding branch and setup journey](https://github.com/wesleysimplicio/SendSprint/issues/161)
- #162 [epic: Developer Mode as a personal sprint and project delivery workspace](https://github.com/wesleysimplicio/SendSprint/issues/162)
- #163 [epic: Company Mode as a portfolio, team, and project delivery operating system](https://github.com/wesleysimplicio/SendSprint/issues/163)
- #164 [epic: Portfolio and Project shared objects across Developer and Company modes](https://github.com/wesleysimplicio/SendSprint/issues/164)
- #165 [epic: onboarding connection center for Git and work-management providers](https://github.com/wesleysimplicio/SendSprint/issues/165)
- #166 [epic: normalized source-control provider adapters for GitHub, GitLab, Bitbucket, and Gitee](https://github.com/wesleysimplicio/SendSprint/issues/166)
- #167 [epic: normalized work-management provider adapters for Azure DevOps, Jira, ClickUp, Wrike, Asana, Trello, and monday.com](https://github.com/wesleysimplicio/SendSprint/issues/167)
- #168 [epic: import and sync external portfolios, projects, boards, and repositories](https://github.com/wesleysimplicio/SendSprint/issues/168)
- #169 [epic: plan subscription-gated distribution, entitlement enforcement, and managed LLM chat surfaces](https://github.com/wesleysimplicio/SendSprint/issues/169)
- #170 [feat: add a subscription center with plan status, payment health, renewal state, and access notices](https://github.com/wesleysimplicio/SendSprint/issues/170)
- #171 [feat: enforce server-authoritative entitlement checks before chat, execution, and protected admin actions](https://github.com/wesleysimplicio/SendSprint/issues/171)
- #172 [feat: add recurring subscription compliance checks with session revalidation, grace windows, and run-safe interruption policy](https://github.com/wesleysimplicio/SendSprint/issues/172)
- #173 [epic: Codex-Claude style conversation shell with model picker and managed chat sessions](https://github.com/wesleysimplicio/SendSprint/issues/173)
- #174 [epic: managed conversational LLM provider adapters](https://github.com/wesleysimplicio/SendSprint/issues/174)
- #175 [architecture: harden Desktop distribution with signed releases, anti-tamper boundaries, and server-signed entitlement tokens](https://github.com/wesleysimplicio/SendSprint/issues/175)
- #176 [feat: integrate Stripe as the subscription billing and payment-health source of truth](https://github.com/wesleysimplicio/SendSprint/issues/176)
- #177 [epic: plan versioned updates and phased rollout from Console + Web to Desktop and Mobile](https://github.com/wesleysimplicio/SendSprint/issues/177)
- #178 [architecture: define a versioned update manifest and compatibility policy for core, Web, language packs, and theme bundles](https://github.com/wesleysimplicio/SendSprint/issues/178)
- #179 [feat: add update orchestration for Console + Web with release checks, staged rollout, and safe rollback](https://github.com/wesleysimplicio/SendSprint/issues/179)
- #180 [feat: deliver language packs and theme bundles as versioned updateable assets with safe fallback](https://github.com/wesleysimplicio/SendSprint/issues/180)
- #181 [architecture: define the shared platform and infrastructure boundary for Console + Web now, Desktop later, and Mobile later](https://github.com/wesleysimplicio/SendSprint/issues/181)
- #182 [architecture: extend the post-launch Desktop roadmap to include Linux after the initial macOS and Windows wave](https://github.com/wesleysimplicio/SendSprint/issues/182)
- #183 [plan: define the sellable Console + Web launch package, acceptance bar, and commercial readiness checklist](https://github.com/wesleysimplicio/SendSprint/issues/183)
- #184 [plan: [Sprint CW-1] Console + Web product foundation and update groundwork](https://github.com/wesleysimplicio/SendSprint/issues/184)
- #185 [plan: [Sprint CW-2] Console + Web commercial launch candidate](https://github.com/wesleysimplicio/SendSprint/issues/185)
- #186 [plan: [Sprint DX-1] Desktop, updater, and Linux groundwork after Console + Web](https://github.com/wesleysimplicio/SendSprint/issues/186)
- #187 [plan: [Sprint PX-1] Mobile-ready contracts and shared platform expansion](https://github.com/wesleysimplicio/SendSprint/issues/187)
- #188 [epic: in-product support center and support-to-backlog triage](https://github.com/wesleysimplicio/SendSprint/issues/188)
- #189 [epic: developer diagnostics and repro bundle workflow](https://github.com/wesleysimplicio/SendSprint/issues/189)
- #190 [epic: project manager planning cockpit for milestones, dependencies, delivery risks, and release readiness](https://github.com/wesleysimplicio/SendSprint/issues/190)
- #191 [epic: company workspace health and adoption center for admins](https://github.com/wesleysimplicio/SendSprint/issues/191)
- #192 [feat: add feature flags, staged rollouts, and emergency kill switches for product capabilities](https://github.com/wesleysimplicio/SendSprint/issues/192)
- #193 [architecture: define privacy, retention, and compliance policy for audit, support, AI usage, and company data](https://github.com/wesleysimplicio/SendSprint/issues/193)
- #194 [feat: add backup, export, restore, and workspace recovery flows for customer-critical product state](https://github.com/wesleysimplicio/SendSprint/issues/194)
- #195 [feat: expose public API, webhooks, and SDK contracts for enterprise integration and automation](https://github.com/wesleysimplicio/SendSprint/issues/195)
- #196 [feat: add release notes, migration assistant, and configuration upgrade guidance for customer updates](https://github.com/wesleysimplicio/SendSprint/issues/196)
- #197 [feat: add incident reporting, service health workflow, and support SLA primitives](https://github.com/wesleysimplicio/SendSprint/issues/197)
- #198 [feat: add a sales/demo sandbox mode with sample company, sample projects, and safe fake integrations](https://github.com/wesleysimplicio/SendSprint/issues/198)
- #199 [plan: define the functional Console + Web release scope without billing and re-sequence the open backlog](https://github.com/wesleysimplicio/SendSprint/issues/199)
- #200 [plan: [Sprint CW-2A] Build the first functional Console + Web release without billing](https://github.com/wesleysimplicio/SendSprint/issues/200)
- #201 [plan: defer billing, Desktop, and Mobile until after the first functional Console + Web release](https://github.com/wesleysimplicio/SendSprint/issues/201)
- #202 [plan: [Sprint CW-F1] Zero-to-connected workspace and onboarding foundation](https://github.com/wesleysimplicio/SendSprint/issues/202)
- #203 [plan: [Sprint CW-F2] First chat-to-task execution baseline](https://github.com/wesleysimplicio/SendSprint/issues/203)
- #204 [plan: [Sprint CW-F3] External sync, mapping, and controlled execution](https://github.com/wesleysimplicio/SendSprint/issues/204)
- #205 [plan: [Sprint CW-F4] Visibility, diagnostics, support, and launch readiness](https://github.com/wesleysimplicio/SendSprint/issues/205)
- #206 [front: build the onboarding mode selector, stepper, and resume UX for Developer vs Company](https://github.com/wesleysimplicio/SendSprint/issues/206)
- #207 [back: persist onboarding sessions, mode selection, and completion gates](https://github.com/wesleysimplicio/SendSprint/issues/207)
- #208 [front: build the provider connection center UI for add, test, revoke, and scoping flows](https://github.com/wesleysimplicio/SendSprint/issues/208)
- #209 [back: implement provider connection registry, health checks, and scoping APIs](https://github.com/wesleysimplicio/SendSprint/issues/209)
- #210 [back: implement Portfolio and Project domain services with mode-aware visibility rules](https://github.com/wesleysimplicio/SendSprint/issues/210)
- #211 [front: build Portfolio and Project setup flows for onboarding and workspace settings](https://github.com/wesleysimplicio/SendSprint/issues/211)
- #212 [config: persist execution defaults, provider allowlists, and notification preferences from onboarding](https://github.com/wesleysimplicio/SendSprint/issues/212)
- #213 [front: build sign-in, company join, access-denied, and role-aware shell bootstrap flows](https://github.com/wesleysimplicio/SendSprint/issues/213)
- #214 [back: implement auth, sessions, company membership, and approval services for the non-billing release](https://github.com/wesleysimplicio/SendSprint/issues/214)
- #215 [front: build company admin employee approval and workspace policy screens](https://github.com/wesleysimplicio/SendSprint/issues/215)
- #216 [back: implement company policy services for provider allowlists, execution defaults, and role restrictions](https://github.com/wesleysimplicio/SendSprint/issues/216)
- #217 [front: build the conversation shell layout with history, composer, and execution side panel](https://github.com/wesleysimplicio/SendSprint/issues/217)
- #218 [back: implement chat session state, conversation persistence, and narrated execution event stream](https://github.com/wesleysimplicio/SendSprint/issues/218)
- #219 [front: add model/provider picker, provider badges, and restricted-state messaging in the chat shell](https://github.com/wesleysimplicio/SendSprint/issues/219)
- #220 [back: implement managed conversational provider registry and provider-policy evaluation](https://github.com/wesleysimplicio/SendSprint/issues/220)
- #221 [integration: add first-release hosted conversational providers for OpenAI/Codex, Anthropic/Claude, and OpenRouter](https://github.com/wesleysimplicio/SendSprint/issues/221)
- #222 [integration: add first-release local conversational providers for Ollama and a generic local runtime contract](https://github.com/wesleysimplicio/SendSprint/issues/222)
- #223 [back: implement coding-agent execution contracts, worktree or CLI dispatch, and normalized lifecycle events](https://github.com/wesleysimplicio/SendSprint/issues/223)
- #224 [integration: add first-release coding-agent adapters for Codex, Claude, Hermes, OpenClaw, and Cursor](https://github.com/wesleysimplicio/SendSprint/issues/224)
- #225 [front: build operator queue, blocker detail, and approve or retry intervention controls](https://github.com/wesleysimplicio/SendSprint/issues/225)
- #226 [integration: implement the first-release GitHub source-control adapter for repo import, branch targets, and publish metadata](https://github.com/wesleysimplicio/SendSprint/issues/226)
- #227 [integration: implement GitLab, Bitbucket, and Gitee source-control adapters under the normalized contract](https://github.com/wesleysimplicio/SendSprint/issues/227)
- #228 [integration: implement the first-release Jira and Azure DevOps work-management adapters for project and task sync](https://github.com/wesleysimplicio/SendSprint/issues/228)
- #229 [integration: implement ClickUp, Wrike, Asana, Trello, and monday.com adapters under the normalized work-management contract](https://github.com/wesleysimplicio/SendSprint/issues/229)
- #230 [back: implement the import and incremental sync pipeline for portfolios, projects, boards, and repositories](https://github.com/wesleysimplicio/SendSprint/issues/230)
- #231 [back: implement task-origin mapping, assignee normalization, and routing-confidence services](https://github.com/wesleysimplicio/SendSprint/issues/231)
- #232 [front: build the manager live activity overview and employee drill-down experience](https://github.com/wesleysimplicio/SendSprint/issues/232)
- #233 [back: implement audit-query and activity-aggregation APIs for manager, support, and admin views](https://github.com/wesleysimplicio/SendSprint/issues/233)
- #234 [back: implement time, token, model, and report-export aggregation APIs for the first functional release](https://github.com/wesleysimplicio/SendSprint/issues/234)
- #235 [front: build the diagnostics center and repro-bundle creation flow](https://github.com/wesleysimplicio/SendSprint/issues/235)
- #236 [back: implement support-item intake, triage states, and backlog-candidate linkage services](https://github.com/wesleysimplicio/SendSprint/issues/236)
- #237 [front: build the support center UI with diagnostics, evidence, and backlog-triage attachment flows](https://github.com/wesleysimplicio/SendSprint/issues/237)
- #238 [front: build the PM planning cockpit for milestones, dependency chains, and release-risk views](https://github.com/wesleysimplicio/SendSprint/issues/238)
- #239 [back: implement company workspace health, adoption, and support-load aggregation services](https://github.com/wesleysimplicio/SendSprint/issues/239)
- #240 [front: build company health and summary views for adoption, integration risk, and operational posture](https://github.com/wesleysimplicio/SendSprint/issues/240)
- #241 [epic: align SendSprint surfaces with a clean Codex-Claude inspired operator UX](https://github.com/wesleysimplicio/SendSprint/issues/241)
- #242 [design: refine the login and empty-shell onboarding journey for Console + Web](https://github.com/wesleysimplicio/SendSprint/issues/242)
- #243 [design: redesign provider connection and sprint import UX with explicit fallback states](https://github.com/wesleysimplicio/SendSprint/issues/243)
- #244 [design: refine the sprint backlog Kanban, card detail, and play controls](https://github.com/wesleysimplicio/SendSprint/issues/244)
- #245 [design: redesign live execution, logs, evidence, and result-review-deploy surfaces](https://github.com/wesleysimplicio/SendSprint/issues/245)
- #246 [design: unify project setup, settings, manager, company health, support, and reporting shells](https://github.com/wesleysimplicio/SendSprint/issues/246)
- #247 [design: adapt the SendSprint design system to Windows and macOS desktop shells](https://github.com/wesleysimplicio/SendSprint/issues/247)
- #248 [design: adapt the SendSprint design system to iPhone and Android mobile workflows](https://github.com/wesleysimplicio/SendSprint/issues/248)
- #249 [design: polish the SendSprint console narrative UX and terminal command surfaces](https://github.com/wesleysimplicio/SendSprint/issues/249)

## Notes

- Console + Web remains the immediate delivery focus.
- Billing is intentionally outside the first functional release scope.
- Desktop and Mobile are planned but not on the critical path for the first operational launch.
- The design backlog opened from `telas/` starts at issues #241 to #249.
