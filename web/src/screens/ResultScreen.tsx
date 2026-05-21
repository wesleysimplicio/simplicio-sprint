import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import type { ControlPlaneRunDetail, DashboardSnapshot, RunStatus } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Result">;
type Rt = RouteProp<RootStackParamList, "Result">;

export const ResultScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const route = useRoute<Rt>();
  const { api, session } = useSession();
  const [run, setRun] = useState<RunStatus | null>(null);
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [detail, setDetail] = useState<ControlPlaneRunDetail | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [next, controlDetail] = await Promise.all([
          api.getRunDashboard(route.params.runId),
          api.getControlPlaneRun(route.params.runId).catch(() => null),
        ]);
        setSnapshot(next);
        setRun(next.run);
        setDetail(controlDetail);
      } catch {
        try {
          setRun(await api.getRun(route.params.runId));
        } catch {
          // ignore
        }
      }
    })();
  }, []);

  const failed = run?.failed ?? false;
  const headline = failed ? "Entrega falhou" : "Execucao concluida com sucesso";
  const deployTargets = Array.from(
    new Set(
      session.projectSetup.repositories
        .map((repository) => repository.deployTargetBranch.trim())
        .filter(Boolean),
    ),
  );

  const reviewState = failed
    ? "Corrija os bloqueios antes de review humana."
    : run?.pr_url
      ? "PR criado. Revisao humana pronta para assumir."
      : "Run finalizada sem PR publicado; revisar artefatos e logs.";
  const deployState = failed
    ? "Deploy bloqueado."
    : deployTargets.length > 0
      ? `Aguardando envio para ${deployTargets.join(", ")}.`
      : "Branch de deploy ainda nao configurada.";

  const topCards = [
    {
      label: "Pull Request",
      value: run?.pr_url ? "Pronto" : failed ? "Bloqueado" : "Pendente",
      note: run?.pr_url ?? "A run ainda nao publicou PR.",
      tone: run?.pr_url ? "success" : failed ? "danger" : "default",
    },
    {
      label: "Review Humana",
      value: failed ? "Necessaria" : "Liberada",
      note: reviewState,
      tone: failed ? "warning" : "primary",
    },
    {
      label: "Handoff para Deploy",
      value: failed ? "Bloqueado" : "Aguardando",
      note: deployState,
      tone: failed ? "danger" : "default",
    },
  ] as const;

  const durationLabel = useMemo(() => {
    if (!run?.started_at || !run?.finished_at) return "-";
    const start = Date.parse(run.started_at);
    const finish = Date.parse(run.finished_at);
    if (Number.isNaN(start) || Number.isNaN(finish) || finish < start) return "-";
    const seconds = Math.round((finish - start) / 1000);
    return `${seconds}s`;
  }, [run?.finished_at, run?.started_at]);

  return (
    <Screen
      chrome="app"
      eyebrow="Web 10 - Run Result"
      title={headline}
      subtitle={run?.summary ?? `run_id ${route.params.runId} - ${run?.state ?? "carregando..."}`}
      scroll={false}
      footer={
        <View style={{ gap: 10 }}>
          {run?.pr_url ? (
            <Button title="Abrir PR" onPress={() => Linking.openURL(run.pr_url!)} icon="->" />
          ) : null}
          <Button title="Voltar para o inicio" variant="secondary" onPress={() => nav.popToTop()} />
        </View>
      }
    >
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.handoffGrid}>
          {topCards.map((card) => (
            <Card key={card.label} style={styles.handoffCard}>
              <Text style={styles.label}>{card.label}</Text>
              <Text
                style={[
                  styles.value,
                  card.tone === "success" && { color: theme.success },
                  card.tone === "warning" && { color: theme.warning },
                  card.tone === "primary" && { color: theme.primary },
                  card.tone === "danger" && { color: theme.danger },
                ]}
              >
                {card.value}
              </Text>
              <Text style={styles.note}>{card.note}</Text>
            </Card>
          ))}
        </View>

        <View style={styles.metrics}>
          <MetricCard label="Status" value={run?.state ?? "-"} tone={failed ? "danger" : "success"} />
          <MetricCard
            label="Readiness"
            value={detail?.quality_gate?.verdict ?? (snapshot ? "Disponivel" : "Carregando")}
            tone="primary"
          />
          <MetricCard
            label="Evidencias"
            value={
              detail?.evidence
                ? String(detail.evidence.total_items)
                : snapshot
                  ? String(snapshot.evidence.length)
                  : "-"
            }
          />
          <MetricCard label="Duracao" value={durationLabel} />
        </View>

        <Card>
          <Text style={styles.label}>RESUMO DA ENTREGA</Text>
          <Text style={styles.value}>{run?.summary ?? "-"}</Text>
          {snapshot?.blockers.length ? (
            <View style={styles.blockerList}>
              {snapshot.blockers.map((item) => (
                <Text key={item} style={[styles.note, styles.blocker]}>
                  - {item}
                </Text>
              ))}
            </View>
          ) : (
            <Text style={styles.note}>Sem bloqueios adicionais registrados no fechamento desta run.</Text>
          )}
        </Card>

        {detail?.quality_gate ? (
          <Card>
            <Text style={styles.label}>QUALITY GATE</Text>
            <Text style={styles.value}>{detail.quality_gate.verdict}</Text>
            {detail.quality_gate.checks.map((check) => (
              <Text
                key={check.check_name}
                style={[
                  styles.checkRow,
                  { color: check.passed ? theme.success : theme.danger },
                ]}
              >
                {check.check_name}: {check.passed ? "ok" : "failed"} - {check.details}
              </Text>
            ))}
          </Card>
        ) : null}

        {detail?.evidence?.items?.length ? (
          <Card>
            <Text style={styles.label}>EVIDENCE BUNDLE</Text>
            {detail.evidence.items.map((item) => (
              <Text key={`${item.type}-${item.path}`} style={[styles.mono, styles.evidenceRow]}>
                {item.label} - {item.type} - {item.path}
              </Text>
            ))}
          </Card>
        ) : null}

        {run?.pr_url ? (
          <Card>
            <Text style={styles.label}>PULL REQUEST</Text>
            <Text style={[styles.value, styles.mono]}>{run.pr_url}</Text>
          </Card>
        ) : null}

        <Card>
          <Text style={styles.label}>METADADOS</Text>
          <Text style={[styles.value, styles.mono]}>sprint: {run?.sprint_id ?? "-"}</Text>
          <Text style={[styles.value, styles.mono]}>provider: {run?.provider ?? "-"}</Text>
          <Text style={[styles.value, styles.mono]}>iniciado: {run?.started_at?.slice(0, 19) ?? "-"}</Text>
          <Text style={[styles.value, styles.mono]}>terminado: {run?.finished_at?.slice(0, 19) ?? "-"}</Text>
        </Card>
      </ScrollView>
    </Screen>
  );
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  tone?: "default" | "primary" | "success" | "danger";
}> = ({ label, value, tone = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.label}>{label}</Text>
    <Text
      style={[
        styles.value,
        tone === "primary" && { color: theme.primary },
        tone === "success" && { color: theme.success },
        tone === "danger" && { color: theme.danger },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const styles = StyleSheet.create({
  scroll: {
    gap: 12,
    paddingBottom: 24,
  },
  handoffGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  handoffCard: {
    flex: 1,
    minWidth: 220,
  },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  metricCard: {
    flex: 1,
    minWidth: 180,
  },
  label: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  value: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "600",
    marginTop: 4,
  },
  note: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 8,
  },
  mono: {
    fontFamily: theme.fontMono,
    fontSize: 13,
    fontWeight: "400",
  },
  blockerList: {
    marginTop: 6,
    gap: 4,
  },
  blocker: {
    color: theme.danger,
  },
  checkRow: {
    fontSize: 13,
    fontWeight: "500",
    marginTop: 6,
  },
  evidenceRow: {
    marginTop: 6,
    color: theme.text,
  },
});
