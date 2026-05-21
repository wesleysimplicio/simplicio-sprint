import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import { Button } from "../components/Button";
import { Screen } from "../components/Screen";
import { StepRow } from "../components/StepRow";
import type { RootStackParamList } from "../navigation";
import { subscribeToRun, type Subscription } from "../api/sse";
import type { RunEvent } from "../api/types";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Run">;
type Rt = RouteProp<RootStackParamList, "Run">;

const STEP_LABELS: Record<number, string> = {
  1: "Lê a sprint",
  2: "Mapeia arquitetura",
  3: "Dev: install + build",
  4: "Lint",
  5: "Testes (unit + E2E + regressão)",
  6: "Segurança",
  7: "Fix loop",
  8: "Commit + push",
  9: "Cria PR",
  10: "Revisa e entrega",
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
          repo_path:
            primaryRepo && !looksRemote(primaryRepo) && !session.projectSetup.repositories.length
              ? primaryRepo
              : undefined,
          project_setup: session.projectSetup.repositories.length ? session.projectSetup : null,
        });
        setRunId(res.run_id);
        subRef.current = subscribeToRun(api.eventsUrl(res.run_id), {
          onEvent: (ev) => handleEvent(ev, res.run_id),
          onError: (e) => console.warn("sse error", e),
        });
      } catch (e) {
        setLogs((l) => [...l, "✗ falha ao iniciar: " + String((e as Error).message ?? e)]);
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
      setLogs((l) => [...l, `↻ ${ev.message ?? `round ${ev.iteration}`}`]);
    } else if (ev.type === "regression") {
      if (typeof ev.iteration === "number") {
        setRegressions((r) => [
          ...r.filter((x) => x.iteration !== ev.iteration),
          {
            iteration: ev.iteration!,
            status: (ev.status === "ok" ? "ok" : "failed") as "ok" | "failed",
            failingTests: ev.failing_tests ?? [],
          },
        ]);
      }
    } else if (ev.type === "log") {
      setLogs((l) => [...l, ev.message ?? ""]);
    } else if (ev.type === "evidence") {
      const path = ev.evidence_path ?? "";
      const name = path.split("/").pop() ?? path;
      const iter = ev.iteration ?? 1;
      setEvidence((e) => [
        ...e,
        {
          name,
          iteration: iter,
          label: ev.evidence_label ?? name,
          url: api.evidenceUrl(currentRunId, name),
        },
      ]);
      setLogs((l) => [...l, `📸 ${ev.evidence_label ?? name}`]);
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
      setLogs((l) => [...l, "✗ erro: " + (ev.message ?? "")]);
    }
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
  };

  const goToResult = () => runId && nav.navigate("Result", { runId });

  const evidenceByIteration = groupBy(evidence, (e) => e.iteration);
  const lastRegression = regressions[regressions.length - 1];

  return (
    <Screen
      chrome="app"
      eyebrow="Web 09 · Live Run"
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
          <View>
            <View style={styles.progressBar}>
              <View style={[styles.progressFill, { width: `${Math.round(progress * 100)}%` }]} />
            </View>
            <Text style={styles.iterTag}>
              ↻ round {iteration} / {maxIterations} · {Math.round(progress * 100)}%
            </Text>
          </View>
        )
      }
    >
      <ScrollView ref={scrollRef} contentContainerStyle={{ paddingBottom: 24, gap: 4 }}>
        {steps.map((s) => (
          <StepRow key={s.num} num={s.num} name={STEP_LABELS[s.num]} status={s.status} message={s.message} />
        ))}

        {regressions.length > 0 ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>REGRESSÃO</Text>
            <View style={{ paddingHorizontal: 12, gap: 8 }}>
              {regressions.map((r) => (
                <View
                  key={r.iteration}
                  style={[
                    styles.regBox,
                    r.status === "ok" ? styles.regOk : styles.regFail,
                  ]}
                >
                  <View style={styles.regHead}>
                    <Text
                      style={[
                        styles.regBadge,
                        r.status === "ok" ? styles.regBadgeOk : styles.regBadgeFail,
                      ]}
                    >
                      ROUND {r.iteration}
                    </Text>
                    <Text
                      style={[
                        styles.regStatus,
                        { color: r.status === "ok" ? theme.success : theme.danger },
                      ]}
                    >
                      {r.status === "ok" ? "✓ verde — todos passaram" : `✗ ${r.failingTests.length} falhas`}
                    </Text>
                  </View>
                  {r.failingTests.length > 0 ? (
                    <View style={{ marginTop: 6, gap: 2 }}>
                      {r.failingTests.map((t) => (
                        <Text key={t} style={styles.failingTest}>
                          ✗ {t}
                        </Text>
                      ))}
                    </View>
                  ) : null}
                </View>
              ))}
            </View>
          </View>
        ) : null}

        {evidence.length > 0 ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>EVIDÊNCIAS</Text>
            {Array.from(evidenceByIteration.entries()).map(([iter, shots]) => (
              <View key={iter} style={{ marginBottom: 14 }}>
                <Text style={styles.iterHeader}>round {iter}</Text>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={{ gap: 10, paddingHorizontal: 12 }}
                >
                  {shots.map((s) => (
                    <View key={s.url + s.name} style={styles.shotCard}>
                      <Image source={{ uri: s.url }} style={styles.evidence} />
                      <Text style={styles.shotLabel} numberOfLines={2}>
                        {s.label}
                      </Text>
                    </View>
                  ))}
                </ScrollView>
              </View>
            ))}
          </View>
        ) : null}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>LOG</Text>
          <View style={styles.logBox}>
            {logs.length === 0 ? (
              <Text style={styles.logEmpty}>aguardando eventos…</Text>
            ) : (
              logs.map((l, i) => (
                <Text key={i} style={styles.logLine}>
                  {l}
                </Text>
              ))
            )}
          </View>
        </View>

        {prUrl ? (
          <View style={[styles.prBox, failed ? styles.prFailed : styles.prOk]}>
            <Text style={styles.prTitle}>{failed ? "✗ entrega falhou" : "✓ PR criado"}</Text>
            <Text style={styles.prUrl}>{prUrl}</Text>
          </View>
        ) : null}
      </ScrollView>
    </Screen>
  );
};

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

function groupBy<T, K extends string | number>(arr: T[], keyOf: (t: T) => K): Map<K, T[]> {
  const m = new Map<K, T[]>();
  for (const item of arr) {
    const k = keyOf(item);
    const list = m.get(k);
    if (list) list.push(item);
    else m.set(k, [item]);
  }
  return m;
}

const styles = StyleSheet.create({
  section: { marginTop: 16, gap: 8 },
  sectionTitle: { color: theme.textMuted, fontSize: 11, letterSpacing: 2, paddingHorizontal: 12 },
  iterHeader: {
    color: theme.primarySoft,
    fontFamily: theme.fontMono,
    fontSize: 12,
    paddingHorizontal: 12,
    marginBottom: 6,
    letterSpacing: 1,
  },
  shotCard: { width: 220, gap: 6 },
  evidence: {
    width: 220,
    height: 140,
    borderRadius: theme.radius,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
  shotLabel: { color: theme.textMuted, fontSize: 12, fontFamily: theme.fontMono },
  logBox: {
    backgroundColor: theme.bgDeep,
    borderRadius: theme.radius,
    padding: 12,
    borderWidth: 1,
    borderColor: theme.border,
    minHeight: 100,
    gap: 4,
    marginHorizontal: 12,
  },
  logEmpty: { color: theme.textMuted, fontFamily: theme.fontMono, fontSize: 12 },
  logLine: { color: theme.text, fontFamily: theme.fontMono, fontSize: 12 },
  prBox: {
    marginTop: 14,
    marginHorizontal: 12,
    padding: 14,
    borderRadius: theme.radius,
    borderWidth: 1,
  },
  prOk: { backgroundColor: "rgba(52, 211, 153, 0.12)", borderColor: theme.success },
  prFailed: { backgroundColor: "rgba(248, 113, 113, 0.12)", borderColor: theme.danger },
  prTitle: { color: theme.text, fontWeight: "700", fontSize: 14 },
  prUrl: { color: theme.primarySoft, fontFamily: theme.fontMono, fontSize: 12, marginTop: 4 },
  progressBar: {
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.surface,
    overflow: "hidden",
  },
  progressFill: { height: "100%", backgroundColor: theme.primary },
  iterTag: {
    color: theme.textMuted,
    fontFamily: theme.fontMono,
    fontSize: 11,
    textAlign: "center",
    marginTop: 8,
    letterSpacing: 1,
  },
  regBox: {
    padding: 12,
    borderRadius: theme.radius,
    borderWidth: 1,
  },
  regOk: { backgroundColor: "rgba(52, 211, 153, 0.10)", borderColor: theme.success },
  regFail: { backgroundColor: "rgba(248, 113, 113, 0.10)", borderColor: theme.danger },
  regHead: { flexDirection: "row", alignItems: "center", gap: 10 },
  regBadge: {
    fontFamily: theme.fontMono,
    fontSize: 11,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
    overflow: "hidden",
    color: "white",
  },
  regBadgeOk: { backgroundColor: theme.success },
  regBadgeFail: { backgroundColor: theme.danger },
  regStatus: { fontWeight: "700", fontSize: 13, flex: 1 },
  failingTest: {
    color: theme.danger,
    fontFamily: theme.fontMono,
    fontSize: 12,
    paddingLeft: 8,
  },
});
