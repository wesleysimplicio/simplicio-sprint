import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type {
  ControlPlaneRunDetail,
  ControlPlaneRunSummary,
  SprintItem,
  SprintDetail,
} from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "SprintDetail">;
type Rt = RouteProp<RootStackParamList, "SprintDetail">;
type ColumnKey =
  | "backlog"
  | "planning"
  | "programming"
  | "testing"
  | "review"
  | "awaiting_deploy"
  | "blocked";

const COLUMNS: Record<ColumnKey, { label: string; hint: string }> = {
  backlog: { label: "Backlog", hint: "Itens importados e aguardando play" },
  planning: { label: "Planning", hint: "Mapeamento e planejamento do trabalho" },
  programming: { label: "Programming", hint: "Implementacao e fix loops" },
  testing: { label: "Testing", hint: "Lint, testes e seguranca" },
  review: { label: "Review Humana", hint: "PR, evidencias e aprovacao" },
  awaiting_deploy: { label: "Awaiting Deploy", hint: "Pronto para branch alvo do projeto" },
  blocked: { label: "Blocked", hint: "Falhas ou setup pendente" },
};

export const SprintDetailScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const route = useRoute<Rt>();
  const { api, session } = useSession();

  const [detail, setDetail] = useState<SprintDetail | null>(null);
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedItem, setSelectedItem] = useState<SprintItem | null>(null);
  const [selectedRunDetail, setSelectedRunDetail] = useState<ControlPlaneRunDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const provider = session.currentSprint?.provider ?? session.provider ?? "jira";

  const load = async (background = false) => {
    if (!background) setLoading(true);
    try {
      const [sprintDetail, runList] = await Promise.all([
        api.getSprint(route.params.sprintId, provider),
        api.listControlPlaneRuns(),
      ]);
      setDetail(sprintDetail);
      setRuns(runList);
    } catch (e) {
      Alert.alert("Falha", String((e as Error).message ?? e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [route.params.sprintId, provider]);

  const relevantRuns = useMemo(
    () =>
      runs.filter(
        (run) => run.sprint_id === route.params.sprintId && String(run.provider) === String(provider),
      ),
    [provider, route.params.sprintId, runs],
  );

  const latestRunByItem = useMemo(() => {
    const map = new Map<string, ControlPlaneRunSummary>();
    for (const run of relevantRuns) {
      for (const key of run.item_keys ?? []) {
        const current = map.get(key);
        if (!current || compareRunAge(run, current) > 0) {
          map.set(key, run);
        }
      }
    }
    return map;
  }, [relevantRuns]);

  const grouped = useMemo(() => {
    const base: Record<ColumnKey, SprintItem[]> = {
      backlog: [],
      planning: [],
      programming: [],
      testing: [],
      review: [],
      awaiting_deploy: [],
      blocked: [],
    };
    for (const item of detail?.items ?? []) {
      base[resolveItemColumn(item, latestRunByItem.get(item.key))].push(item);
    }
    return base;
  }, [detail?.items, latestRunByItem]);

  const configuredLocalRepos = useMemo(
    () =>
      session.projectSetup.repositories.filter(
        (repo) => repo.repoPath.trim() && !looksRemote(repo.repoPath.trim()),
      ),
    [session.projectSetup.repositories],
  );

  const canRun = configuredLocalRepos.length > 0;
  const runnableKeys = useMemo(() => (detail?.items ?? []).map((item) => item.key), [detail?.items]);
  const headerMeta = [
    session.currentSprint?.portfolioName,
    session.currentSprint?.projectName,
    session.currentSprint?.teamName,
  ]
    .filter(Boolean)
    .join(" / ");

  const startItems = (keys: string[]) => {
    if (!canRun) {
      Alert.alert(
        "Repositorio nao configurado",
        "Abra Project Setup e informe ao menos um caminho local de repositorio para liberar a execucao.",
      );
      return;
    }
    nav.navigate("Run", {
      sprintId: route.params.sprintId,
      mode: "selected",
      itemKeys: keys,
    });
  };

  const openItem = async (item: SprintItem) => {
    setSelectedItem(item);
    setSelectedRunDetail(null);
    const latestRun = latestRunByItem.get(item.key);
    if (!latestRun) return;
    setDetailLoading(true);
    try {
      setSelectedRunDetail(await api.getControlPlaneRun(latestRun.run_id));
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading) {
    return (
      <Screen title="Carregando sprint">
        <ActivityIndicator color={theme.primary} />
      </Screen>
    );
  }

  return (
    <Screen
      title={detail?.sprint.name ?? session.currentSprint?.sprintName ?? "Sprint"}
      subtitle={
        headerMeta
          ? `${headerMeta} · ${(detail?.items ?? []).length} item(s) importado(s)`
          : `${(detail?.items ?? []).length} item(s) importado(s)`
      }
      scroll={false}
      footer={
        <View style={{ gap: 10 }}>
          <Button
            title={`Play todos (${runnableKeys.length})`}
            onPress={() => startItems(runnableKeys)}
            disabled={runnableKeys.length === 0}
          />
          <Button
            title="Setup do projeto"
            variant="secondary"
            onPress={() => nav.navigate("ProjectSetup")}
          />
        </View>
      }
    >
      <ScrollView
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              void load(true);
            }}
            tintColor={theme.primary}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        <Card style={styles.hero}>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>SPRINT BACKLOG</Text>
            <Text style={styles.heroTitle}>{detail?.sprint.goal || "Backlog pronto para despacho"}</Text>
            <Text style={styles.heroText}>
              {canRun
                ? `${configuredLocalRepos.length} repositorio(s) local(is) liberados para play.`
                : "Nenhum repositorio local configurado. O play fica bloqueado ate concluir o setup."}
            </Text>
          </View>
          <View style={styles.heroActions}>
            <MiniAction title="Play todos" onPress={() => startItems(runnableKeys)} disabled={!canRun} />
            <MiniAction
              title="Refresh"
              onPress={() => {
                setRefreshing(true);
                void load(true);
              }}
            />
          </View>
        </Card>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.board}
        >
          {(Object.keys(COLUMNS) as ColumnKey[]).map((column) => (
            <View key={column} style={styles.column}>
              <View style={styles.columnHead}>
                <Text style={styles.columnTitle}>{COLUMNS[column].label}</Text>
                <Text style={styles.columnHint}>{COLUMNS[column].hint}</Text>
              </View>

              <View style={{ gap: 10 }}>
                {grouped[column].length === 0 ? (
                  <Card style={styles.emptyCard}>
                    <Text style={styles.emptyText}>Sem cards nesta etapa.</Text>
                  </Card>
                ) : (
                  grouped[column].map((item) => {
                    const latestRun = latestRunByItem.get(item.key);
                    return (
                      <Pressable key={item.id} onPress={() => void openItem(item)}>
                        <Card style={styles.taskCard}>
                          <View style={styles.cardHead}>
                            <Text style={styles.itemKey}>{item.key}</Text>
                            <StatusChip label={item.type} />
                          </View>
                          <Text style={styles.itemTitle}>{item.title}</Text>
                          <Text style={styles.itemStatus}>{item.status}</Text>
                          <View style={styles.metaRow}>
                            {item.assignee ? <Text style={styles.metaText}>👤 {item.assignee}</Text> : null}
                            {item.story_points != null ? (
                              <Text style={styles.metaText}>⚡ {item.story_points} sp</Text>
                            ) : null}
                          </View>
                          <View style={styles.cardFooter}>
                            <MiniAction
                              title="Play"
                              onPress={() => startItems([item.key])}
                              disabled={!canRun}
                            />
                            <Text style={styles.runMeta}>
                              {latestRun
                                ? `${latestRun.state} · step ${latestRun.last_step ?? 0}`
                                : "sem run"}
                            </Text>
                          </View>
                        </Card>
                      </Pressable>
                    );
                  })
                )}
              </View>
            </View>
          ))}
        </ScrollView>
      </ScrollView>

      <ItemDetailModal
        item={selectedItem}
        detail={selectedRunDetail}
        loading={detailLoading}
        onClose={() => {
          setSelectedItem(null);
          setSelectedRunDetail(null);
          setDetailLoading(false);
        }}
      />
    </Screen>
  );
};

const compareRunAge = (left: ControlPlaneRunSummary, right: ControlPlaneRunSummary): number => {
  const leftValue = left.finished_at ?? left.started_at ?? "";
  const rightValue = right.finished_at ?? right.started_at ?? "";
  return leftValue.localeCompare(rightValue);
};

const resolveItemColumn = (item: SprintItem, run?: ControlPlaneRunSummary): ColumnKey => {
  if (run) {
    if (run.failed || run.state === "failed") return "blocked";
    if (run.state === "done") return "awaiting_deploy";
    if ((run.last_step ?? 0) >= 8 || run.readiness_verdict === "needs_human_approval") {
      return "review";
    }
    if ((run.last_step ?? 0) >= 4) return "testing";
    if ((run.last_step ?? 0) >= 3) return "programming";
    if ((run.last_step ?? 0) >= 1 || run.state === "running") return "planning";
  }

  const status = item.status.toLowerCase();
  if (status.includes("block")) return "blocked";
  if (status.includes("review") || status.includes("qa") || status.includes("homolog")) {
    return "review";
  }
  if (status.includes("test")) return "testing";
  if (
    status.includes("progress") ||
    status.includes("doing") ||
    status.includes("develop") ||
    status.includes("coding")
  ) {
    return "programming";
  }
  if (status.includes("plan") || status.includes("analysis")) return "planning";
  if (status.includes("deploy") || status.includes("ready")) return "awaiting_deploy";
  return "backlog";
};

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

const MiniAction: React.FC<{
  title: string;
  onPress: () => void;
  disabled?: boolean;
}> = ({ title, onPress, disabled }) => (
  <Pressable
    disabled={disabled}
    onPress={(event) => {
      event.stopPropagation();
      onPress();
    }}
    style={({ pressed }) => [
      styles.miniAction,
      disabled && styles.miniActionDisabled,
      pressed && !disabled && { opacity: 0.82 },
    ]}
  >
    <Text style={styles.miniActionText}>{title}</Text>
  </Pressable>
);

const StatusChip: React.FC<{ label: string }> = ({ label }) => (
  <View style={styles.statusChip}>
    <Text style={styles.statusChipText}>{label}</Text>
  </View>
);

const ItemDetailModal: React.FC<{
  item: SprintItem | null;
  detail: ControlPlaneRunDetail | null;
  loading: boolean;
  onClose: () => void;
}> = ({ item, detail, loading, onClose }) => (
  <Modal visible={Boolean(item)} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.modalBackdrop}>
      <View style={styles.modalCard}>
        <View style={styles.modalHead}>
          <View style={{ flex: 1 }}>
            <Text style={styles.modalTitle}>{item?.key ?? "Item"}</Text>
            <Text style={styles.modalSubtitle}>{item?.title ?? "Sem titulo"}</Text>
          </View>
          <Button title="Fechar" variant="ghost" onPress={onClose} />
        </View>

        <ScrollView style={{ maxHeight: 460 }} showsVerticalScrollIndicator={false}>
          <Card style={styles.modalSection}>
            <Text style={styles.modalSectionTitle}>DETALHES</Text>
            <Text style={styles.modalBody}>Status: {item?.status ?? "unknown"}</Text>
            <Text style={styles.modalBody}>Tipo: {item?.type ?? "Issue"}</Text>
            {item?.assignee ? <Text style={styles.modalBody}>Assignee: {item.assignee}</Text> : null}
            {item?.story_points != null ? (
              <Text style={styles.modalBody}>Story points: {item.story_points}</Text>
            ) : null}
          </Card>

          <Card style={styles.modalSection}>
            <Text style={styles.modalSectionTitle}>LOGS DO SENDSPRINT</Text>
            {loading ? (
              <ActivityIndicator color={theme.primary} />
            ) : detail ? (
              <>
                <Text style={styles.modalBody}>
                  Run: {detail.run.state} · step {detail.run.last_step ?? 0}
                </Text>
                {(detail.logs ?? []).length === 0 ? (
                  <Text style={styles.modalBody}>Sem logs capturados ainda.</Text>
                ) : (
                  detail.logs.map((log, index) => (
                    <Text key={`${index}-${log}`} style={styles.modalMono}>
                      {log}
                    </Text>
                  ))
                )}
              </>
            ) : (
              <Text style={styles.modalBody}>Nenhuma execucao registrada para este card ainda.</Text>
            )}
          </Card>
        </ScrollView>
      </View>
    </View>
  </Modal>
);

const styles = StyleSheet.create({
  hero: {
    backgroundColor: "#eef5ff",
    flexDirection: "row",
    gap: 12,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
  },
  heroTitle: {
    color: theme.text,
    fontSize: 24,
    lineHeight: 30,
    fontWeight: "800",
    marginTop: 4,
  },
  heroText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 4,
  },
  heroActions: {
    gap: 8,
    alignItems: "flex-end",
  },
  board: {
    gap: 12,
    paddingTop: 16,
    paddingBottom: 20,
  },
  column: {
    width: 292,
    gap: 10,
  },
  columnHead: {
    paddingHorizontal: 4,
  },
  columnTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "800",
  },
  columnHint: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  emptyCard: {
    backgroundColor: theme.surfaceAlt,
  },
  emptyText: {
    color: theme.textMuted,
    fontSize: 12,
  },
  taskCard: {
    gap: 8,
  },
  cardHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
  },
  itemKey: {
    color: theme.primary,
    fontFamily: theme.fontMono,
    fontSize: 12,
  },
  itemTitle: {
    color: theme.text,
    fontSize: 15,
    lineHeight: 21,
    fontWeight: "700",
  },
  itemStatus: {
    color: theme.textMuted,
    fontSize: 12,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  metaText: {
    color: theme.textMuted,
    fontSize: 12,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    marginTop: 2,
  },
  runMeta: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontMono,
  },
  statusChip: {
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.12)",
  },
  statusChipText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "800",
  },
  miniAction: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  miniActionDisabled: {
    opacity: 0.42,
  },
  miniActionText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "800",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(14, 24, 36, 0.35)",
    justifyContent: "center",
    padding: 20,
  },
  modalCard: {
    backgroundColor: theme.bg,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    padding: 16,
    gap: 12,
  },
  modalHead: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  modalTitle: {
    color: theme.text,
    fontSize: 20,
    fontWeight: "800",
  },
  modalSubtitle: {
    color: theme.textMuted,
    fontSize: 13,
    marginTop: 4,
  },
  modalSection: {
    marginBottom: 12,
  },
  modalSectionTitle: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: 4,
  },
  modalBody: {
    color: theme.text,
    fontSize: 13,
    lineHeight: 20,
  },
  modalMono: {
    color: theme.text,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: theme.fontMono,
  },
});
