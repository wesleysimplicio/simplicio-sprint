import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import { subscribeToRun, type Subscription } from "../api/sse";
import type { RunEvent } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import { StepRow } from "../components/StepRow";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Run">;
type Rt = RouteProp<RootStackParamList, "Run">;

const STEP_LABELS: Record<number, string> = {
  1: "Le a sprint",
  2: "Mapeia arquitetura",
  3: "Dev: install + build",
  4: "Lint",
  5: "Testes unitarios + E2E",
  6: "Seguranca",
  7: "Fix loop",
  8: "Commit + push",
  9: "Cria PR",
  10: "Review e entrega",
};

type StepState = {
  num: number;
  status: "pending" | "running" | "ok" | "skipped" | "failed";
  message?: string;
};

type EvidenceShot = {
  name: string;
  iteration: number;
  label: string;
  url: string;
};

type Regression = {
  iteration: number;
  status: "ok" | "failed";
  failingTests: string[];
};

export const RunScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const route = useRoute<Rt>();
  const { api, session } = useSession();
  const subRef = useRef<Subscription | null>(null);
  const scrollRef = useRef<ScrollView | null>(null);

  const [runId, setRunId] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepState[]>(
    Object.keys(STEP_LABELS).map((k) => ({ num: Number(k), status: "pending" })),
  );
  const [logs, setLogs] = useState<string[]>([]);
  const [evidence, setEvidence] = useState<EvidenceShot[]>([]);
  const [regressions, setRegressions] = useState<Regression[]>([]);
  const [iteration, setIteration] = useState(1);
  const [maxIterations, setMaxIterations] = useState(3);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [prUrl, setPrUrl] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const primaryRepo =
          session.projectSetup.mode === "single"
            ? session.projectSetup.repositories[0]?.repoPath.trim()
            : null;
        const res = await api.startRun({
          provider: session.currentSprint?.provider ?? session.provider ?? "jira",
          sprint_id: route.params.sprintId,
          mode: route.params.mode,
          item_keys: route.params.itemKeys,
          repo_path: primaryRepo && !looksRemote(primaryRepo) ? primaryRepo : undefined,
          project_setup: session.projectSetup.repositories.length ? session.projectSetup : null,
        });
        setRunId(res.run_id);
        subRef.current = subscribeToRun(api.eventsUrl(res.run_id), {
          onEvent: (ev) => handleEvent(ev, res.run_id),
          onError: (e) => console.warn("sse error", e),
        });
      } catch (e) {
        setLogs((current) => [...current, "X falha ao iniciar: " + String((e as Error).message ?? e)]);
        setFailed(true);
      }
    })();
    return () => subRef.current?.close();
  }, []);

  const handleEvent = (ev: RunEvent, currentRunId: string) => {
    if (ev.type === "step" && ev.step != null) {
      const stepNum = ev.step;
      const status = (ev.status ?? "running") as StepState["status"];
      setSteps((prev) =>
        prev.map((s) => {
          if (s.num === stepNum) return { num: s.num, status, message: ev.message ?? s.message };
          if (s.num < stepNum && s.status === "pending") return { ...s, status: "ok" };
          return s;
        }),
      );
      if (typeof ev.progress === "number") setProgress(ev.progress);
    } else if (ev.type === "loop") {
      if (typeof ev.iteration === "number") setIteration(ev.iteration);
      if (typeof ev.max_iterations === "number") setMaxIterations(ev.max_iterations);
      setLogs((current) => [...current, `round ${ev.iteration}: ${ev.message ?? "fix loop"}`]);
    } else if (ev.type === "regression") {
      if (typeof ev.iteration === "number") {
        setRegressions((current) => [
          ...current.filter((item) => item.iteration !== ev.iteration),
          {
            iteration: ev.iteration!,
            status: (ev.status === "ok" ? "ok" : "failed") as "ok" | "failed",
            failingTests: ev.failing_tests ?? [],
          },
        ]);
      }
    } else if (ev.type === "log") {
      setLogs((current) => [...current, ev.message ?? ""]);
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
      setLogs((current) => [...current, `evidence: ${ev.evidence_label ?? name}`]);
    } else if (ev.type === "done") {
      setDone(true);
      setFailed(Boolean(ev.failed));
      setPrUrl(ev.pr_url ?? null);
      setProgress(1);
      setSteps((prev) =>
        prev.map((s) => (s.status === "running" ? { ...s, status: ev.failed ? "failed" : "ok" } : s)),
      );
    } else if (ev.type === "error") {
      setFailed(true);
      setLogs((current) => [...current, "X erro: " + (ev.message ?? "")]);
    }
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
  };

  const goToResult = () => runId && nav.navigate("Result", { runId });
  const activeStep = steps.find((step) => step.status === "running") ?? steps.find((step) => step.status === "pending") ?? steps[steps.length - 1];
  const completedSteps = steps.filter((step) => step.status === "ok" || step.status === "skipped").length;
  const lastRegression = regressions[regressions.length - 1];
  const provider = session.currentSprint?.provider ?? session.provider ?? "jira";
  const primaryRepo = session.projectSetup.repositories[0];

  return (
    <Screen
      chrome="app"
      title="Executando sprint"
      subtitle={
        route.params.mode === "all"
          ? "Sprint inteira"
          : route.params.mode === "mine"
            ? "Apenas seus itens"
            : `${route.params.itemKeys.length} item(s) selecionado(s)`
      }
      scroll={false}
      footer={
        done ? (
          <Button title={failed ? "Ver detalhes da falha" : "Ver resultado"} onPress={goToResult} />
        ) : (
          <View style={styles.footerProgress}>
            <View style={styles.progressBar}>
              <View style={[styles.progressFill, { width: `${Math.round(progress * 100)}%` }]} />
            </View>
            <Text style={styles.iterTag}>
              round {iteration} / {maxIterations} - {Math.round(progress * 100)}%
            </Text>
          </View>
        )
      }
    >
      <ScrollView ref={scrollRef} contentContainerStyle={styles.runBoard}>
        <Card style={styles.stepsPane}>
          <View style={styles.paneHeader}>
            <Text style={styles.sectionTitle}>Fluxo de execucao (10 passos)</Text>
            <Text style={styles.sectionMeta}>{completedSteps}/10 completos</Text>
          </View>
          <View style={styles.stepList}>
            {steps.map((step) => (
              <StepRow key={step.num} num={step.num} name={STEP_LABELS[step.num]} status={step.status} message={step.message} />
            ))}
          </View>
        </Card>

        <View style={styles.activityPane}>
          <Card style={styles.activityCard}>
            <View style={styles.paneHeader}>
              <View>
                <Text style={styles.sectionTitle}>Atividade atual</Text>
                <Text style={styles.activityTitle}>
                  {activeStep ? STEP_LABELS[activeStep.num] : "Aguardando eventos"}
                </Text>
              </View>
              <Text style={styles.timer}>{runId ? runId.slice(0, 10) : "iniciando"}</Text>
            </View>
            <View style={styles.evidenceStrip}>
              {(evidence.length ? evidence.slice(-3) : placeholderEvidence).map((shot) => (
                <View key={`${shot.url}-${shot.name}`} style={styles.shotCard}>
                  {shot.url ? (
                    <Image source={{ uri: shot.url }} style={styles.evidence} />
                  ) : (
                    <View style={styles.evidencePlaceholder}>
                      <Text style={styles.placeholderText}>{shot.label}</Text>
                    </View>
                  )}
                  <Text style={styles.shotLabel} numberOfLines={1}>{shot.label}</Text>
                </View>
              ))}
            </View>
          </Card>

          <Card style={styles.logCard}>
            <View style={styles.paneHeader}>
              <Text style={styles.sectionTitle}>LOG</Text>
              <Text style={styles.sectionMeta}>{logs.length} eventos</Text>
            </View>
            <View style={styles.logBox}>
              {logs.length === 0 ? (
                <Text style={styles.logEmpty}>aguardando eventos...</Text>
              ) : (
                logs.slice(-12).map((line, index) => (
                  <Text key={`${index}-${line}`} style={styles.logLine}>
                    {line}
                  </Text>
                ))
              )}
            </View>
          </Card>
        </View>

        <Card style={styles.contextPane}>
          <Text style={styles.sectionTitle}>Contexto</Text>
          <ContextRow label="Branch" value={renderPattern(session.projectSetup.branchPattern, route.params.itemKeys[0])} />
          <ContextRow label="Repositorio" value={primaryRepo?.repoPath || "nao configurado"} />
          <ContextRow label="Provider" value={provider} />
          <ContextRow label="Executor" value="SendSprint Agent" />
          <ContextRow label="Modelo" value="GPT-4o / local policy" />

          {lastRegression ? (
            <View style={[styles.regBox, lastRegression.status === "ok" ? styles.regOk : styles.regFail]}>
              <Text style={styles.regTitle}>Regressao round {lastRegression.iteration}</Text>
              <Text style={styles.regText}>
                {lastRegression.status === "ok"
                  ? "Todos os testes passaram."
                  : `${lastRegression.failingTests.length} falha(s) pendente(s).`}
              </Text>
            </View>
          ) : null}

          {prUrl ? (
            <View style={[styles.prBox, failed ? styles.prFailed : styles.prOk]}>
              <Text style={styles.prTitle}>{failed ? "Entrega falhou" : "PR criado"}</Text>
              <Text style={styles.prUrl}>{prUrl}</Text>
            </View>
          ) : null}

          <Button title="Ver detalhes da execucao" variant="secondary" onPress={goToResult} disabled={!runId} />
        </Card>
      </ScrollView>
    </Screen>
  );
};

const ContextRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.contextRow}>
    <Text style={styles.contextLabel}>{label}</Text>
    <Text style={styles.contextValue} numberOfLines={2}>{value}</Text>
  </View>
);

const placeholderEvidence: EvidenceShot[] = [
  { name: "mapper", iteration: 1, label: "Arquitetura", url: "" },
  { name: "tests", iteration: 1, label: "Testes", url: "" },
  { name: "pr", iteration: 1, label: "PR", url: "" },
];

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

const renderPattern = (pattern: string, itemKey?: string): string => {
  const key = itemKey || "ITEM-1";
  return pattern.replace("{item_key}", key).replace("{slug}", "task");
};

const styles = StyleSheet.create({
  runBoard: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    paddingBottom: 18,
  },
  stepsPane: {
    width: 260,
    minHeight: 520,
  },
  activityPane: {
    flex: 1,
    minWidth: 520,
    gap: 12,
  },
  contextPane: {
    width: 250,
    minHeight: 520,
    gap: 12,
  },
  paneHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  sectionTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  sectionMeta: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  stepList: {
    gap: 2,
    marginTop: 8,
  },
  activityCard: {
    minHeight: 190,
  },
  activityTitle: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 4,
    fontFamily: theme.fontSans,
  },
  timer: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontMono,
  },
  evidenceStrip: {
    flexDirection: "row",
    gap: 10,
    marginTop: 12,
  },
  shotCard: {
    flex: 1,
    minWidth: 130,
    gap: 6,
  },
  evidence: {
    width: "100%",
    height: 110,
    borderRadius: theme.radius,
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  evidencePlaceholder: {
    height: 110,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  shotLabel: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontMono,
  },
  logCard: {
    minHeight: 300,
  },
  logBox: {
    backgroundColor: "#f8fafc",
    borderRadius: theme.radius,
    padding: 10,
    borderWidth: 1,
    borderColor: theme.border,
    minHeight: 230,
    gap: 4,
    marginTop: 10,
  },
  logEmpty: {
    color: theme.textMuted,
    fontFamily: theme.fontMono,
    fontSize: 12,
  },
  logLine: {
    color: theme.text,
    fontFamily: theme.fontMono,
    fontSize: 11,
    lineHeight: 16,
  },
  contextRow: {
    gap: 4,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  contextLabel: {
    color: theme.textMuted,
    fontSize: 10,
    textTransform: "uppercase",
    fontFamily: theme.fontSans,
  },
  contextValue: {
    color: theme.text,
    fontSize: 12,
    lineHeight: 17,
    fontFamily: theme.fontSans,
  },
  regBox: {
    padding: 10,
    borderRadius: theme.radius,
    borderWidth: 1,
  },
  regOk: {
    backgroundColor: "rgba(22,163,74,0.08)",
    borderColor: "rgba(22,163,74,0.24)",
  },
  regFail: {
    backgroundColor: "rgba(220,38,38,0.08)",
    borderColor: "rgba(220,38,38,0.24)",
  },
  regTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  regText: {
    color: theme.textMuted,
    fontSize: 11,
    lineHeight: 16,
    marginTop: 4,
    fontFamily: theme.fontSans,
  },
  prBox: {
    padding: 10,
    borderRadius: theme.radius,
    borderWidth: 1,
  },
  prOk: {
    backgroundColor: "rgba(22,163,74,0.08)",
    borderColor: theme.success,
  },
  prFailed: {
    backgroundColor: "rgba(220,38,38,0.08)",
    borderColor: theme.danger,
  },
  prTitle: {
    color: theme.text,
    fontWeight: "700",
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  prUrl: {
    color: theme.primary,
    fontFamily: theme.fontMono,
    fontSize: 11,
    marginTop: 4,
  },
  footerProgress: {
    width: 260,
  },
  progressBar: {
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.surfaceAlt,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: theme.primary,
  },
  iterTag: {
    color: theme.textMuted,
    fontFamily: theme.fontMono,
    fontSize: 11,
    textAlign: "center",
    marginTop: 6,
  },
});
