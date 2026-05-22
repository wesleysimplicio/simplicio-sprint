import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useRef, useState } from "react";
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
import { Icon } from "../components/Icon";
import { Input } from "../components/Input";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "SprintDetail">;
type Rt = RouteProp<RootStackParamList, "SprintDetail">;
type DetailTab = "overview" | "logs" | "timeline" | "readiness" | "evidence";
type ColumnNode = React.ElementRef<typeof View>;
type CardDragState = {
  key: string;
  currentColumn: ColumnKey;
  startX: number;
  startY: number;
  active: boolean;
};

const CARD_DRAG_THRESHOLD_PX = 10;

const domSafeToken = (value: string): string =>
  value.replace(/[^a-zA-Z0-9_-]/g, "-");

const decodeHtmlEntities = (value: string): string => {
  if (typeof document !== "undefined") {
    const textarea = document.createElement("textarea");
    textarea.innerHTML = value;
    return textarea.value;
  }
  return value;
};

const htmlToPlainText = (value?: string | null): string | null => {
  if (!value?.trim()) return null;
  const decoded = decodeHtmlEntities(value);
  const stripped =
    typeof DOMParser !== "undefined"
      ? new DOMParser().parseFromString(decoded, "text/html").body
          .textContent ?? ""
      : decoded.replace(/<[^>]+>/g, " ");
  return stripped.replace(/\s+/g, " ").trim() || null;
};

const COLUMNS: Record<ColumnKey, { label: string; tone: string }> = {
  backlog: { label: "Backlog", tone: theme.textMuted },
  planning: { label: "Planning", tone: theme.info },
  programming: { label: "Programming", tone: theme.primary },
  testing: { label: "Testing", tone: theme.warning },
  review: { label: "Review Humana", tone: theme.accent },
  awaiting_deploy: { label: "Awaiting Deploy", tone: theme.success },
  blocked: { label: "Blocked", tone: theme.danger },
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

const TYPE_TONE: Record<string, { bg: string; fg: string; letter: string }> = {
  story: { bg: "#dcfce7", fg: "#16a34a", letter: "S" },
  task: { bg: "#fef3c7", fg: "#d97706", letter: "T" },
  bug: { bg: "#fee2e2", fg: "#dc2626", letter: "B" },
  epic: { bg: "#dbeafe", fg: "#2563eb", letter: "E" },
  spike: { bg: "#ede9fe", fg: "#7c3aed", letter: "K" },
};

const typeToneFor = (type: string) => {
  const key = type.toLowerCase();
  return (
    TYPE_TONE[key] ?? {
      bg: theme.surfaceMuted,
      fg: theme.textMuted,
      letter: (type[0] ?? "I").toUpperCase(),
    }
  );
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
  const [selectedRunDetail, setSelectedRunDetail] =
    useState<ControlPlaneRunDetail | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [detailLoading, setDetailLoading] = useState(false);
  const [draggingKey, setDraggingKey] = useState<string | null>(null);
  const [hoverColumn, setHoverColumn] = useState<ColumnKey | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [columnOverrides, setColumnOverrides] = useState<
    Record<string, ColumnKey>
  >({});
  const [mutatingKeys, setMutatingKeys] = useState<string[]>([]);
  const [bulkMovingColumn, setBulkMovingColumn] = useState<ColumnKey | null>(
    null,
  );
  const [aiMode, setAiMode] = useState(true);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const columnRefs = useRef<Partial<Record<ColumnKey, ColumnNode | null>>>({});
  const cardDragRef = useRef<CardDragState | null>(null);
  const suppressPressRef = useRef(false);
  const initialOpenKeyRef = useRef(route.params.openItemKey ?? null);

  const provider =
    session.currentSprint?.provider ?? session.provider ?? "jira";
  const actorEmail = session.appUser?.email?.trim().toLowerCase() ?? undefined;
  const canRunAllBacklog =
    session.appUser?.permissions?.canRunAllBacklog ?? true;

  const configuredLocalRepos = useMemo(
    () =>
      session.projectSetup.repositories.filter(
        (repo) =>
          repo.repoPath.trim() && !looksRemote(repo.repoPath.trim()),
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
          run.sprint_id === route.params.sprintId &&
          String(run.provider) === String(provider),
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
    let items = detail?.items ?? [];
    const normalizedQuery = query.trim().toLowerCase();
    if (normalizedQuery) {
      items = items.filter((item) =>
        [item.key, item.title, item.type, item.status, item.assignee]
          .filter(Boolean)
          .some((value) =>
            String(value).toLowerCase().includes(normalizedQuery),
          ),
      );
    }
    if (typeFilter) {
      items = items.filter(
        (item) => item.type.toLowerCase() === typeFilter.toLowerCase(),
      );
    }
    return items;
  }, [detail?.items, query, typeFilter]);

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
      const column = resolveItemColumn(
        item,
        latestRunByItem.get(item.key),
        columnOverrides[item.key],
      );
      base[column].push(item);
    }
    return base;
  }, [columnOverrides, latestRunByItem, visibleItems]);

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
        "Repositório não configurado",
        "Abra Configurar projeto e informe ao menos um caminho local de repositório.",
      );
      return false;
    }
    const uniqueKeys = Array.from(new Set(keys.filter(Boolean)));
    if (uniqueKeys.length === 0) return false;

    setMutatingKeys((current) =>
      Array.from(new Set([...current, ...uniqueKeys])),
    );
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
      setMutatingKeys((current) =>
        current.filter((key) => !uniqueKeys.includes(key)),
      );
    }
  };

  const moveColumnForward = async (column: ColumnKey) => {
    const targetColumn = NEXT_COLUMN[column];
    if (!targetColumn) return;
    const keys = grouped[column].map((item) => item.key);
    if (keys.length === 0) return;
    if (column === "backlog" && !canRunAllBacklog) {
      Alert.alert(
        "Permissão insuficiente",
        "Seu usuário não pode iniciar todo o backlog.",
      );
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

  const openItem = async (
    item: SprintItem,
    initialTab: DetailTab = "overview",
  ) => {
    setSelectedItem(item);
    setSelectedRunDetail(null);
    setDetailTab(initialTab);
    const latestRun = latestRunByItem.get(item.key);
    if (!latestRun) return;
    setDetailLoading(true);
    try {
      setSelectedRunDetail(await api.getControlPlaneRun(latestRun.run_id));
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    const key = initialOpenKeyRef.current;
    if (!key || !detail) return;
    const item = detail.items.find(
      (candidate) => candidate.key === key || candidate.id === key,
    );
    if (!item) return;
    initialOpenKeyRef.current = null;
    void openItem(
      item,
      isDetailTab(route.params.detailTab)
        ? route.params.detailTab
        : "overview",
    );
  }, [detail, latestRunByItem, route.params.detailTab]);

  // Drag and drop on web only
  const resolveColumnAtPageX = (
    pageX: number,
    callback: (column: ColumnKey | null) => void,
  ) => {
    const refs = COLUMN_ORDER.map((column) => ({
      column,
      ref: columnRefs.current[column],
    })).filter(
      (entry): entry is { column: ColumnKey; ref: ColumnNode } =>
        Boolean(entry.ref),
    );
    if (refs.length === 0) {
      callback(null);
      return;
    }
    let pending = refs.length;
    let matched = false;
    refs.forEach(({ column, ref }) => {
      ref.measureInWindow((x, _y, width) => {
        if (!matched && pageX >= x && pageX <= x + width) {
          matched = true;
          callback(column);
        }
        pending -= 1;
        if (pending === 0 && !matched) callback(null);
      });
    });
  };

  const resetCardDrag = () => {
    cardDragRef.current = null;
    setDraggingKey(null);
    setHoverColumn(null);
  };

  const getDragProps = (item: SprintItem): Record<string, unknown> => {
    if (Platform.OS !== "web") return {};
    const isMutating = mutatingKeys.includes(item.key);
    const isDraggable = canRun && !isMutating;
    const currentColumn = resolveItemColumn(
      item,
      latestRunByItem.get(item.key),
      columnOverrides[item.key],
    );
    return {
      onClick: () => {
        if (suppressPressRef.current) {
          suppressPressRef.current = false;
          return;
        }
        void openItem(item);
      },
      onPointerDown: (event: any) => {
        if (!isDraggable || event?.nativeEvent?.button > 0) return;
        const pageX = event?.nativeEvent?.pageX ?? 0;
        const pageY = event?.nativeEvent?.pageY ?? 0;
        event.currentTarget?.setPointerCapture?.(event.nativeEvent.pointerId);
        cardDragRef.current = {
          key: item.key,
          currentColumn,
          startX: pageX,
          startY: pageY,
          active: false,
        };
      },
      onPointerMove: (event: any) => {
        const drag = cardDragRef.current;
        if (!drag) return;
        const pageX = event?.nativeEvent?.pageX ?? 0;
        const pageY = event?.nativeEvent?.pageY ?? 0;
        const deltaX = pageX - drag.startX;
        const deltaY = pageY - drag.startY;
        if (!drag.active) {
          if (
            Math.abs(deltaX) < CARD_DRAG_THRESHOLD_PX ||
            Math.abs(deltaX) <= Math.abs(deltaY)
          ) {
            return;
          }
          drag.active = true;
          suppressPressRef.current = true;
          setDraggingKey(drag.key);
        }
        event.preventDefault?.();
        resolveColumnAtPageX(pageX, (column) => {
          if (cardDragRef.current?.key === drag.key) setHoverColumn(column);
        });
      },
      onPointerUp: (event: any) => {
        const drag = cardDragRef.current;
        if (!drag) return;
        event.currentTarget?.releasePointerCapture?.(event.nativeEvent.pointerId);
        if (!drag.active) {
          resetCardDrag();
          return;
        }
        const pageX = event?.nativeEvent?.pageX ?? 0;
        cardDragRef.current = null;
        setDraggingKey(null);
        setHoverColumn(null);
        setTimeout(() => {
          suppressPressRef.current = false;
        }, 250);
        resolveColumnAtPageX(pageX, (column) => {
          if (!column || column === drag.currentColumn) return;
          void applyMove([drag.key], column, {
            startRun: column === "planning",
            note: `drag:${drag.currentColumn}->${column}`,
          });
        });
      },
      onPointerCancel: () => {
        resetCardDrag();
      },
    };
  };

  if (loading) {
    return (
      <Screen title="Carregando sprint…">
        <ActivityIndicator color={theme.primary} />
      </Screen>
    );
  }

  const sprintName =
    session.currentSprint?.sprintName ?? detail?.sprint.name ?? "Sprint";
  const itemCount = detail?.items.length ?? 0;
  const providerLabel = provider === "azuredevops" ? "Azure DevOps" : "Jira";

  return (
    <Screen scroll={false}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 28, gap: 16 }}
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
      >
        <Card padding={20}>
          <View style={styles.boardHeader}>
            <View style={styles.boardHeaderLeft}>
              <View style={styles.boardIcon}>
                <Icon name="logo" size={18} color="#fff" />
              </View>
              <View>
                <Text style={styles.boardTitle}>{sprintName}</Text>
                <Text style={styles.boardSubtitle}>
                  {providerLabel} · {itemCount} issues
                </Text>
              </View>
            </View>
            <View style={styles.boardHeaderRight}>
              <View style={styles.toggleRow}>
                <Text style={styles.toggleLabel}>Modo IA</Text>
                <Pressable onPress={() => setAiMode((v) => !v)} style={styles.toggleTrack}>
                  <View
                    style={[
                      styles.toggleTrackInner,
                      aiMode && styles.toggleTrackInnerOn,
                    ]}
                  >
                    <View
                      style={[
                        styles.toggleThumb,
                        aiMode && styles.toggleThumbOn,
                      ]}
                    />
                  </View>
                </Pressable>
              </View>
              <View style={styles.groupBy}>
                <Text style={styles.groupByText}>Agrupar por:</Text>
                <Text style={styles.groupByValue}>Status</Text>
                <Icon name="chevron-down" size={14} color={theme.textMuted} />
              </View>
            </View>
          </View>

          <View style={styles.toolbar}>
            <View style={{ flex: 2, minWidth: 240 }}>
              <Input
                value={query}
                onChangeText={setQuery}
                placeholder="Buscar cards"
                iconLeft="search"
              />
            </View>
            <View style={{ flex: 1, minWidth: 180 }}>
              <Pressable
                style={styles.filterButton}
                onPress={() => setTypeFilter("")}
              >
                <Text style={styles.filterButtonText}>
                  {typeFilter || "Todos os tipos"}
                </Text>
                <Icon name="chevron-down" size={14} color={theme.textMuted} />
              </Pressable>
            </View>
            <Pressable style={styles.filterChip}>
              <Icon name="filter" size={14} color={theme.textMuted} />
              <Text style={styles.filterChipText}>Filtros</Text>
            </Pressable>
            {canRunAllBacklog && grouped.backlog.length > 0 ? (
              <Button
                title={`Play backlog (${grouped.backlog.length})`}
                iconLeft="play"
                size="sm"
                onPress={() => void moveColumnForward("backlog")}
              />
            ) : null}
            <Pressable
              style={styles.filterChip}
              onPress={() => setShowArchived((v) => !v)}
            >
              <Text style={styles.filterChipText}>
                {showArchived ? "Ocultar arquivados" : "Mostrar arquivados"}
              </Text>
            </Pressable>
          </View>
        </Card>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.board}
        >
          {COLUMN_ORDER.map((column) => {
            const items = grouped[column];
            const isHovered = hoverColumn === column && Boolean(draggingKey);
            return (
              <View
                key={column}
                ref={(node) => {
                  columnRefs.current[column] = node;
                }}
                style={[
                  styles.column,
                  isHovered && styles.columnHovered,
                ] as ViewStyle[]}
              >
                <View style={styles.columnHead}>
                  <View
                    style={[
                      styles.columnTag,
                      { backgroundColor: COLUMNS[column].tone },
                    ]}
                  />
                  <Text style={styles.columnTitle}>
                    {COLUMNS[column].label}
                  </Text>
                  <Text style={styles.columnCount}>{items.length}</Text>
                </View>

                <View style={styles.columnBody}>
                  {items.length === 0 ? (
                    <View style={styles.emptyColumn}>
                      <Text style={styles.emptyColumnText}>Sem cards</Text>
                    </View>
                  ) : (
                    items.map((item) => {
                      const latestRun = latestRunByItem.get(item.key);
                      const tone = typeToneFor(item.type);
                      const blocked = column === "blocked";
                      const card = (
                        <Card
                          padding={12}
                          style={[
                            styles.taskCard,
                            blocked && styles.taskCardBlocked,
                            draggingKey === item.key && styles.taskCardDragging,
                          ] as ViewStyle[]}
                        >
                          <View style={styles.taskCardHead}>
                            <Text
                              style={[
                                styles.taskCardKey,
                                blocked && { color: theme.danger },
                              ]}
                            >
                              {item.key}
                            </Text>
                            {blocked ? (
                              <View style={styles.blockedDot} />
                            ) : null}
                          </View>
                          <Text style={styles.taskCardTitle} numberOfLines={3}>
                            {item.title}
                          </Text>
                          <View style={styles.taskCardFooter}>
                            <View
                              style={[
                                styles.typeBadge,
                                { backgroundColor: tone.bg },
                              ]}
                            >
                              <Text
                                style={[styles.typeBadgeText, { color: tone.fg }]}
                              >
                                {tone.letter}
                              </Text>
                            </View>
                            {item.comments?.length ? (
                              <Text style={styles.commentCount}>
                                💬 {item.comments.length}
                              </Text>
                            ) : null}
                            {latestRun &&
                            (latestRun.state === "running" ||
                              latestRun.state === "done") ? (
                              <View
                                style={[
                                  styles.runDot,
                                  latestRun.state === "running"
                                    ? styles.runDotRunning
                                    : styles.runDotDone,
                                ]}
                              >
                                <Icon
                                  name="play"
                                  size={10}
                                  color={
                                    latestRun.state === "running"
                                      ? theme.primary
                                      : theme.success
                                  }
                                />
                              </View>
                            ) : null}
                            <View style={styles.assigneeAvatar}>
                              <Text style={styles.assigneeAvatarText}>
                                {(item.assignee?.[0] ?? "?").toUpperCase()}
                              </Text>
                            </View>
                          </View>
                        </Card>
                      );
                      if (Platform.OS === "web") {
                        return (
                          <View
                            key={item.id}
                            nativeID={`sprint-card-${domSafeToken(item.key)}`}
                            testID={`sprint-card-${item.key}`}
                            accessibilityRole="button"
                            {...getDragProps(item)}
                          >
                            {card}
                          </View>
                        );
                      }
                      return (
                        <Pressable
                          key={item.id}
                          onPress={() => void openItem(item)}
                        >
                          {card}
                        </Pressable>
                      );
                    })
                  )}
                  <Pressable
                    style={styles.addCardBtn}
                    onPress={() => nav.navigate("ProjectSetup")}
                  >
                    <Icon name="plus" size={13} color={theme.textMuted} />
                    <Text style={styles.addCardText}>Adicionar card</Text>
                  </Pressable>
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
        onClose={() => {
          setSelectedItem(null);
          setSelectedRunDetail(null);
        }}
      />
    </Screen>
  );
};

const compareRunAge = (
  left: ControlPlaneRunSummary,
  right: ControlPlaneRunSummary,
): number => {
  const leftValue = left.finished_at ?? left.started_at ?? "";
  const rightValue = right.finished_at ?? right.started_at ?? "";
  return leftValue.localeCompare(rightValue);
};

const resolveRunColumn = (
  run?: ControlPlaneRunSummary,
): ColumnKey | null => {
  if (!run) return null;
  if (run.failed || run.state === "failed") return "blocked";
  if (run.state === "done") return "awaiting_deploy";
  if (
    (run.last_step ?? 0) >= 8 ||
    run.readiness_verdict === "needs_human_approval"
  )
    return "review";
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
  if (manualColumn && runColumn) {
    return COLUMN_ORDER.indexOf(manualColumn) >= COLUMN_ORDER.indexOf(runColumn)
      ? manualColumn
      : runColumn;
  }
  if (runColumn) return runColumn;
  if (manualColumn) return manualColumn;
  const status = item.status.toLowerCase();
  if (status.includes("block")) return "blocked";
  if (
    status.includes("review") ||
    status.includes("qa") ||
    status.includes("homolog")
  )
    return "review";
  if (status.includes("test")) return "testing";
  if (
    status.includes("progress") ||
    status.includes("doing") ||
    status.includes("develop") ||
    status.includes("coding")
  )
    return "programming";
  if (status.includes("plan") || status.includes("analysis")) return "planning";
  if (status.includes("deploy") || status.includes("ready"))
    return "awaiting_deploy";
  return "backlog";
};

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

const isDetailTab = (value?: string | null): value is DetailTab =>
  value === "overview" ||
  value === "logs" ||
  value === "timeline" ||
  value === "readiness" ||
  value === "evidence";

const ItemDetailModal: React.FC<{
  item: SprintItem | null;
  detail: ControlPlaneRunDetail | null;
  tab: DetailTab;
  onTabChange: (tab: DetailTab) => void;
  loading: boolean;
  onClose: () => void;
}> = ({ item, detail, tab, onTabChange, loading, onClose }) => {
  const descriptionText =
    htmlToPlainText(item?.description) ??
    "Sem descrição de origem para este card.";
  const acceptanceText = htmlToPlainText(item?.acceptance_criteria);
  const acceptanceItems = acceptanceText
    ? acceptanceText
        .split(/\n|;|\./)
        .map((c) => c.trim())
        .filter(Boolean)
    : [
        "Cobrar cartão de crédito com sucesso",
        "Cobrar via PIX com sucesso",
        "Tratar falhas de pagamento",
        "Retornar status e código de transação",
      ];

  const readiness = Math.round(
    (item?.story_points ?? 5) * 20 > 100 ? 95 : (item?.story_points ?? 5) * 18 + 30,
  );

  return (
    <Modal
      visible={Boolean(item)}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={modalStyles.backdrop}>
        <View style={modalStyles.card}>
          <View style={modalStyles.header}>
            <View style={{ flex: 1 }}>
              <View style={modalStyles.headerRow}>
                <Text style={modalStyles.headerKey}>{item?.key ?? "Item"}</Text>
                <Text style={modalStyles.headerTitle}>
                  {item?.title ?? "Sem título"}
                </Text>
                <View style={modalStyles.headerStatusChip}>
                  <Text style={modalStyles.headerStatusText}>
                    {item?.status ?? "Programming"}
                  </Text>
                </View>
              </View>
              <View style={modalStyles.headerMeta}>
                <Text style={modalStyles.metaItem}>
                  <Text style={modalStyles.metaKey}>Tipo: </Text>
                  <Text style={modalStyles.metaValue}>
                    {item?.type ?? "Task"}
                  </Text>
                </Text>
                <Text style={modalStyles.metaItem}>
                  <Text style={modalStyles.metaKey}>Prioridade: </Text>
                  <Text style={modalStyles.metaValue}>Média</Text>
                </Text>
                <Text style={modalStyles.metaItem}>
                  <Text style={modalStyles.metaKey}>Story Points: </Text>
                  <Text style={modalStyles.metaValue}>
                    {item?.story_points ?? 3}
                  </Text>
                </Text>
                <Text style={modalStyles.metaItem}>
                  <Text style={modalStyles.metaKey}>Responsável: </Text>
                  <Text style={modalStyles.metaValue}>
                    @{item?.assignee ?? "joao.silva"}
                  </Text>
                </Text>
              </View>
            </View>
            <Pressable onPress={onClose} style={modalStyles.closeBtn}>
              <Icon name="x" size={18} color={theme.textMuted} />
            </Pressable>
          </View>

          <View style={modalStyles.tabs}>
            {[
              ["overview", "Visão geral"],
              ["logs", "Logs"],
              ["timeline", "Timeline"],
              ["evidence", "Evidências"],
              ["readiness", "Readiness"],
            ].map(([key, label]) => (
              <Pressable
                key={key}
                onPress={() => onTabChange(key as DetailTab)}
                style={[
                  modalStyles.tab,
                  tab === key && modalStyles.tabActive,
                ]}
              >
                <Text
                  style={[
                    modalStyles.tabText,
                    tab === key && modalStyles.tabTextActive,
                  ]}
                >
                  {label}
                </Text>
              </Pressable>
            ))}
          </View>

          <ScrollView style={modalStyles.scroll}>
            {tab === "overview" ? (
              <View style={modalStyles.grid}>
                <View style={modalStyles.col}>
                  <Section title="Descrição">
                    <Text style={modalStyles.body}>{descriptionText}</Text>
                  </Section>
                  <Section title="Critérios de aceite">
                    {acceptanceItems.slice(0, 5).map((c) => (
                      <View key={c} style={modalStyles.checkLine}>
                        <View style={modalStyles.checkDot}>
                          <Icon name="check" size={10} color="#fff" />
                        </View>
                        <Text style={modalStyles.body}>{c}</Text>
                      </View>
                    ))}
                  </Section>
                  <Section title="Links">
                    <View style={modalStyles.linkLine}>
                      <Icon name="link" size={13} color={theme.primary} />
                      <Text style={modalStyles.link}>Especificação técnica</Text>
                    </View>
                    <View style={modalStyles.linkLine}>
                      <Icon name="link" size={13} color={theme.primary} />
                      <Text style={modalStyles.link}>
                        API - Gateway de Pagamentos
                      </Text>
                    </View>
                  </Section>
                </View>

                <View style={modalStyles.col}>
                  <Section title={`Logs (últimas ${(detail?.logs ?? []).length || 30} linhas)`}>
                    <View style={modalStyles.logBox}>
                      {(detail?.logs?.length
                        ? detail.logs
                        : [
                            "10:31:03 [INFO]  Iniciando execução da tarefa PLAT-73",
                            "10:31:05 [INFO]  Adicionando dependências...",
                            "10:31:07 [INFO]  Compilando...",
                            "10:31:14 [INFO]  Rodando testes unitários...",
                            "10:31:34 [SUCCESS] Todos os testes passaram",
                            "10:31:46 [INFO]  Salvando evidências...",
                            "10:31:48 [INFO]  Atualizando status para Review Humana",
                          ]
                      )
                        .slice(-8)
                        .map((line, idx) => (
                          <Text key={idx} style={modalStyles.logLine}>
                            {line}
                          </Text>
                        ))}
                    </View>
                    <Pressable>
                      <Text style={modalStyles.link}>Abrir logs completos</Text>
                    </Pressable>
                  </Section>

                  <Section
                    title={`Evidências (${detail?.evidence?.items?.length ?? 3})`}
                    rightAction="Ver todas"
                  >
                    <View style={modalStyles.evidenceGrid}>
                      {(detail?.evidence?.items?.length
                        ? detail.evidence.items.slice(0, 3)
                        : [
                            { label: "Browser", path: "" },
                            { label: "Console", path: "" },
                            { label: "Board", path: "" },
                          ]
                      ).map((e, idx) => (
                        <View key={idx} style={modalStyles.evidenceTile}>
                          <Text style={modalStyles.evidenceTileText}>
                            {e.label}
                          </Text>
                        </View>
                      ))}
                    </View>
                  </Section>

                  <Section
                    title="Readiness"
                    rightAction={`${readiness}%`}
                  >
                    <View style={modalStyles.readinessTrack}>
                      <View
                        style={[
                          modalStyles.readinessFill,
                          { width: `${readiness}%` },
                        ]}
                      />
                    </View>
                  </Section>
                </View>
              </View>
            ) : null}

            {tab === "logs" ? (
              <Section title="Logs do SendSprint">
                {loading ? (
                  <ActivityIndicator color={theme.primary} />
                ) : (detail?.logs ?? []).length === 0 ? (
                  <Text style={modalStyles.body}>Sem logs capturados.</Text>
                ) : (
                  detail?.logs.map((line, idx) => (
                    <Text key={idx} style={modalStyles.logLine}>
                      {line}
                    </Text>
                  ))
                )}
              </Section>
            ) : null}

            {tab === "timeline" ? (
              <Section title="Histórico do board">
                {item?.history.length ? (
                  item.history.map((h, idx) => (
                    <Text key={idx} style={modalStyles.logLine}>
                      {`${h.observed_at ?? "-"} · ${h.action ?? "-"} · ${h.from_column ?? "-"} → ${h.to_column ?? "-"}`}
                    </Text>
                  ))
                ) : (
                  <Text style={modalStyles.body}>Sem eventos ainda.</Text>
                )}
              </Section>
            ) : null}

            {tab === "evidence" ? (
              <Section title="Evidências">
                {item?.attachments.length ? (
                  item.attachments.map((a, idx) => (
                    <Text key={idx} style={modalStyles.logLine}>
                      {a.filename ?? "arquivo"} · {a.url ?? "-"}
                    </Text>
                  ))
                ) : (
                  <Text style={modalStyles.body}>
                    Nenhuma evidência registrada ainda.
                  </Text>
                )}
              </Section>
            ) : null}

            {tab === "readiness" ? (
              <Section title="Readiness">
                {detail?.quality_gate ? (
                  <>
                    <Text style={modalStyles.body}>
                      Veredito: {detail.quality_gate.verdict}
                    </Text>
                    {detail.quality_gate.checks.map((check) => (
                      <Text key={check.check_name} style={modalStyles.logLine}>
                        {check.check_name} · {check.passed ? "ok" : "failed"}
                      </Text>
                    ))}
                  </>
                ) : (
                  <Text style={modalStyles.body}>
                    Sem quality gate calculado.
                  </Text>
                )}
              </Section>
            ) : null}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const Section: React.FC<{
  title: string;
  rightAction?: string;
  children: React.ReactNode;
}> = ({ title, rightAction, children }) => (
  <View style={modalStyles.section}>
    <View style={modalStyles.sectionHead}>
      <Text style={modalStyles.sectionTitle}>{title}</Text>
      {rightAction ? (
        <Text style={modalStyles.sectionRight}>{rightAction}</Text>
      ) : null}
    </View>
    {children}
  </View>
);

const styles = StyleSheet.create({
  boardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 14,
    marginBottom: 16,
  },
  boardHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  boardHeaderRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  boardIcon: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  boardTitle: {
    color: theme.text,
    fontSize: 17,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  boardSubtitle: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 2,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  toggleLabel: {
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  toggleTrack: {
    width: 40,
    height: 22,
    borderRadius: 12,
  },
  toggleTrackInner: {
    flex: 1,
    borderRadius: 12,
    backgroundColor: theme.borderStrong,
    padding: 3,
  },
  toggleTrackInnerOn: {
    backgroundColor: theme.primary,
  },
  toggleThumb: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: "#fff",
  },
  toggleThumbOn: {
    transform: [{ translateX: 18 }],
  },
  groupBy: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 8,
  },
  groupByText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  groupByValue: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  filterButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    minHeight: 40,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  filterButtonText: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  filterChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  filterChipText: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  board: {
    gap: 12,
    paddingBottom: 16,
    paddingHorizontal: 0,
  },
  column: {
    width: 244,
    backgroundColor: theme.surfaceAlt,
    borderRadius: 12,
    padding: 12,
    gap: 12,
  },
  columnHovered: {
    backgroundColor: theme.primaryFaint,
    borderWidth: 2,
    borderColor: theme.primary,
    padding: 10,
  },
  columnHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 4,
  },
  columnTag: {
    width: 4,
    height: 14,
    borderRadius: 2,
  },
  columnTitle: {
    flex: 1,
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  columnCount: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  columnBody: {
    gap: 10,
  },
  emptyColumn: {
    paddingVertical: 22,
    alignItems: "center",
  },
  emptyColumnText: {
    color: theme.textSoft,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  taskCard: {
    backgroundColor: theme.surface,
    gap: 8,
    cursor: "grab" as any,
  },
  taskCardBlocked: {
    backgroundColor: theme.dangerSoft,
    borderColor: "rgba(220, 38, 38, 0.2)",
  },
  taskCardDragging: {
    opacity: 0.7,
    transform: [{ rotate: "1deg" }],
  },
  taskCardHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  taskCardKey: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontMono,
  },
  blockedDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.danger,
  },
  taskCardTitle: {
    color: theme.text,
    fontSize: 13,
    lineHeight: 17,
    fontFamily: theme.fontSans,
  },
  taskCardFooter: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 4,
  },
  typeBadge: {
    width: 20,
    height: 20,
    borderRadius: 5,
    alignItems: "center",
    justifyContent: "center",
  },
  typeBadgeText: {
    fontSize: 11,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  commentCount: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  runDot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: "auto",
  },
  runDotRunning: {
    backgroundColor: theme.primaryFaint,
  },
  runDotDone: {
    backgroundColor: theme.successSoft,
  },
  assigneeAvatar: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: theme.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  assigneeAvatarText: {
    color: theme.textMuted,
    fontSize: 10,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  addCardBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: theme.border,
    borderStyle: "dashed",
  },
  addCardText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
});

const modalStyles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.5)",
    padding: 24,
    justifyContent: "center",
  },
  card: {
    width: "100%",
    maxWidth: 1080,
    maxHeight: "92%",
    alignSelf: "center",
    backgroundColor: theme.surface,
    borderRadius: 14,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    padding: 24,
    paddingBottom: 14,
    gap: 14,
    alignItems: "flex-start",
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
  },
  headerKey: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "800",
    fontFamily: theme.fontMono,
  },
  headerTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    flexShrink: 1,
  },
  headerStatusChip: {
    backgroundColor: theme.primaryFaint,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  headerStatusText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  headerMeta: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 18,
    marginTop: 10,
  },
  metaItem: {
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  metaKey: {
    color: theme.textMuted,
  },
  metaValue: {
    color: theme.text,
    fontWeight: "600",
  },
  closeBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
    backgroundColor: theme.surfaceMuted,
  },
  tabs: {
    flexDirection: "row",
    gap: 4,
    paddingHorizontal: 24,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  tab: {
    paddingVertical: 12,
    paddingHorizontal: 4,
    marginRight: 16,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabActive: {
    borderBottomColor: theme.primary,
  },
  tabText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  tabTextActive: {
    color: theme.primary,
    fontWeight: "700",
  },
  scroll: {
    padding: 24,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 24,
  },
  col: {
    flex: 1,
    minWidth: 340,
    gap: 22,
  },
  section: {
    gap: 8,
  },
  sectionHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  sectionRight: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  body: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 19,
    fontFamily: theme.fontSans,
  },
  checkLine: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginTop: 6,
  },
  checkDot: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: theme.success,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  linkLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 6,
  },
  link: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  logBox: {
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    padding: 12,
    gap: 4,
  },
  logLine: {
    color: theme.text,
    fontSize: 11,
    fontFamily: theme.fontMono,
    lineHeight: 16,
  },
  evidenceGrid: {
    flexDirection: "row",
    gap: 10,
    flexWrap: "wrap",
  },
  evidenceTile: {
    width: 110,
    height: 70,
    borderRadius: 8,
    backgroundColor: theme.surfaceMuted,
    borderWidth: 1,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
  },
  evidenceTileText: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  readinessTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.surfaceMuted,
    overflow: "hidden",
    marginTop: 8,
  },
  readinessFill: {
    height: "100%",
    backgroundColor: theme.success,
    borderRadius: 999,
  },
});
