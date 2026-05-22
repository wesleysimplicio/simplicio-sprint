import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { subscribeToRun, type Subscription } from "../api/sse";
import type { RunEvent } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Run">;
type Rt = RouteProp<RootStackParamList, "Run">;

const STEP_LABELS: Record<number, string> = {
  1: "Analisar a tarefa",
  2: "Planejar abordagem",
  3: "Mapear contexto e código",
  4: "Implementar mudanças",
  5: "Executar testes",
  6: "Validar resultados",
  7: "Gerar evidências",
  8: "Criar/atualizar PR",
  9: "Atualizar documentação",
  10: "Preparar handoff",
};

type StepStatus = "pending" | "running" | "ok" | "skipped" | "failed";

type StepState = {
  num: number;
  status: StepStatus;
  message?: string;
};

type EvidenceShot = {
  name: string;
  iteration: number;
  label: string;
  url: string;
};

export const RunScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const route = useRoute<Rt>();
  const { api, session } = useSession();
  const subRef = useRef<Subscription | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  const [runId, setRunId] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepState[]>(
    Object.keys(STEP_LABELS).map((k) => ({
      num: Number(k),
      status: "pending",
    })),
  );
  const [logs, setLogs] = useState<string[]>([]);
  const [evidence, setEvidence] = useState<EvidenceShot[]>([]);
  const [iteration, setIteration] = useState(1);
  const [maxIterations, setMaxIterations] = useState(3);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [prUrl, setPrUrl] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [currentActivity, setCurrentActivity] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSec(
        Math.floor((Date.now() - startTimeRef.current) / 1000),
      );
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const primaryRepo =
          session.projectSetup.mode === "single"
            ? session.projectSetup.repositories[0]?.repoPath.trim()
            : null;
        const res = await api.startRun({
          provider:
            session.currentSprint?.provider ?? session.provider ?? "jira",
          sprint_id: route.params.sprintId,
          mode: route.params.mode,
          item_keys: route.params.itemKeys,
          repo_path:
            primaryRepo && !looksRemote(primaryRepo) ? primaryRepo : undefined,
          project_setup: session.projectSetup.repositories.length
            ? session.projectSetup
            : null,
        });
        setRunId(res.run_id);
        startTimeRef.current = Date.now();
        subRef.current = subscribeToRun(api.eventsUrl(res.run_id), {
          onEvent: (ev) => handleEvent(ev, res.run_id),
          onError: (e) => console.warn("sse error", e),
        });
      } catch (e) {
        setLogs((current) => [
          ...current,
          "[ERROR] Falha ao iniciar: " + String((e as Error).message ?? e),
        ]);
        setFailed(true);
      }
    })();
    return () => subRef.current?.close();
  }, []);

  const handleEvent = (ev: RunEvent, currentRunId: string) => {
    if (ev.type === "step" && ev.step != null) {
      const stepNum = ev.step;
      const status = (ev.status ?? "running") as StepStatus;
      setSteps((prev) =>
        prev.map((s) => {
          if (s.num === stepNum)
            return {
              num: s.num,
              status,
              message: ev.message ?? s.message,
            };
          if (s.num < stepNum && s.status === "pending")
            return { ...s, status: "ok" };
          return s;
        }),
      );
      if (typeof ev.progress === "number") setProgress(ev.progress);
      if (ev.status === "running")
        setCurrentActivity(ev.message ?? STEP_LABELS[stepNum]);
    } else if (ev.type === "loop") {
      if (typeof ev.iteration === "number") setIteration(ev.iteration);
      if (typeof ev.max_iterations === "number")
        setMaxIterations(ev.max_iterations);
      setLogs((current) => [
        ...current,
        `[INFO]  Round ${ev.iteration}: ${ev.message ?? "fix loop"}`,
      ]);
    } else if (ev.type === "log") {
      setLogs((current) => [
        ...current,
        `${formatNow()} [INFO]  ${ev.message ?? ""}`,
      ]);
    } else if (ev.type === "evidence") {
      const path = ev.evidence_path ?? "";
      const name = path.split("/").pop() ?? path;
      const iter = ev.iteration ?? 1;
      setEvidence((current) => [
        ...current,
        {
          name,
          iteration: iter,
          label: ev.evidence_label ?? name,
          url: api.evidenceUrl(currentRunId, name),
        },
      ]);
    } else if (ev.type === "done") {
      setDone(true);
      setFailed(Boolean(ev.failed));
      setPrUrl(ev.pr_url ?? null);
      setProgress(1);
      setSteps((prev) =>
        prev.map((s) =>
          s.status === "running"
            ? { ...s, status: ev.failed ? "failed" : "ok" }
            : s.status === "pending" && !ev.failed
              ? { ...s, status: "ok" }
              : s,
        ),
      );
    } else if (ev.type === "error") {
      setFailed(true);
      setLogs((current) => [
        ...current,
        `${formatNow()} [ERROR] ${ev.message ?? ""}`,
      ]);
    }
  };

  const goToResult = () => runId && nav.navigate("Result", { runId });

  const provider =
    session.currentSprint?.provider ?? session.provider ?? "jira";
  const primaryRepo = session.projectSetup.repositories[0];
  const taskKey = route.params.itemKeys[0] ?? "PLAT-73";
  const taskTitle =
    currentActivity ??
    (route.params.mode === "all"
      ? "Sprint inteira"
      : route.params.mode === "mine"
        ? "Apenas seus itens"
        : `${route.params.itemKeys.length} item(s) selecionado(s)`);

  return (
    <Screen scroll={false}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 28, gap: 16 }}
      >
        <Card padding={22}>
          <View style={styles.runHeader}>
            <View style={{ flex: 1 }}>
              <View style={styles.runHeaderRow}>
                <Text style={styles.runHeaderLabel}>Execução:</Text>
                <Text style={styles.runHeaderTitle}>
                  {taskKey} – {taskTitle}
                </Text>
              </View>
            </View>
            <View style={styles.elapsedBox}>
              <Text style={styles.elapsedLabel}>Tempo decorrido</Text>
              <Text style={styles.elapsedValue}>{formatTime(elapsedSec)}</Text>
            </View>
          </View>
        </Card>

        <View style={styles.runGrid}>
          <Card padding={20} style={styles.stepsPane}>
            <Text style={styles.paneTitle}>Fluxo de execução (10 passos)</Text>
            <View style={styles.stepList}>
              {steps.map((step) => (
                <StepRow
                  key={step.num}
                  num={step.num}
                  label={STEP_LABELS[step.num]}
                  status={step.status}
                />
              ))}
            </View>
          </Card>

          <View style={styles.activityCol}>
            <Card padding={20}>
              <Text style={styles.paneTitle}>Atividade atual</Text>
              <Text style={styles.activityText}>
                {currentActivity ??
                  "Aguardando início da execução…"}
              </Text>

              <Text style={[styles.paneTitle, { marginTop: 20 }]}>
                Evidências ao vivo
              </Text>
              <View style={styles.evidenceRow}>
                {(evidence.length ? evidence.slice(-3) : PLACEHOLDER_EVIDENCE).map(
                  (shot, idx) => (
                    <View key={idx} style={styles.evidenceCard}>
                      {shot.url ? (
                        <Image
                          source={{ uri: shot.url }}
                          style={styles.evidenceImg}
                        />
                      ) : (
                        <View style={styles.evidencePlaceholder}>
                          <Text style={styles.evidencePlaceholderText}>
                            {shot.label}
                          </Text>
                        </View>
                      )}
                    </View>
                  ),
                )}
              </View>
            </Card>

            <Card padding={20}>
              <Text style={styles.paneTitle}>Logs em tempo real</Text>
              <View style={styles.logBox}>
                {logs.length === 0 ? (
                  <Text style={styles.logEmpty}>
                    {formatNow()} [INFO]  Aguardando eventos…
                  </Text>
                ) : (
                  logs.slice(-8).map((line, idx) => (
                    <Text key={idx} style={styles.logLine}>
                      {line}
                    </Text>
                  ))
                )}
              </View>
            </Card>
          </View>

          <Card padding={20} style={styles.contextPane}>
            <Text style={styles.paneTitle}>Contexto</Text>

            <View style={styles.ctxRow}>
              <Text style={styles.ctxLabel}>Branch</Text>
              <Text style={styles.ctxValue}>
                {renderPattern(
                  session.projectSetup.branchPattern,
                  taskKey,
                )}
              </Text>
            </View>

            <View style={styles.ctxRow}>
              <Text style={styles.ctxLabel}>Repositório</Text>
              <Text style={styles.ctxValue}>
                {primaryRepo?.repoPath || "não configurado"}
              </Text>
            </View>

            <View style={styles.ctxRow}>
              <Text style={styles.ctxLabel}>Modelo</Text>
              <Text style={styles.ctxValue}>GPT-4o</Text>
            </View>

            <View style={styles.ctxRow}>
              <Text style={styles.ctxLabel}>Executor</Text>
              <Text style={styles.ctxValue}>SendSprint Agent</Text>
            </View>

            <View style={styles.ctxRow}>
              <Text style={styles.ctxLabel}>Provider</Text>
              <Text style={styles.ctxValue}>
                {provider === "azuredevops" ? "Azure DevOps" : "Jira"}
              </Text>
            </View>

            {prUrl ? (
              <View style={[styles.prBox, failed ? styles.prFail : styles.prOk]}>
                <Text style={styles.prBoxTitle}>
                  {failed ? "Entrega falhou" : "PR criado"}
                </Text>
                <Text style={styles.prBoxUrl} numberOfLines={1}>
                  {prUrl}
                </Text>
              </View>
            ) : null}

            <Pressable
              onPress={goToResult}
              disabled={!runId}
              style={styles.viewDetails}
            >
              <Text style={styles.viewDetailsText}>
                Ver detalhes da execução
              </Text>
            </Pressable>
          </Card>
        </View>

        <View style={styles.runFooter}>
          <View style={styles.runFooterLeft}>
            <Text style={styles.runFooterLabel}>
              Round {iteration} / {maxIterations}
            </Text>
            <View style={styles.progressBar}>
              <View
                style={[
                  styles.progressFill,
                  { width: `${Math.round(progress * 100)}%` },
                ]}
              />
            </View>
            <Text style={styles.runFooterMeta}>
              {Math.round(progress * 100)}%
            </Text>
          </View>
          {done ? (
            <Button
              title={failed ? "Ver detalhes da falha" : "Ver resultado"}
              onPress={goToResult}
              iconRight="arrow-right"
            />
          ) : null}
        </View>
      </ScrollView>
    </Screen>
  );
};

const StepRow: React.FC<{
  num: number;
  label: string;
  status: StepStatus;
}> = ({ num, label, status }) => {
  const isDone = status === "ok";
  const isRunning = status === "running";
  const isFailed = status === "failed";
  const isPending = status === "pending";

  let bubbleColor: string = theme.surfaceMuted;
  let bubbleBorder: string = theme.border;
  const glyphColor: string = theme.textMuted;
  let glyph: React.ReactNode = (
    <Text style={[styles.stepNum, { color: glyphColor }]}>{num}</Text>
  );

  if (isDone) {
    bubbleColor = theme.success;
    bubbleBorder = theme.success;
    glyph = <Icon name="check" size={13} color="#fff" />;
  } else if (isRunning) {
    bubbleColor = theme.primary;
    bubbleBorder = theme.primary;
    glyph = (
      <Text style={[styles.stepNum, { color: "#fff" }]}>{num}</Text>
    );
  } else if (isFailed) {
    bubbleColor = theme.danger;
    bubbleBorder = theme.danger;
    glyph = <Icon name="x" size={13} color="#fff" />;
  }

  return (
    <View style={styles.stepRow}>
      <View
        style={[
          styles.stepBubble,
          {
            backgroundColor: bubbleColor,
            borderColor: bubbleBorder,
          },
        ]}
      >
        {glyph}
      </View>
      <Text
        style={[
          styles.stepLabel,
          isDone && { color: theme.text },
          isRunning && { color: theme.primary, fontWeight: "600" },
        ]}
      >
        {label}
      </Text>
      <Text
        style={[
          styles.stepStatus,
          isDone && { color: theme.success },
          isRunning && { color: theme.primary },
          isFailed && { color: theme.danger },
          isPending && { color: theme.textSoft },
        ]}
      >
        {isDone
          ? "Concluído"
          : isRunning
            ? "Em andamento"
            : isFailed
              ? "Falhou"
              : "Pendente"}
      </Text>
    </View>
  );
};

const PLACEHOLDER_EVIDENCE = [
  { name: "code", iteration: 1, label: "Editor", url: "" },
  { name: "console", iteration: 1, label: "Console", url: "" },
  { name: "browser", iteration: 1, label: "Browser", url: "" },
];

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

const renderPattern = (pattern: string, itemKey?: string): string => {
  return pattern
    .replace(/\{?\{issueKey\}?\}/gi, itemKey ?? "PLAT-73")
    .replace(/\{slug\}/g, "payments");
};

const formatTime = (sec: number): string => {
  const h = Math.floor(sec / 3600).toString().padStart(2, "0");
  const m = Math.floor((sec % 3600) / 60).toString().padStart(2, "0");
  const s = (sec % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
};

const formatNow = (): string => {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map((v) => String(v).padStart(2, "0"))
    .join(":");
};

const styles = StyleSheet.create({
  runHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14,
    flexWrap: "wrap",
  },
  runHeaderRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 8,
    flexWrap: "wrap",
  },
  runHeaderLabel: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  runHeaderTitle: {
    color: theme.text,
    fontSize: 16,
    fontFamily: theme.fontSans,
  },
  elapsedBox: {
    alignItems: "flex-end",
  },
  elapsedLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  elapsedValue: {
    color: theme.text,
    fontSize: 14,
    fontFamily: theme.fontMono,
    fontWeight: "700",
    marginTop: 2,
  },
  runGrid: {
    flexDirection: "row",
    gap: 16,
    alignItems: "flex-start",
    flexWrap: "wrap",
  },
  stepsPane: {
    width: 280,
    minWidth: 240,
    gap: 14,
  },
  activityCol: {
    flex: 1,
    minWidth: 360,
    gap: 16,
  },
  contextPane: {
    width: 260,
    minWidth: 220,
    gap: 14,
  },
  paneTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginBottom: 4,
  },
  stepList: {
    gap: 12,
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  stepBubble: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
  },
  stepNum: {
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  stepLabel: {
    flex: 1,
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  stepStatus: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  activityText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 19,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  evidenceRow: {
    flexDirection: "row",
    gap: 12,
    marginTop: 10,
  },
  evidenceCard: {
    flex: 1,
    minWidth: 100,
    aspectRatio: 1.6,
    borderRadius: 10,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surfaceMuted,
  },
  evidenceImg: {
    width: "100%",
    height: "100%",
  },
  evidencePlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  evidencePlaceholderText: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  logBox: {
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    padding: 12,
    marginTop: 6,
    gap: 4,
    minHeight: 140,
  },
  logEmpty: {
    color: theme.textSoft,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  logLine: {
    color: theme.text,
    fontSize: 11,
    fontFamily: theme.fontMono,
    lineHeight: 16,
  },
  ctxRow: {
    gap: 3,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  ctxLabel: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  ctxValue: {
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontMono,
    fontWeight: "600",
  },
  prBox: {
    borderRadius: 8,
    padding: 12,
    gap: 4,
    marginTop: 8,
  },
  prOk: {
    backgroundColor: theme.successSoft,
  },
  prFail: {
    backgroundColor: theme.dangerSoft,
  },
  prBoxTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  prBoxUrl: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontMono,
  },
  viewDetails: {
    marginTop: 6,
    paddingVertical: 8,
  },
  viewDetailsText: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  runFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
    paddingTop: 8,
  },
  runFooterLeft: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  runFooterLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  progressBar: {
    flex: 1,
    height: 8,
    backgroundColor: theme.surfaceMuted,
    borderRadius: 999,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: theme.primary,
    borderRadius: 999,
  },
  runFooterMeta: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
});
