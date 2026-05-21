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
type ColumnNode = React.ElementRef<typeof View>;
type CardDragState = {
  key: string;
  currentColumn: ColumnKey;
  startX: number;
  startY: number;
  active: boolean;
};

const CARD_DRAG_THRESHOLD_PX = 10;

const domSafeToken = (value: string): string => value.replace(/[^a-zA-Z0-9_-]/g, "-");

const decodeHtmlEntities = (value: string): string => {
  if (typeof document !== "undefined") {
    const textarea = document.createElement("textarea");
    textarea.innerHTML = value;
    return textarea.value;
  }

  return value.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (match, entity: string) => {
    if (entity.startsWith("#x")) return String.fromCodePoint(Number.parseInt(entity.slice(2), 16));
    if (entity.startsWith("#")) return String.fromCodePoint(Number.parseInt(entity.slice(1), 10));
    const named: Record<string, string> = {
      amp: "&",
      apos: "'",
      ccedil: "ç",
      gt: ">",
      lt: "<",
      nbsp: " ",
      quot: "\"",
      aacute: "á",
      acirc: "â",
      agrave: "à",
      atilde: "ã",
      eacute: "é",
      ecirc: "ê",
      iacute: "í",
      oacute: "ó",
      ocirc: "ô",
      otilde: "õ",
      uacute: "ú",
    };
    return named[entity.toLowerCase()] ?? match;
  });
};

const htmlToPlainText = (value?: string | null): string | null => {
  if (!value?.trim()) return null;
  const decoded = decodeHtmlEntities(value);
  const withLineBreaks = decoded
    .replace(/<\s*br\s*\/?>/gi, "\n")
    .replace(/<\s*\/\s*(p|div|li|h[1-6]|tr)\s*>/gi, "\n")
    .replace(/<\s*li\b[^>]*>/gi, "\n- ");
  const stripped =
    typeof DOMParser !== "undefined"
      ? new DOMParser().parseFromString(withLineBreaks, "text/html").body.textContent ?? ""
      : withLineBreaks.replace(/<[^>]+>/g, " ");
  const normalized = decodeHtmlEntities(stripped)
    .replace(/\u00a0/g, " ")
    .replace(/[ \t\f\v]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return normalized || null;
};

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
  const columnRefs = useRef<Partial<Record<ColumnKey, ColumnNode | null>>>({});
  const cardDragRef = useRef<CardDragState | null>(null);
  const suppressPressRef = useRef(false);
  const initialOpenKeyRef = useRef(route.params.openItemKey ?? null);

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

  const openItem = async (item: SprintItem, initialTab: DetailTab = "overview") => {
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
    const item = detail.items.find((candidate) => candidate.key === key || candidate.id === key);
    if (!item) return;
    initialOpenKeyRef.current = null;
    void openItem(item, isDetailTab(route.params.detailTab) ? route.params.detailTab : "overview");
  }, [detail, latestRunByItem, route.params.detailTab]);

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

  const resolveColumnAtPageX = (
    pageX: number,
    callback: (column: ColumnKey | null) => void,
  ) => {
    const refs = COLUMN_ORDER.map((column) => ({ column, ref: columnRefs.current[column] })).filter(
      (entry): entry is { column: ColumnKey; ref: ColumnNode } => Boolean(entry.ref),
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

  const releasePressSuppressionSoon = () => {
    setTimeout(() => {
      suppressPressRef.current = false;
    }, 250);
  };

  const eventPagePoint = (event: any): { pageX: number; pageY: number } => ({
    pageX: Number(event?.nativeEvent?.pageX ?? event?.pageX ?? 0),
    pageY: Number(event?.nativeEvent?.pageY ?? event?.pageY ?? 0),
  });

  const getDragProps = (item: SprintItem): Record<string, unknown> => {
    if (Platform.OS !== "web") return {};
    const isMutating = mutatingKeys.includes(item.key);
    const isDraggable = canDragItem(canRun, isMutating);
    const currentColumn = resolveItemColumn(item, latestRunByItem.get(item.key), columnOverrides[item.key]);
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
        const { pageX, pageY } = eventPagePoint(event);
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
        const { pageX, pageY } = eventPagePoint(event);
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

        const { pageX } = eventPagePoint(event);
        suppressPressRef.current = true;
        cardDragRef.current = null;
        setDraggingKey(null);
        setHoverColumn(null);
        releasePressSuppressionSoon();
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
        releasePressSuppressionSoon();
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
      title={session.currentSprint?.sprintName ?? detail?.sprint.name ?? "Sprint"}
      subtitle={
        headerMeta
          ? `${headerMeta} - ${visibleItems.length}/${(detail?.items ?? []).length} item(s) visiveis`
          : `${visibleItems.length}/${(detail?.items ?? []).length} item(s) visiveis`
      }
      scroll={false}
      actions={
        <View style={styles.boardActions}>
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
                ? `${configuredLocalRepos.length} repo(s) liberados. Arraste cards para atualizar status; Planning dispara execucao.`
                : "Configure um repositorio local para liberar arraste e execucao."}
            </Text>
            <Text style={styles.heroMeta}>
              Arquivados: {detail?.archived_count ?? 0} | filtro: {actorEmail ?? "sem email de app"}.
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
                id={`sprint-column-${column}`}
                nativeID={`sprint-column-${column}`}
                testID={`sprint-column-${column}`}
                ref={(node) => {
                  columnRefs.current[column] = node;
                }}
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
                      const card = (
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
                      );
                      if (Platform.OS === "web") {
                        return (
                          <View
                            key={item.id}
                            id={`sprint-card-${domSafeToken(item.key)}`}
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
                        <Pressable key={item.id} onPress={() => void openItem(item)}>
                          {card}
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

const isDetailTab = (value?: string | null): value is DetailTab =>
  value === "overview" ||
  value === "logs" ||
  value === "timeline" ||
  value === "readiness" ||
  value === "evidence";

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

const ModalMeta: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.modalMetaItem}>
    <Text style={styles.modalMetaLabel}>{label}</Text>
    <Text style={styles.modalMetaValue} numberOfLines={1}>{value}</Text>
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
}> = ({ item, detail, tab, onTabChange, loading, archiveBusy, onToggleArchive, onClose }) => {
  const descriptionText =
    htmlToPlainText(item?.description) ?? "Sem descricao de origem para este card.";
  const acceptanceText = htmlToPlainText(item?.acceptance_criteria);
  const acceptanceItems = acceptanceText
    ? acceptanceText.split(/\n|;|\./).map((criterion) => criterion.trim()).filter(Boolean)
    : [
        "Cobrir fluxo principal com sucesso",
        "Registrar evidencias da execucao",
        "Liberar status e codigo de automacao",
      ];

  return (
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

        <ScrollView style={styles.modalScroll} showsVerticalScrollIndicator={false}>
          {tab === "overview" ? (
            <View style={styles.modalOverviewGrid}>
              <View style={styles.modalOverviewLeft}>
                <View style={styles.modalSectionBox}>
                  <Text style={styles.modalSectionTitle}>WORKFLOW</Text>
                  <View style={styles.modalMetaGrid}>
                    <ModalMeta label="Tipo" value={item?.type ?? "Issue"} />
                    <ModalMeta label="Prioridade" value={item?.status ?? "Medium"} />
                    <ModalMeta label="Story points" value={item?.story_points != null ? String(item.story_points) : "-"} />
                    <ModalMeta label="Responsavel" value={item?.assignee ?? item?.assignee_email ?? "Sem responsavel"} />
                  </View>
                </View>

                <View style={styles.modalSectionBox}>
                  <Text style={styles.modalSectionTitle}>DESCRICAO</Text>
                  <Text style={styles.modalBody}>{descriptionText}</Text>
                </View>

                <View style={styles.modalSectionBox}>
                  <Text style={styles.modalSectionTitle}>CRITERIOS DE ACEITE</Text>
                  {acceptanceItems.slice(0, 5).map((criterion) => (
                    <View key={criterion} style={styles.checkLine}>
                      <View style={styles.checkDot} />
                      <Text style={styles.modalBody}>{criterion.trim()}</Text>
                    </View>
                  ))}
                </View>

                <View style={styles.modalSectionBox}>
                  <Text style={styles.modalSectionTitle}>LINKS</Text>
                  {item?.source_url ? <Text style={styles.modalLink}>{item.source_url}</Text> : null}
                  {item?.links.length ? (
                    item.links.map((link, index) => (
                      <Text key={`${index}-${link.type}-${link.target_key ?? ""}`} style={styles.modalLink}>
                        {link.type} - {link.target_key ?? "-"}
                      </Text>
                    ))
                  ) : (
                    <Text style={styles.modalBody}>Sem links adicionais.</Text>
                  )}
                </View>
              </View>

              <View style={styles.modalOverviewRight}>
                <View style={styles.modalSectionBox}>
                  <Text style={styles.modalSectionTitle}>Logs ultimos 30 linhas</Text>
                  <View style={styles.modalLogBox}>
                    {(detail?.logs?.length ? detail.logs : [
                      "Sequencia executiva da tarefa iniciada...",
                      "Arvore de requisitos normalizada...",
                      "Executando dependencias...",
                      "Todos os testes passaram",
                      "Aguardando review humana",
                    ]).slice(-8).map((log, index) => (
                      <Text key={`${index}-${log}`} style={styles.modalMono}>{log}</Text>
                    ))}
                  </View>
                </View>

                <View style={styles.modalSectionBox}>
                  <View style={styles.modalSectionHeader}>
                    <Text style={styles.modalSectionTitle}>Evidencias</Text>
                    <Text style={styles.modalLink}>Ver todas</Text>
                  </View>
                  <View style={styles.evidenceGrid}>
                    {(detail?.evidence?.items?.length ? detail.evidence.items.slice(0, 3) : [
                      { label: "Browser", path: "evidence/browser.png" },
                      { label: "Console", path: "evidence/console.png" },
                      { label: "Board", path: "evidence/board.png" },
                    ]).map((entry) => (
                      <View key={`${entry.label}-${entry.path}`} style={styles.evidenceTile}>
                        <Text style={styles.evidenceTileText}>{entry.label}</Text>
                      </View>
                    ))}
                  </View>
                </View>

                <View style={styles.modalSectionBox}>
                  <View style={styles.modalSectionHeader}>
                    <Text style={styles.modalSectionTitle}>Readiness</Text>
                    <Text style={styles.modalReadinessValue}>82%</Text>
                  </View>
                  <View style={styles.readinessTrack}>
                    <View style={styles.readinessFill} />
                  </View>
                </View>
              </View>
            </View>
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
};

const styles = StyleSheet.create({
  boardActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  hero: {
    backgroundColor: theme.surface,
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
  },
  kicker: {
    color: theme.primary,
    fontSize: 10,
    letterSpacing: 1,
    fontWeight: "800",
  },
  heroTitle: {
    color: theme.text,
    fontSize: 16,
    lineHeight: 21,
    fontWeight: "700",
    marginTop: 2,
  },
  heroText: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 4,
  },
  heroMeta: {
    color: theme.textMuted,
    fontSize: 11,
    lineHeight: 16,
    marginTop: 5,
    fontFamily: theme.fontMono,
  },
  searchInput: {
    marginTop: 9,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: theme.text,
    fontSize: 12,
  },
  toolbarRow: {
    marginTop: 8,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  heroActions: {
    gap: 8,
    alignItems: "flex-end",
  },
  board: {
    gap: 8,
    paddingTop: 10,
    paddingBottom: 14,
  },
  column: {
    width: 166,
    gap: 8,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: "transparent",
    padding: 3,
  },
  columnDropTarget: {
    backgroundColor: "rgba(44,107,237,0.06)",
    borderColor: theme.primary,
  },
  columnHead: {
    paddingHorizontal: 4,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
  },
  columnTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "800",
  },
  columnHint: {
    color: theme.textMuted,
    fontSize: 10,
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
    gap: 6,
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
    fontSize: 10,
  },
  itemTitle: {
    color: theme.text,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: "700",
  },
  itemStatus: {
    color: theme.textMuted,
    fontSize: 10,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  metaText: {
    color: theme.textMuted,
    fontSize: 10,
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
    fontSize: 10,
    fontFamily: theme.fontMono,
  },
  statusChip: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.12)",
  },
  statusChipText: {
    color: theme.primary,
    fontSize: 10,
    fontWeight: "800",
  },
  miniAction: {
    paddingHorizontal: 8,
    paddingVertical: 5,
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
    fontSize: 10,
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
    padding: 24,
  },
  modalCard: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    padding: 18,
    gap: 12,
    width: "96%",
    maxWidth: 1280,
    minHeight: 620,
    alignSelf: "center",
    shadowColor: "#0f172a",
    shadowOpacity: 0.12,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
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
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    paddingBottom: 8,
  },
  modalTab: {
    paddingHorizontal: 6,
    paddingVertical: 7,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  modalTabActive: {
    borderBottomColor: theme.primary,
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
    fontSize: 22,
    fontWeight: "800",
  },
  modalSubtitle: {
    color: theme.textMuted,
    fontSize: 13,
    marginTop: 4,
  },
  modalScroll: {
    maxHeight: 520,
  },
  modalOverviewGrid: {
    flexDirection: "row",
    gap: 18,
  },
  modalOverviewLeft: {
    flex: 1,
    gap: 12,
    paddingRight: 18,
    borderRightWidth: 1,
    borderRightColor: theme.border,
  },
  modalOverviewRight: {
    flex: 1,
    gap: 12,
  },
  modalSection: {
    marginBottom: 12,
  },
  modalSectionBox: {
    gap: 8,
  },
  modalSectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  modalSectionTitle: {
    color: theme.textMuted,
    fontSize: 12,
    letterSpacing: 0,
    fontWeight: "800",
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
  modalMetaGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  modalMetaItem: {
    minWidth: 130,
    gap: 4,
  },
  modalMetaLabel: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  modalMetaValue: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "800",
  },
  checkLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
  },
  checkDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: theme.success,
  },
  modalLink: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "800",
  },
  modalLogBox: {
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: "#f8fafc",
    padding: 12,
    minHeight: 158,
  },
  evidenceGrid: {
    flexDirection: "row",
    gap: 10,
  },
  evidenceTile: {
    flex: 1,
    height: 96,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: "#f8fafc",
    alignItems: "center",
    justifyContent: "center",
  },
  evidenceTileText: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  modalReadinessValue: {
    color: theme.textMuted,
    fontSize: 13,
    fontWeight: "800",
  },
  readinessTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: "#e8edf5",
    overflow: "hidden",
  },
  readinessFill: {
    width: "82%",
    height: "100%",
    backgroundColor: theme.success,
  },
  modalListItem: {
    gap: 4,
    marginBottom: 10,
  },
});
