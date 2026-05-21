import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type ViewStyle,
} from "react-native";
import { getApiErrorMessage } from "../api/client";
import type {
  ColumnKey,
  ControlPlaneRunDetail,
  ControlPlaneRunSummary,
  SprintDetail,
  SprintItem,
} from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "SprintDetail">;
type Rt = RouteProp<RootStackParamList, "SprintDetail">;
type DetailTab = "overview" | "logs" | "timeline" | "readiness" | "evidence";

const COLUMNS: Record<ColumnKey, { label: string; hint: string }> = {
  backlog: { label: "Backlog", hint: "Itens importados e aguardando preparo" },
  planning: { label: "Planning", hint: "Mapeamento e planejamento" },
  programming: { label: "Programming", hint: "Implementacao e fix loops" },
  testing: { label: "Testing", hint: "Lint, testes e seguranca" },
  review: { label: "Review Humana", hint: "Validacao e aprovacao" },
  awaiting_deploy: { label: "Awaiting Deploy", hint: "Pronto para branch alvo" },
  blocked: { label: "Blocked", hint: "Falhas ou setup pendente" },
};

const COLUMN_ORDER: ColumnKey[] = [
  "backlog",
  "planning",
  "programming",
  "testing",
  "review",
  "awaiting_deploy",
  "blocked",
];

const NEXT_COLUMN: Partial<Record<ColumnKey, ColumnKey>> = {
  backlog: "planning",
  planning: "programming",
  programming: "testing",
  testing: "review",
  review: "awaiting_deploy",
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
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [detailLoading, setDetailLoading] = useState(false);
  const [draggingKey, setDraggingKey] = useState<string | null>(null);
  const [hoverColumn, setHoverColumn] = useState<ColumnKey | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [columnOverrides, setColumnOverrides] = useState<Record<string, ColumnKey>>({});
  const [mutatingKeys, setMutatingKeys] = useState<string[]>([]);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [bulkMovingColumn, setBulkMovingColumn] = useState<ColumnKey | null>(null);
  const [query, setQuery] = useState("");

  const provider = session.currentSprint?.provider ?? session.provider ?? "jira";
  const actorEmail = session.appUser?.email?.trim().toLowerCase() ?? undefined;
  const canRunAllBacklog = session.appUser?.permissions?.canRunAllBacklog ?? true;

  const configuredLocalRepos = useMemo(
    () =>
      session.projectSetup.repositories.filter(
        (repo) => repo.repoPath.trim() && !looksRemote(repo.repoPath.trim()),
      ),
    [session.projectSetup.repositories],
  );
  const canRun = configuredLocalRepos.length > 0;

  const executionProjectSetup = useMemo(
    () => ({
      ...session.projectSetup,
      repositories: configuredLocalRepos,
    }),
    [configuredLocalRepos, session.projectSetup],
  );

  const load = async (background = false) => {
    if (!background) setLoading(true);
    try {
      const [sprintDetail, runList] = await Promise.all([
        api.getSprint(route.params.sprintId, provider, {
          scope: actorEmail ? "mine" : undefined,
          user_email: actorEmail,
          include_archived: showArchived,
        }),
        api.listControlPlaneRuns(),
      ]);
      setDetail(sprintDetail);
      setRuns(runList);
    } catch (error) {
      Alert.alert("Falha", getApiErrorMessage(error));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [actorEmail, provider, route.params.sprintId, showArchived]);

  const relevantRuns = useMemo(
    () =>
      runs.filter(
        (run) =>
          run.sprint_id === route.params.sprintId && String(run.provider) === String(provider),
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

  const itemByKey = useMemo(
    () => new Map((detail?.items ?? []).map((item) => [item.key, item])),
    [detail?.items],
  );

  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return detail?.items ?? [];
    return (detail?.items ?? []).filter((item) =>
      [item.key, item.title, item.type, item.status, item.assignee, item.assignee_email]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedQuery)),
    );
  }, [detail?.items, query]);

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
    for (const item of visibleItems) {
      const column = resolveItemColumn(item, latestRunByItem.get(item.key), columnOverrides[item.key]);
      base[column].push(item);
    }
    return base;
  }, [columnOverrides, latestRunByItem, visibleItems]);

  const backlogKeys = useMemo(() => grouped.backlog.map((item) => item.key), [grouped.backlog]);

  const headerMeta = [
    session.currentSprint?.portfolioName,
    session.currentSprint?.projectName,
    session.currentSprint?.teamName,
  ]
    .filter(Boolean)
    .join(" / ");

  const removeOverrides = (keys: string[]) => {
    setColumnOverrides((current) => {
      const next = { ...current };
      for (const key of keys) delete next[key];
      return next;
    });
  };

  const applyMove = async (
    keys: string[],
    targetColumn: ColumnKey,
    opts: { startRun?: boolean; note?: string } = {},
  ) => {
    if (!canRun) {
      Alert.alert(
        "Repositorio nao configurado",
        "Abra Project Setup e informe ao menos um caminho local de repositorio para liberar o backlog.",
      );
      return false;
    }

    const uniqueKeys = Array.from(new Set(keys.filter(Boolean)));
    if (uniqueKeys.length === 0) return false;

    setMutatingKeys((current) => Array.from(new Set([...current, ...uniqueKeys])));
    setColumnOverrides((current) => {
      const next = { ...current };
      for (const key of uniqueKeys) next[key] = targetColumn;
      return next;
    });

    try {
      await Promise.all(
        uniqueKeys.map((key) =>
          api.moveSprintItem(route.params.sprintId, key, {
            provider,
            target_column: targetColumn,
            actor_email: actorEmail ?? null,
            note: opts.note ?? null,
          }),
        ),
      );

      if (opts.startRun) {
        await api.startRun({
          provider,
          sprint_id: route.params.sprintId,
          mode: "selected",
          item_keys: uniqueKeys,
          project_setup: executionProjectSetup,
        });
      }

      await load(true);
      return true;
    } catch (error) {
      removeOverrides(uniqueKeys);
      Alert.alert("Falha ao atualizar", getApiErrorMessage(error));
      return false;
    } finally {
      setMutatingKeys((current) => current.filter((key) => !uniqueKeys.includes(key)));
    }
  };

  const moveColumnForward = async (column: ColumnKey) => {
    const targetColumn = NEXT_COLUMN[column];
    if (!targetColumn) return;
    const keys = grouped[column].map((item) => item.key);
    if (keys.length === 0) return;
    if (column === "backlog" && !canRunAllBacklog) {
      Alert.alert("Permissao insuficiente", "Seu usuario nao pode iniciar todo o backlog.");
      return;
    }
    setBulkMovingColumn(column);
    try {
      await applyMove(keys, targetColumn, {
        startRun: targetColumn === "planning",
        note: `bulk-advance:${column}->${targetColumn}`,
      });
    } finally {
      setBulkMovingColumn(null);
    }
  };

  const openItem = async (item: SprintItem) => {
    setSelectedItem(item);
    setSelectedRunDetail(null);
    setDetailTab("overview");
    const latestRun = latestRunByItem.get(item.key);
    if (!latestRun) return;
    setDetailLoading(true);
    try {
      setSelectedRunDetail(await api.getControlPlaneRun(latestRun.run_id));
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleArchive = async () => {
    if (!selectedItem || archiveBusy) return;
    setArchiveBusy(true);
    try {
      await api.archiveSprintItem(route.params.sprintId, selectedItem.key, {
        provider,
        actor_email: actorEmail ?? null,
        archived: !selectedItem.archived,
        note: selectedItem.archived ? "restore-card" : "archive-card",
      });
      setSelectedItem(null);
      setSelectedRunDetail(null);
      await load(true);
    } catch (error) {
      Alert.alert("Falha ao arquivar", getApiErrorMessage(error));
    } finally {
      setArchiveBusy(false);
    }
  };

  const getDragProps = (item: SprintItem): Record<string, unknown> => {
    if (Platform.OS !== "web") return {};
    const isMutating = mutatingKeys.includes(item.key);
    const isDraggable = canDragItem(canRun, isMutating);
    const currentColumn = resolveItemColumn(item, latestRunByItem.get(item.key), columnOverrides[item.key]);
    return {
      draggable: isDraggable,
      onDragStart: (event: any) => {
        if (!isDraggable) {
          event.preventDefault?.();
          return;
        }
        event.dataTransfer?.setData("text/plain", item.key);
        event.dataTransfer?.setData("application/x-sendsprint-column", currentColumn);
        setDraggingKey(item.key);
      },
      onDragEnd: () => {
        setDraggingKey(null);
        setHoverColumn(null);
      },
    };
  };

  const getDropProps = (column: ColumnKey): Record<string, unknown> => {
    if (Platform.OS !== "web") return {};
    return {
      onDragOver: (event: any) => {
        if (!draggingKey || !canRun) return;
        event.preventDefault?.();
        setHoverColumn(column);
      },
      onDragLeave: () => {
        setHoverColumn((current) => (current === column ? null : current));
      },
      onDrop: async (event: any) => {
        event.preventDefault?.();
        const key = event.dataTransfer?.getData("text/plain") || draggingKey;
        setHoverColumn(null);
        setDraggingKey(null);
        if (!key) return;
        const item = itemByKey.get(key);
        if (!item) return;
        const currentColumn = resolveItemColumn(item, latestRunByItem.get(item.key), columnOverrides[item.key]);
        if (currentColumn === column) return;
        await applyMove([key], column, {
          startRun: column === "planning",
          note: `drag:${currentColumn}->${column}`,
        });
      },
    };
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
      chrome="app"
      eyebrow="Web 07 - Kanban Backlog / Web 08 - Card Detail"
      title={detail?.sprint.name ?? session.currentSprint?.sprintName ?? "Sprint"}
      subtitle={
        headerMeta
          ? `${headerMeta} - ${visibleItems.length}/${(detail?.items ?? []).length} item(s) visiveis`
          : `${visibleItems.length}/${(detail?.items ?? []).length} item(s) visiveis`
      }
      scroll={false}
      footer={
        <View style={{ gap: 10 }}>
          {canRunAllBacklog ? (
            <Button
              title={`Play todos do backlog (${backlogKeys.length})`}
              onPress={() => void moveColumnForward("backlog")}
              disabled={backlogKeys.length === 0 || bulkMovingColumn === "backlog"}
            />
          ) : null}
          <Button title="Setup do projeto" variant="secondary" onPress={() => nav.navigate("ProjectSetup")} />
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
                ? `${configuredLocalRepos.length} repositorio(s) local(is) liberados. Arraste os cards entre colunas para alterar o status; mover para Planning dispara a execucao.`
                : "Nenhum repositorio local configurado. O backlog fica bloqueado para arraste ate concluir o setup."}
            </Text>
            <Text style={styles.heroMeta}>
              Arquivados nesta sprint: {detail?.archived_count ?? 0}. Filtro atual: {actorEmail ?? "sem email de app"}.
            </Text>
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Buscar por chave, titulo, tipo ou responsavel"
              placeholderTextColor={theme.textMuted}
              style={styles.searchInput}
            />
            <View style={styles.toolbarRow}>
              <SignalPill label={`cards ${visibleItems.length}`} />
              <SignalPill
                label={`repos ${configuredLocalRepos.length}`}
                tone={canRun ? "success" : "warning"}
              />
              <SignalPill label={actorEmail ? "scope mine" : "scope all"} />
              <SignalPill label="modo IA" tone="primary" />
            </View>
          </View>
          <View style={styles.heroActions}>
            <MiniAction
              title="Refresh"
              onPress={() => {
                setRefreshing(true);
                void load(true);
              }}
            />
            <MiniAction
              title={showArchived ? "Ocultar arquivados" : "Mostrar arquivados"}
              onPress={() => setShowArchived((current) => !current)}
            />
          </View>
        </Card>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.board}>
          {COLUMN_ORDER.map((column) => {
            const nextColumn = NEXT_COLUMN[column];
            const columnItems = grouped[column];
            const canAdvanceColumn =
              Boolean(nextColumn) &&
              columnItems.length > 0 &&
              canRun &&
              (column !== "backlog" || canRunAllBacklog);
            return (
              <View
                key={column}
                style={styleList<ViewStyle>(
                  styles.column,
                  hoverColumn === column && Boolean(draggingKey) && styles.columnDropTarget,
                )}
                {...getDropProps(column)}
              >
                <View style={styles.columnHead}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.columnTitle}>
                      {COLUMNS[column].label} ({columnItems.length})
                    </Text>
                    <Text style={styles.columnHint}>{COLUMNS[column].hint}</Text>
                  </View>
                  {nextColumn ? (
                    <MiniAction
                      title="Avancar"
                      onPress={() => void moveColumnForward(column)}
                      disabled={!canAdvanceColumn || bulkMovingColumn === column}
                    />
                  ) : null}
                </View>

                <View style={{ gap: 10 }}>
                  {columnItems.length === 0 ? (
                    <Card style={styles.emptyCard}>
                      <Text style={styles.emptyText}>Sem cards nesta etapa.</Text>
                    </Card>
                  ) : (
                    columnItems.map((item) => {
                      const latestRun = latestRunByItem.get(item.key);
                      const isMutating = mutatingKeys.includes(item.key);
                      const isDraggable = canDragItem(canRun, isMutating);
                      return (
                        <Pressable key={item.id} onPress={() => void openItem(item)} {...getDragProps(item)}>
                          <Card
                            style={styleList<ViewStyle>(
                              styles.taskCard,
                              draggingKey === item.key && styles.taskCardDragging,
                              !isDraggable && styles.taskCardLocked,
                            )}
                          >
                            <View style={styles.cardHead}>
                              <Text style={styles.itemKey}>{item.key}</Text>
                              <StatusChip label={item.type} />
                            </View>
                            <Text style={styles.itemTitle}>{item.title}</Text>
                            <Text style={styles.itemStatus}>{item.board_status ?? COLUMNS[column].label}</Text>
                            <View style={styles.metaRow}>
                              {item.assignee ? <Text style={styles.metaText}>owner {item.assignee}</Text> : null}
                              {item.story_points != null ? <Text style={styles.metaText}>{item.story_points} sp</Text> : null}
                              {latestRun?.readiness_verdict ? (
                                <Text style={styles.metaText}>readiness {latestRun.readiness_verdict}</Text>
                              ) : null}
                              {latestRun?.failed ? (
                                <Text style={[styles.metaText, styles.metaDanger]}>failed</Text>
                              ) : null}
                              {item.archived ? <Text style={styles.metaText}>archived</Text> : null}
                            </View>
                            <View style={styles.cardFooter}>
                              <Text style={styles.runMeta}>
                                {isMutating
                                  ? "atualizando..."
                                  : latestRun
                                    ? `${latestRun.state} - step ${latestRun.last_step ?? 0}`
                                    : item.status}
                              </Text>
                              <Text style={[styles.runMeta, !isDraggable && styles.metaDanger]}>
                                {isDraggable ? "drag para mover" : "configure o repositorio"}
                              </Text>
                            </View>
                          </Card>
                        </Pressable>
                      );
                    })
                  )}
                </View>
              </View>
            );
          })}
        </ScrollView>
      </ScrollView>

      <ItemDetailModal
        item={selectedItem}
        detail={selectedRunDetail}
        tab={detailTab}
        onTabChange={setDetailTab}
        loading={detailLoading}
        archiveBusy={archiveBusy}
        onToggleArchive={() => void toggleArchive()}
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

const resolveRunColumn = (run?: ControlPlaneRunSummary): ColumnKey | null => {
  if (!run) return null;
  if (run.failed || run.state === "failed") return "blocked";
  if (run.state === "done") return "awaiting_deploy";
  if ((run.last_step ?? 0) >= 8 || run.readiness_verdict === "needs_human_approval") return "review";
  if ((run.last_step ?? 0) >= 4) return "testing";
  if ((run.last_step ?? 0) >= 3) return "programming";
  if ((run.last_step ?? 0) >= 1 || run.state === "running") return "planning";
  return null;
};

const resolveItemColumn = (
  item: SprintItem,
  run?: ControlPlaneRunSummary,
  override?: ColumnKey,
): ColumnKey => {
  if (override) return override;

  const runColumn = resolveRunColumn(run);
  const manualColumn = item.board_column ?? undefined;
  const runTimestamp = run?.finished_at ?? run?.started_at ?? "";
  const manualTimestamp = item.board_updated_at ?? "";

  if (manualColumn && manualTimestamp && runTimestamp && manualTimestamp >= runTimestamp) {
    return manualColumn;
  }
  if (runColumn && manualColumn) {
    return furthestColumn(manualColumn, runColumn);
  }
  if (runColumn) return runColumn;
  if (manualColumn) return manualColumn;

  const status = item.status.toLowerCase();
  if (status.includes("block")) return "blocked";
  if (status.includes("review") || status.includes("qa") || status.includes("homolog")) return "review";
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

const furthestColumn = (left: ColumnKey, right: ColumnKey): ColumnKey => {
  if (left === "blocked" || right === "blocked") return right === "blocked" ? "blocked" : left;
  return COLUMN_ORDER.indexOf(left) >= COLUMN_ORDER.indexOf(right) ? left : right;
};

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

const canDragItem = (canRun: boolean, isMutating: boolean): boolean => canRun && !isMutating;

const styleList = <T,>(...values: Array<T | false | null | undefined>): T[] =>
  values.filter(Boolean) as T[];

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

const SignalPill: React.FC<{
  label: string;
  tone?: "default" | "primary" | "success" | "warning";
}> = ({ label, tone = "default" }) => (
  <View
    style={[
      styles.signalPill,
      tone === "primary" && styles.signalPillPrimary,
      tone === "success" && styles.signalPillSuccess,
      tone === "warning" && styles.signalPillWarning,
    ]}
  >
    <Text style={[styles.signalPillText, tone !== "default" && styles.signalPillTextStrong]}>{label}</Text>
  </View>
);

const ItemDetailModal: React.FC<{
  item: SprintItem | null;
  detail: ControlPlaneRunDetail | null;
  tab: DetailTab;
  onTabChange: (tab: DetailTab) => void;
  loading: boolean;
  archiveBusy: boolean;
  onToggleArchive: () => void;
  onClose: () => void;
}> = ({ item, detail, tab, onTabChange, loading, archiveBusy, onToggleArchive, onClose }) => (
  <Modal visible={Boolean(item)} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.modalBackdrop}>
      <View style={styles.modalCard}>
        <View style={styles.modalHead}>
          <View style={{ flex: 1 }}>
            <Text style={styles.modalTitle}>{item?.key ?? "Item"}</Text>
            <Text style={styles.modalSubtitle}>{item?.title ?? "Sem titulo"}</Text>
          </View>
          <View style={styles.modalActions}>
            {item ? (
              <Button
                title={archiveBusy ? "Salvando..." : item.archived ? "Restaurar" : "Arquivar"}
                variant="secondary"
                onPress={onToggleArchive}
                disabled={archiveBusy}
              />
            ) : null}
            <Button title="Fechar" variant="ghost" onPress={onClose} />
          </View>
        </View>

        <View style={styles.modalTabs}>
          {[
            ["overview", "Visao geral"],
            ["logs", "Logs"],
            ["timeline", "Timeline"],
            ["readiness", "Readiness"],
            ["evidence", "Evidencias"],
          ].map(([value, label]) => (
            <Pressable
              key={value}
              onPress={() => onTabChange(value as DetailTab)}
              style={[styles.modalTab, tab === value && styles.modalTabActive]}
            >
              <Text style={[styles.modalTabText, tab === value && styles.modalTabTextActive]}>{label}</Text>
            </Pressable>
          ))}
        </View>

        <ScrollView style={{ maxHeight: 520 }} showsVerticalScrollIndicator={false}>
          {tab === "overview" ? (
            <>
              <Card style={styles.modalSection}>
                <Text style={styles.modalSectionTitle}>WORKFLOW</Text>
                <Text style={styles.modalBody}>Status do provider: {item?.status ?? "unknown"}</Text>
                <Text style={styles.modalBody}>Status SendSprint: {item?.board_status ?? "Backlog"}</Text>
                <Text style={styles.modalBody}>Tipo: {item?.type ?? "Issue"}</Text>
                {item?.assignee ? <Text style={styles.modalBody}>Assignee: {item.assignee}</Text> : null}
                {item?.assignee_email ? (
                  <Text style={styles.modalBody}>Email do assignee: {item.assignee_email}</Text>
                ) : null}
                {item?.parent_key ? <Text style={styles.modalBody}>Parent: {item.parent_key}</Text> : null}
                {item?.story_points != null ? (
                  <Text style={styles.modalBody}>Story points: {item.story_points}</Text>
                ) : null}
                {item?.board_updated_by ? (
                  <Text style={styles.modalBody}>Ultima alteracao: {item.board_updated_by}</Text>
                ) : null}
              </Card>

              {item?.description ? (
                <Card style={styles.modalSection}>
                  <Text style={styles.modalSectionTitle}>DESCRICAO</Text>
                  <Text style={styles.modalBody}>{item.description}</Text>
                </Card>
              ) : null}

              {item?.acceptance_criteria ? (
                <Card style={styles.modalSection}>
                  <Text style={styles.modalSectionTitle}>CRITERIOS DE ACEITE</Text>
                  <Text style={styles.modalBody}>{item.acceptance_criteria}</Text>
                </Card>
              ) : null}

              <Card style={styles.modalSection}>
                <Text style={styles.modalSectionTitle}>ORIGEM</Text>
                {item?.source_url ? <Text style={styles.modalMono}>{item.source_url}</Text> : null}
                {item?.created_at ? <Text style={styles.modalBody}>Criado em: {item.created_at}</Text> : null}
                {item?.updated_at ? <Text style={styles.modalBody}>Atualizado em: {item.updated_at}</Text> : null}
                {item?.revision != null ? <Text style={styles.modalBody}>Revision: {String(item.revision)}</Text> : null}
                {item?.labels.length ? <Text style={styles.modalBody}>Labels: {item.labels.join(", ")}</Text> : null}
              </Card>

              {item?.links.length ? (
                <Card style={styles.modalSection}>
                  <Text style={styles.modalSectionTitle}>LINKS</Text>
                  {item.links.map((link, index) => (
                    <Text key={`${index}-${link.type}-${link.target_key ?? ""}`} style={styles.modalMono}>
                      {link.type} - {link.target_key ?? "-"} - {link.target_url ?? "-"}
                    </Text>
                  ))}
                </Card>
              ) : null}

              {item?.comments.length ? (
                <Card style={styles.modalSection}>
                  <Text style={styles.modalSectionTitle}>COMENTARIOS</Text>
                  {item.comments.map((comment, index) => (
                    <View key={`${index}-${comment.created_at ?? "comment"}`} style={styles.modalListItem}>
                      <Text style={styles.modalBody}>
                        {(comment.author || "autor desconhecido") +
                          (comment.created_at ? ` - ${comment.created_at}` : "")}
                      </Text>
                      <Text style={styles.modalBody}>{comment.body ?? ""}</Text>
                    </View>
                  ))}
                </Card>
              ) : null}
            </>
          ) : null}

          {tab === "logs" ? (
            <Card style={styles.modalSection}>
              <Text style={styles.modalSectionTitle}>LOGS DO SENDSPRINT</Text>
              {loading ? (
                <ActivityIndicator color={theme.primary} />
              ) : detail ? (
                <>
                  <Text style={styles.modalBody}>
                    Run: {detail.run.state} - step {detail.run.last_step ?? 0}
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
          ) : null}

          {tab === "timeline" ? (
            <>
              {item?.history.length ? (
                <Card style={styles.modalSection}>
                  <Text style={styles.modalSectionTitle}>HISTORICO DO BOARD</Text>
                  {item.history.map((entry, index) => (
                    <Text key={`${index}-${entry.observed_at ?? "history"}`} style={styles.modalMono}>
                      {`${entry.observed_at ?? "-"} | ${entry.action ?? "-"} | ${entry.actor_email ?? "-"} | ${entry.from_column ?? "-"} -> ${entry.to_column ?? "-"}${entry.note ? ` | ${entry.note}` : ""}`}
                    </Text>
                  ))}
                </Card>
              ) : null}
              <Card style={styles.modalSection}>
                <Text style={styles.modalSectionTitle}>TIMELINE DA EXECUCAO</Text>
                {detail?.timeline?.length ? (
                  detail.timeline.map((entry, index) => (
                    <Text key={`${index}-timeline`} style={styles.modalMono}>
                      {JSON.stringify(entry)}
                    </Text>
                  ))
                ) : (
                  <Text style={styles.modalBody}>Nenhum evento de timeline registrado ainda.</Text>
                )}
              </Card>
            </>
          ) : null}

          {tab === "readiness" ? (
            <Card style={styles.modalSection}>
              <Text style={styles.modalSectionTitle}>READINESS</Text>
              {detail?.quality_gate ? (
                <>
                  <Text style={styles.modalBody}>Veredito: {detail.quality_gate.verdict}</Text>
                  {detail.quality_gate.reasons.map((reason, index) => (
                    <Text key={`${index}-${reason}`} style={styles.modalBody}>
                      - {reason}
                    </Text>
                  ))}
                  {detail.quality_gate.checks.map((check) => (
                    <Text key={check.check_name} style={styles.modalMono}>
                      {check.check_name} - {check.passed ? "ok" : "failed"} - {check.details}
                    </Text>
                  ))}
                </>
              ) : (
                <Text style={styles.modalBody}>Sem quality gate calculado para este card ainda.</Text>
              )}
            </Card>
          ) : null}

          {tab === "evidence" ? (
            <>
              {item?.attachments.length ? (
                <Card style={styles.modalSection}>
                  <Text style={styles.modalSectionTitle}>ANEXOS DE ORIGEM</Text>
                  {item.attachments.map((attachment, index) => (
                    <Text key={`${index}-${attachment.filename ?? "attachment"}`} style={styles.modalMono}>
                      {attachment.filename ?? "arquivo"} - {attachment.mime_type ?? "sem mime"} - {attachment.url ?? "-"}
                    </Text>
                  ))}
                </Card>
              ) : null}
              <Card style={styles.modalSection}>
                <Text style={styles.modalSectionTitle}>EVIDENCIAS DO SENDSPRINT</Text>
                {detail?.evidence?.items?.length ? (
                  detail.evidence.items.map((entry) => (
                    <Text key={`${entry.type}-${entry.path}`} style={styles.modalMono}>
                      {entry.label} - {entry.type} - {entry.path}
                    </Text>
                  ))
                ) : (
                  <Text style={styles.modalBody}>Nenhuma evidencia registrada ainda.</Text>
                )}
              </Card>
            </>
          ) : null}
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
  heroMeta: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 8,
    fontFamily: theme.fontMono,
  },
  searchInput: {
    marginTop: 12,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: theme.text,
    fontSize: 14,
  },
  toolbarRow: {
    marginTop: 12,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
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
    width: 300,
    gap: 10,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: "transparent",
    padding: 4,
  },
  columnDropTarget: {
    backgroundColor: "rgba(44,107,237,0.06)",
    borderColor: theme.primary,
  },
  columnHead: {
    paddingHorizontal: 4,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
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
  taskCardDragging: {
    opacity: 0.52,
  },
  taskCardLocked: {
    borderColor: theme.border,
    backgroundColor: theme.surfaceAlt,
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
  metaDanger: {
    color: theme.danger,
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
  signalPill: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
  signalPillPrimary: {
    backgroundColor: "rgba(44,107,237,0.10)",
    borderColor: "rgba(44,107,237,0.20)",
  },
  signalPillSuccess: {
    backgroundColor: "rgba(30,169,124,0.10)",
    borderColor: "rgba(30,169,124,0.20)",
  },
  signalPillWarning: {
    backgroundColor: "rgba(193,138,23,0.12)",
    borderColor: "rgba(193,138,23,0.24)",
  },
  signalPillText: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  signalPillTextStrong: {
    color: theme.text,
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
  modalActions: {
    gap: 8,
    alignItems: "flex-end",
  },
  modalTabs: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  modalTab: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  modalTabActive: {
    backgroundColor: "rgba(44,107,237,0.10)",
    borderColor: "rgba(44,107,237,0.24)",
  },
  modalTabText: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  modalTabTextActive: {
    color: theme.primary,
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
    marginBottom: 6,
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
  modalListItem: {
    gap: 4,
    marginBottom: 10,
  },
});
