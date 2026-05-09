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
  5: "Testes (unit + E2E)",
  6: "Segurança",
  7: "Fix loop",
  8: "Commit + push",
  9: "Cria PR",
  10: "Revisa e entrega",
};

type StepState = { num: number; status: "pending" | "running" | "ok" | "skipped" | "failed"; message?: string };

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
  const [evidence, setEvidence] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [prUrl, setPrUrl] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.startRun({
          provider: session.provider ?? "jira",
          sprint_id: route.params.sprintId,
          mode: route.params.mode,
          item_keys: route.params.itemKeys,
        });
        setRunId(res.run_id);
        subRef.current = subscribeToRun(api.eventsUrl(res.run_id), {
          onEvent: handleEvent,
          onError: (e) => console.warn("sse error", e),
        });
      } catch (e) {
        setLogs((l) => [...l, "✗ falha ao iniciar: " + String((e as Error).message ?? e)]);
        setFailed(true);
      }
    })();
    return () => subRef.current?.close();
  }, []);

  const handleEvent = (ev: RunEvent) => {
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
    } else if (ev.type === "log") {
      setLogs((l) => [...l, ev.message ?? ""]);
    } else if (ev.type === "evidence") {
      const path = ev.evidence_path ?? "";
      const name = path.split("/").pop() ?? path;
      if (runId) setEvidence((e) => [...e, name]);
      setLogs((l) => [...l, "📸 evidência: " + name]);
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

  return (
    <Screen
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
          <View style={styles.progressBar}>
            <View style={[styles.progressFill, { width: `${Math.round(progress * 100)}%` }]} />
          </View>
        )
      }
    >
      <ScrollView ref={scrollRef} contentContainerStyle={{ paddingBottom: 24, gap: 4 }}>
        {steps.map((s) => (
          <StepRow key={s.num} num={s.num} name={STEP_LABELS[s.num]} status={s.status} message={s.message} />
        ))}

        {evidence.length > 0 && runId ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>EVIDÊNCIAS</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
              {evidence.map((name) => (
                <Image key={name} source={{ uri: api.evidenceUrl(runId, name) }} style={styles.evidence} />
              ))}
            </ScrollView>
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

const styles = StyleSheet.create({
  section: { marginTop: 16, gap: 8 },
  sectionTitle: { color: theme.textMuted, fontSize: 11, letterSpacing: 2, paddingHorizontal: 12 },
  evidence: {
    width: 180,
    height: 110,
    borderRadius: theme.radius,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
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
});
