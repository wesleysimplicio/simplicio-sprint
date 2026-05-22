import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
import { Screen } from "../components/Screen";
import type {
  AuthStatus,
  ControlPlaneRunDetail,
  ControlPlaneRunSummary,
} from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Dashboard">;

export const DashboardScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [selected, setSelected] = useState<ControlPlaneRunDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void load();
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [authStatus, runList] = await Promise.all([
        api.authStatus(),
        api.listControlPlaneRuns(),
      ]);
      setAuth(authStatus);
      setRuns(runList);
    } finally {
      setLoading(false);
    }
  };

  const totals = useMemo(() => {
    const total = runs.length;
    const running = runs.filter((run) => run.state === "running").length;
    const blocked = runs.filter((run) => run.failed || run.state === "failed").length;
    const done = runs.filter((run) => run.state === "done").length;
    return { total, running, blocked, done };
  }, [runs]);

  const providerLabel =
    session.provider === "azuredevops"
      ? "Azure DevOps"
      : session.provider === "jira"
        ? "Jira"
        : auth?.default_provider === "azuredevops"
          ? "Azure DevOps"
          : "Jira";

  if (loading) {
    return (
      <Screen>
        <View style={styles.centerLoading}>
          <ActivityIndicator color={theme.primary} />
          <Text style={styles.centerLoadingText}>Carregando shell operacional…</Text>
        </View>
      </Screen>
    );
  }

  if (!session.currentSprint) {
    return (
      <Screen>
        <View style={styles.emptyOuter}>
          <Card style={styles.emptyHero} padding={48}>
            <View style={styles.compassOrb}>
              <Icon name="compass" size={56} color={theme.primary} />
            </View>
            <Text style={styles.emptyHeroTitle}>
              Pronto para orquestrar seu próximo sprint
            </Text>
            <Text style={styles.emptyHeroText}>
              Conecte seus provedores, importe um sprint e deixe a IA cuidar
              da execução ponta a ponta.
            </Text>
            <View style={{ height: 8 }} />
            <Button
              title="Iniciar"
              onPress={() => nav.navigate("Provider")}
              iconLeft="play"
              size="lg"
            />
          </Card>

          <View style={styles.emptyQuickGrid}>
            <Card style={styles.quickCard} onPress={() => nav.navigate("ProjectSetup")}>
              <View style={styles.quickIcon}>
                <Icon name="clipboard" size={22} color={theme.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.quickTitle}>Configurar projeto</Text>
                <Text style={styles.quickText}>
                  Defina repositórios, papéis e padrões de branches.
                </Text>
                <View style={styles.quickLinkRow}>
                  <Text style={styles.quickLinkText}>Configurar</Text>
                  <Icon name="arrow-right" size={14} color={theme.primary} />
                </View>
              </View>
            </Card>
            <Card style={styles.quickCard} onPress={() => nav.navigate("Provider")}>
              <View style={styles.quickIcon}>
                <Icon name="link" size={22} color={theme.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.quickTitle}>Conexões</Text>
                <Text style={styles.quickText}>
                  Conecte Jira, Azure DevOps ou GitHub.
                </Text>
                <View style={styles.quickLinkRow}>
                  <Text style={styles.quickLinkText}>Conectar</Text>
                  <Icon name="arrow-right" size={14} color={theme.primary} />
                </View>
              </View>
            </Card>
          </View>
        </View>
      </Screen>
    );
  }

  return (
    <Screen
      title={session.currentSprint.sprintName}
      subtitle={`${providerLabel} · ${session.currentSprint.projectName ?? "projeto"} · sprint importada`}
      actions={
        <Button
          title="Abrir backlog"
          iconRight="arrow-right"
          onPress={() =>
            nav.navigate("SprintDetail", {
              sprintId: session.currentSprint?.sprintId ?? "",
            })
          }
        />
      }
    >
      <View style={styles.metricGrid}>
        <MetricCard label="Runs totais" value={String(totals.total)} />
        <MetricCard
          label="Em execução"
          value={String(totals.running)}
          tone="primary"
        />
        <MetricCard
          label="Bloqueadas"
          value={String(totals.blocked)}
          tone="danger"
        />
        <MetricCard label="Concluídas" value={String(totals.done)} tone="success" />
      </View>

      <Card style={styles.runsCard}>
        <View style={styles.runsHeader}>
          <Text style={styles.runsTitle}>Execuções recentes</Text>
          <Text style={styles.runsMeta}>{runs.length} runs · {providerLabel}</Text>
        </View>
        {runs.length === 0 ? (
          <View style={styles.runsEmpty}>
            <Text style={styles.runsEmptyText}>
              Nenhuma execução registrada ainda. Abra o backlog para iniciar.
            </Text>
          </View>
        ) : (
          <ScrollView style={{ maxHeight: 460 }}>
            {runs.map((run) => (
              <Pressable
                key={run.run_id}
                onPress={() => void openDetail(run.run_id, setSelected, api)}
                style={({ pressed }) => [
                  styles.runRow,
                  pressed && { backgroundColor: theme.surfaceMuted },
                ]}
              >
                <View style={{ flex: 1 }}>
                  <View style={styles.runRowHead}>
                    <Text style={styles.runRowKey}>{run.sprint_id}</Text>
                    <RunStateChip state={run.state} failed={run.failed} />
                  </View>
                  <Text style={styles.runRowTitle} numberOfLines={1}>
                    {run.task ?? run.summary ?? "Run sem título"}
                  </Text>
                  <Text style={styles.runRowMeta}>
                    {run.provider} · passo {run.last_step ?? 0}/10 ·
                    {" "}
                    {Math.round((run.progress ?? 0) * 100)}%
                  </Text>
                </View>
                <Icon name="chevron-right" size={16} color={theme.textMuted} />
              </Pressable>
            ))}
          </ScrollView>
        )}
      </Card>

      <RunDetailModal detail={selected} onClose={() => setSelected(null)} />
    </Screen>
  );
};

const openDetail = async (
  runId: string,
  setSelected: (r: ControlPlaneRunDetail | null) => void,
  api: any,
) => {
  setSelected(await api.getControlPlaneRun(runId));
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  tone?: "default" | "primary" | "success" | "danger";
}> = ({ label, value, tone = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        tone === "primary" && { color: theme.primary },
        tone === "success" && { color: theme.success },
        tone === "danger" && { color: theme.danger },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const RunStateChip: React.FC<{ state: string; failed?: boolean }> = ({
  state,
  failed,
}) => {
  const tone = failed
    ? "danger"
    : state === "done"
      ? "success"
      : state === "running"
        ? "info"
        : "muted";
  const colorBg =
    tone === "danger"
      ? theme.dangerSoft
      : tone === "success"
        ? theme.successSoft
        : tone === "info"
          ? theme.infoSoft
          : theme.surfaceMuted;
  const colorFg =
    tone === "danger"
      ? theme.danger
      : tone === "success"
        ? theme.success
        : tone === "info"
          ? theme.info
          : theme.textMuted;
  return (
    <View style={[styles.runChip, { backgroundColor: colorBg }]}>
      <Text style={[styles.runChipText, { color: colorFg }]}>
        {state.toUpperCase()}
      </Text>
    </View>
  );
};

const RunDetailModal: React.FC<{
  detail: ControlPlaneRunDetail | null;
  onClose: () => void;
}> = ({ detail, onClose }) => (
  <Modal visible={Boolean(detail)} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.modalBackdrop}>
      <View style={styles.modalCard}>
        <View style={styles.modalHead}>
          <View style={{ flex: 1 }}>
            <Text style={styles.modalTitle}>
              {detail?.run.task ?? detail?.run.run_id ?? "Run"}
            </Text>
            <Text style={styles.modalSubtitle}>
              {detail?.run.summary ?? "Sem resumo"}
            </Text>
          </View>
          <Pressable onPress={onClose} style={styles.modalClose}>
            <Icon name="x" size={16} color={theme.textMuted} />
          </Pressable>
        </View>

        <ScrollView style={{ maxHeight: 460 }}>
          <View style={styles.modalSection}>
            <Text style={styles.modalSectionTitle}>Run</Text>
            <Text style={styles.modalBody}>Estado: {detail?.run.state ?? "-"}</Text>
            <Text style={styles.modalBody}>Provider: {detail?.run.provider ?? "-"}</Text>
            <Text style={styles.modalBody}>Branch: {detail?.run.branch ?? "-"}</Text>
          </View>

          <View style={styles.modalSection}>
            <Text style={styles.modalSectionTitle}>Logs</Text>
            {(detail?.logs ?? []).length === 0 ? (
              <Text style={styles.modalBody}>Sem logs capturados.</Text>
            ) : (
              detail?.logs.map((line, idx) => (
                <Text key={idx} style={styles.modalMono}>
                  {line}
                </Text>
              ))
            )}
          </View>
        </ScrollView>
      </View>
    </View>
  </Modal>
);

const styles = StyleSheet.create({
  centerLoading: {
    flex: 1,
    minHeight: 280,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  centerLoadingText: {
    color: theme.textMuted,
    fontSize: 13,
  },
  emptyOuter: {
    flex: 1,
    paddingTop: 18,
    gap: 18,
  },
  emptyHero: {
    minHeight: 360,
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
  },
  compassOrb: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 2,
    borderColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
    ...(Platform.OS === "web"
      ? ({ borderStyle: "dashed" } as any)
      : { borderStyle: "dashed" }),
  },
  emptyHeroTitle: {
    color: theme.text,
    fontSize: 22,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  emptyHeroText: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 20,
    fontFamily: theme.fontSans,
    textAlign: "center",
    maxWidth: 480,
  },
  emptyQuickGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  quickCard: {
    flex: 1,
    minWidth: 280,
    flexDirection: "row",
    gap: 14,
    alignItems: "flex-start",
  },
  quickIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: theme.primaryFaint,
    alignItems: "center",
    justifyContent: "center",
  },
  quickTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  quickText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 18,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  quickLinkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 12,
  },
  quickLinkText: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  metricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
  },
  metricCard: {
    flex: 1,
    minWidth: 180,
  },
  metricLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  metricValue: {
    color: theme.text,
    fontSize: 28,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    marginTop: 6,
  },
  runsCard: {
    gap: 0,
  },
  runsHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingBottom: 12,
    marginBottom: 4,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  runsTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  runsMeta: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  runsEmpty: {
    paddingVertical: 28,
    alignItems: "center",
  },
  runsEmptyText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  runRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  runRowHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  runRowKey: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontMono,
  },
  runRowTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  runRowMeta: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  runChip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  runChipText: {
    fontSize: 10,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    letterSpacing: 0.4,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.45)",
    justifyContent: "center",
    padding: 24,
  },
  modalCard: {
    width: "100%",
    maxWidth: 560,
    alignSelf: "center",
    backgroundColor: theme.surface,
    borderRadius: 14,
    padding: 22,
    gap: 14,
  },
  modalHead: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 14,
  },
  modalClose: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.surfaceMuted,
  },
  modalTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  modalSubtitle: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  modalSection: {
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    gap: 4,
  },
  modalSectionTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  modalBody: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  modalMono: {
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontMono,
    lineHeight: 18,
  },
});
