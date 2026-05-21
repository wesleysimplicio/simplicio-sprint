import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
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

  return (
    <Screen
      chrome="app"
      eyebrow="Web 10 · Resultado"
      title={headline}
      subtitle={run?.summary ?? `run_id ${route.params.runId} · ${run?.state ?? "carregando..."}`}
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
      <ScrollView contentContainerStyle={{ gap: 12 }}>
        <Card>
          <Text style={styles.label}>RESUMO</Text>
          <Text style={styles.value}>{run?.summary ?? "-"}</Text>
        </Card>
        <View style={styles.grid}>
          <Card style={styles.metricCard}>
            <Text style={styles.label}>STATUS</Text>
            <Text style={[styles.value, { color: failed ? theme.danger : theme.success }]}>
              {run?.state ?? "-"}
            </Text>
          </Card>
          <Card style={styles.metricCard}>
            <Text style={styles.label}>READINESS</Text>
            <Text style={styles.value}>{detail?.quality_gate?.verdict ?? (snapshot ? "Disponivel" : "Carregando")}</Text>
          </Card>
          <Card style={styles.metricCard}>
            <Text style={styles.label}>EVIDENCIAS</Text>
            <Text style={styles.value}>
              {detail?.evidence ? String(detail.evidence.total_items) : snapshot ? String(snapshot.evidence.length) : "-"}
            </Text>
          </Card>
        </View>
        {run?.pr_url ? (
          <Card>
            <Text style={styles.label}>PULL REQUEST</Text>
            <Text style={[styles.value, styles.mono]}>{run.pr_url}</Text>
          </Card>
        ) : null}
        <Card>
          <Text style={styles.label}>HANDOFF</Text>
          <Text style={styles.value}>{reviewState}</Text>
          <Text style={[styles.value, styles.deployNote]}>{deployState}</Text>
          {snapshot?.blockers.length ? (
            <View style={{ marginTop: 8, gap: 4 }}>
              {snapshot.blockers.map((item) => (
                <Text key={item} style={[styles.value, styles.blocker]}>
                  {item}
                </Text>
              ))}
            </View>
          ) : null}
        </Card>
        {detail?.quality_gate ? (
          <Card>
            <Text style={styles.label}>QUALITY GATE</Text>
            <Text style={styles.value}>{detail.quality_gate.verdict}</Text>
            {detail.quality_gate.checks.map((check) => (
              <Text
                key={check.check_name}
                style={[
                  styles.value,
                  styles.checkRow,
                  { color: check.passed ? theme.success : theme.danger },
                ]}
              >
                {check.check_name}: {check.passed ? "ok" : "failed"} · {check.details}
              </Text>
            ))}
          </Card>
        ) : null}
        {detail?.evidence?.items?.length ? (
          <Card>
            <Text style={styles.label}>EVIDENCE BUNDLE</Text>
            {detail.evidence.items.map((item) => (
              <Text key={`${item.type}-${item.path}`} style={[styles.value, styles.mono, styles.evidenceRow]}>
                {item.label} · {item.type} · {item.path}
              </Text>
            ))}
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

const styles = StyleSheet.create({
  grid: {
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
  },
  value: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "600",
    marginTop: 4,
  },
  mono: {
    fontFamily: theme.fontMono,
    fontSize: 13,
    fontWeight: "400",
  },
  blocker: {
    color: theme.danger,
  },
  deployNote: {
    fontSize: 14,
    fontWeight: "500",
  },
  checkRow: {
    fontSize: 13,
    fontWeight: "500",
  },
  evidenceRow: {
    marginTop: 6,
  },
});
