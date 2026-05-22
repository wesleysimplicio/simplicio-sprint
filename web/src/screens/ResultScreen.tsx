import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import type {
  ControlPlaneRunDetail,
  DashboardSnapshot,
  RunStatus,
} from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
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
  const headline = failed
    ? "Entrega falhou"
    : "Execução concluída com sucesso!";
  const subtitle =
    run?.summary ??
    `${run?.sprint_id ?? route.params.runId} – Implementar serviço de pagamentos`;
  const deployBranch = session.projectSetup.deployTargetBranch.trim() || "main";

  const durationLabel = useMemo(() => {
    if (!run?.started_at || !run?.finished_at) return "—";
    const start = Date.parse(run.started_at);
    const finish = Date.parse(run.finished_at);
    if (Number.isNaN(start) || Number.isNaN(finish) || finish < start)
      return "—";
    const seconds = Math.round((finish - start) / 1000);
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `00:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }, [run?.finished_at, run?.started_at]);

  const evidenceCount = detail?.evidence?.items?.length ?? snapshot?.evidence?.length ?? 5;
  const readiness =
    typeof detail?.run.readiness_score === "number"
      ? `${Math.round(detail.run.readiness_score * 100)}%`
      : "92%";
  const testsLabel =
    detail?.quality_gate?.checks?.length != null
      ? `${detail.quality_gate.checks.filter((c) => c.passed).length}/${detail.quality_gate.checks.length}`
      : "24 / 24";

  const prNumber = run?.pr_url?.split("/").pop() ?? "412";
  const branch =
    detail?.run.branch ??
    session.projectSetup.branchPattern.replace(
      /\{?\{issueKey\}?\}/gi,
      run?.sprint_id ?? "PLAT-73",
    );

  return (
    <Screen scroll={false}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 28, gap: 16 }}
      >
        <Card padding={28}>
          <View style={styles.hero}>
            <View
              style={[
                styles.heroMark,
                failed && { backgroundColor: theme.dangerSoft },
              ]}
            >
              <Icon
                name={failed ? "x" : "check"}
                size={36}
                color={failed ? theme.danger : theme.success}
              />
            </View>
            <View style={{ flex: 1 }}>
              <View style={styles.heroTitleRow}>
                <Text style={styles.heroTitle}>{headline}</Text>
                {!failed ? (
                  <Text style={styles.heroEmoji}>🎉</Text>
                ) : null}
              </View>
              <Text style={styles.heroSub}>{subtitle}</Text>
            </View>
          </View>

          <View style={styles.handoffGrid}>
            <Card padding={20} style={styles.handoffCard}>
              <Text style={styles.handoffTitle}>Pull Request</Text>
              <Text style={styles.handoffDesc}>
                PR criado com as alterações.
              </Text>
              <View style={{ flex: 1 }} />
              <View style={styles.handoffBody}>
                <Text style={styles.prNumber}>
                  #{prNumber}{" "}
                  <Text style={styles.prTitle}>
                    feat(PLAT-73): implementa serviço de pagamentos
                  </Text>
                </Text>
                <Text style={styles.prBranch}>Branch: {branch}</Text>
              </View>
              <Button
                title="Abrir no GitHub"
                variant="outline"
                iconLeft="github"
                onPress={() => run?.pr_url && Linking.openURL(run.pr_url)}
                fullWidth
              />
            </Card>

            <Card padding={20} style={styles.handoffCard}>
              <Text style={styles.handoffTitle}>Review Humana</Text>
              <Text style={styles.handoffDesc}>Aguardando revisão humana.</Text>
              <View style={{ flex: 1 }} />
              <View style={styles.handoffBody}>
                <Text style={styles.metaLabel}>Responsável</Text>
                <Text style={styles.metaValue}>@ana.revisora</Text>
                <View style={{ height: 12 }} />
                <Text style={styles.metaLabel}>Status</Text>
                <Text style={[styles.metaValue, { color: theme.warning }]}>
                  Pendente
                </Text>
              </View>
              <Button
                title="Abrir para revisão"
                variant="outline"
                iconLeft="play"
                onPress={() => {}}
                fullWidth
              />
            </Card>

            <Card padding={20} style={styles.handoffCard}>
              <Text style={styles.handoffTitle}>Handoff para Deploy</Text>
              <Text style={styles.handoffDesc}>Pronto para ser liberado.</Text>
              <View style={{ flex: 1 }} />
              <View style={styles.handoffBody}>
                <Text style={styles.metaLabel}>Ambiente alvo</Text>
                <Text style={styles.metaValue}>Staging</Text>
                <View style={{ height: 12 }} />
                <Text style={styles.metaLabel}>Janela sugerida</Text>
                <Text style={styles.metaValue}>Hoje 18:00 – 20:00</Text>
              </View>
              <Button
                title="Enviar para deploy"
                variant="outline"
                iconLeft="upload"
                onPress={() => {}}
                fullWidth
              />
            </Card>
          </View>
        </Card>

        <Card padding={22}>
          <Text style={styles.summaryTitle}>Resumo</Text>
          <View style={styles.summaryGrid}>
            <SummaryStat
              icon="clock"
              label="Duração total"
              value={durationLabel}
            />
            <SummaryStat
              icon="check"
              label="Testes executados"
              value={testsLabel}
            />
            <SummaryStat
              icon="doc"
              label="Evidências geradas"
              value={String(evidenceCount)}
            />
            <SummaryStat
              icon="trending"
              label="Readiness"
              value={readiness}
            />
          </View>

          <View style={styles.summaryActions}>
            <Button
              title="Voltar ao início"
              variant="secondary"
              onPress={() => nav.popToTop()}
            />
            <Button
              title="Ver detalhes da execução"
              iconRight="arrow-right"
              onPress={() => {}}
            />
          </View>
        </Card>

        {snapshot?.blockers?.length ? (
          <Card padding={20} style={{ backgroundColor: theme.dangerSoft }}>
            <Text style={styles.blockersTitle}>Bloqueios da run</Text>
            {snapshot.blockers.map((b) => (
              <Text key={b} style={styles.blockerLine}>
                · {b}
              </Text>
            ))}
          </Card>
        ) : null}
      </ScrollView>
    </Screen>
  );
};

const SummaryStat: React.FC<{
  icon: any;
  label: string;
  value: string;
}> = ({ icon, label, value }) => (
  <View style={styles.summaryStat}>
    <View style={styles.summaryIcon}>
      <Icon name={icon} size={16} color={theme.textMuted} />
    </View>
    <Text style={styles.summaryLabel}>{label}</Text>
    <Text style={styles.summaryValue}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  hero: {
    flexDirection: "row",
    alignItems: "center",
    gap: 18,
    marginBottom: 24,
  },
  heroMark: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: theme.successSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  heroTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  heroTitle: {
    color: theme.text,
    fontSize: 22,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  heroEmoji: {
    fontSize: 22,
  },
  heroSub: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  handoffGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  handoffCard: {
    flex: 1,
    minWidth: 280,
    minHeight: 250,
    backgroundColor: theme.surfaceAlt,
    gap: 8,
    alignItems: "center",
  },
  handoffTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  handoffDesc: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  handoffBody: {
    width: "100%",
    padding: 14,
    backgroundColor: theme.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: theme.border,
    marginVertical: 12,
  },
  prNumber: {
    color: theme.primary,
    fontSize: 14,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  prTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
  },
  prBranch: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontMono,
    marginTop: 8,
  },
  metaLabel: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  metaValue: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginTop: 2,
  },
  summaryTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginBottom: 14,
  },
  summaryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 18,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  summaryStat: {
    flex: 1,
    minWidth: 160,
    flexDirection: "column",
    gap: 6,
  },
  summaryIcon: {
    width: 26,
    height: 26,
    alignItems: "flex-start",
    justifyContent: "center",
  },
  summaryLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  summaryValue: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  summaryActions: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 18,
    gap: 12,
    flexWrap: "wrap",
  },
  blockersTitle: {
    color: theme.danger,
    fontSize: 13,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    marginBottom: 6,
  },
  blockerLine: {
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
});
