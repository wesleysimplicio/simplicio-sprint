import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { getApiErrorMessage, getApiErrorStatusLine } from "../api/client";
import type { ImportStatus, SprintSummary } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Sprints">;

const PIPELINE_STEPS = [
  "Coletando metadados",
  "Buscando issues",
  "Normalizando dados",
  "Enriquecendo contexto",
  "Analisando dependências",
  "Extraindo evidências",
  "Montando backlog",
  "Finalizando importação",
];

export const SprintsScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session, setCurrentSprint } = useSession();
  const [sprints, setSprints] = useState<SprintSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importJob, setImportJob] = useState<{
    id: string;
    status?: ImportStatus;
  } | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);

  const provider = session.provider ?? "jira";
  const providerLabel = provider === "azuredevops" ? "Azure DevOps" : "Jira";

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listSprints(provider, {
        board_id: session.jiraBoardId ?? undefined,
        team_path: session.adoTeamPath ?? undefined,
      });
      setSprints(list);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [provider, session.jiraBoardId, session.adoTeamPath]);

  useEffect(() => {
    if (!importJob?.id) return;
    setElapsedSec(0);
    const start = Date.now();
    const timer = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [importJob?.id]);

  useEffect(() => {
    if (!importJob?.id) return;
    const jobId = importJob.id;
    let stopped = false;

    const poll = async () => {
      try {
        const status = await api.importStatus(jobId);
        if (stopped) return;
        setImportJob({ id: jobId, status });
        setLogs((prev) => {
          const ts = formatTime(elapsedSec);
          const next = [
            ...prev,
            `${ts} [INFO]  ${status.fetched}/${status.total ?? "?"} sprint(s) lidas`,
          ];
          return next.slice(-8);
        });
        if (status.state !== "running") {
          clearInterval(interval);
          if (status.state === "done") {
            setTimeout(() => {
              setImportJob(null);
              void load();
            }, 800);
          }
        }
      } catch (e) {
        if (stopped) return;
        setError(getApiErrorMessage(e));
        clearInterval(interval);
      }
    };

    const interval = setInterval(poll, 1500);
    void poll();
    return () => {
      stopped = true;
      clearInterval(interval);
    };
  }, [api, importJob?.id]);

  const handleImportAll = async () => {
    setLogs([
      `${formatTime(0)} [INFO]  Iniciando importação no backend local`,
      `${formatTime(0)} [INFO]  Provedor: ${providerLabel}`,
    ]);
    try {
      const job = await api.importSprints(provider, {
        board_id: session.jiraBoardId ?? undefined,
        team_path: session.adoTeamPath ?? undefined,
      });
      setImportJob({ id: job.job_id });
    } catch (e) {
      setError(getApiErrorMessage(e));
      setImportJob(null);
    }
  };

  const importRunning =
    !!importJob && (importJob.status?.state === "running" || !importJob.status);

  if (importRunning) {
    return <ImportPipelineView
      providerLabel={providerLabel}
      sprintName={session.currentSprint?.sprintName ?? "Importação em curso"}
      jobId={importJob?.id ?? "—"}
      logs={logs}
      elapsedSec={elapsedSec}
      progress={importJob?.status?.fetched ?? 0}
      total={importJob?.status?.total ?? 8}
    />;
  }

  return (
    <Screen
      title="Sprints ativas"
      subtitle={`Provedor: ${providerLabel}${session.account ? ` · ${session.account}` : ""}`}
      actions={
        <Button
          title="Importar todas"
          iconLeft="download"
          onPress={handleImportAll}
        />
      }
    >
      {error ? (
        <Card variant="muted" padding={14}>
          <Text style={styles.errorTitle}>Não foi possível listar sprints</Text>
          <Text style={styles.errorText}>{error}</Text>
        </Card>
      ) : null}

      {loading ? (
        <Card padding={28}>
          <Text style={styles.emptyText}>Carregando sprints…</Text>
        </Card>
      ) : sprints.length === 0 ? (
        <Card padding={28} style={{ alignItems: "center", gap: 10 }}>
          <Icon name="sprint" size={40} color={theme.textMuted} />
          <Text style={styles.emptyTitle}>Nenhuma sprint ativa</Text>
          <Text style={styles.emptyText}>
            Importe sprints do {providerLabel} para começar.
          </Text>
          <Button
            title="Importar agora"
            iconLeft="download"
            onPress={handleImportAll}
          />
        </Card>
      ) : (
        <ScrollView
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={load}
              tintColor={theme.primary}
            />
          }
        >
          {sprints.map((s) => (
            <Pressable
              key={s.id}
              onPress={() => {
                void setCurrentSprint({
                  provider,
                  sprintId: s.id,
                  sprintName: s.name,
                  portfolioName:
                    provider === "azuredevops"
                      ? session.adoTeamPath?.split("/")[0] ?? null
                      : session.account?.split("@")[1]?.split(".")[0] ?? null,
                  projectName:
                    provider === "azuredevops"
                      ? session.adoTeamPath?.split("/")[1] ?? null
                      : session.account?.split("@")[1] ?? null,
                  teamName:
                    provider === "azuredevops"
                      ? session.adoTeamPath?.split("/")[2] ?? null
                      : null,
                });
                nav.navigate("SprintDetail", { sprintId: s.id });
              }}
              style={{ marginBottom: 10 }}
            >
              <Card>
                <View style={styles.sprintRow}>
                  <View style={styles.sprintIcon}>
                    <Icon name="sprint" size={20} color={theme.primary} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.sprintName}>
                      {s.name || "Sprint sem nome"}
                    </Text>
                    {s.goal ? (
                      <Text style={styles.sprintGoal}>"{s.goal}"</Text>
                    ) : null}
                    <View style={styles.sprintMeta}>
                      {s.item_count != null ? (
                        <Text style={styles.sprintMetaText}>
                          {s.item_count} itens
                        </Text>
                      ) : null}
                      {s.start_date ? (
                        <Text style={styles.sprintMetaText}>
                          · início {String(s.start_date).slice(0, 10)}
                        </Text>
                      ) : null}
                      <View style={styles.stateBadge}>
                        <Text style={styles.stateBadgeText}>
                          {s.state || "active"}
                        </Text>
                      </View>
                    </View>
                  </View>
                  <Icon name="chevron-right" size={16} color={theme.textMuted} />
                </View>
              </Card>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </Screen>
  );
};

const ImportPipelineView: React.FC<{
  providerLabel: string;
  sprintName: string;
  jobId: string;
  logs: string[];
  elapsedSec: number;
  progress: number;
  total: number;
}> = ({ providerLabel, sprintName, jobId, logs, elapsedSec, progress, total }) => {
  const stepIndex = Math.min(
    Math.floor((progress / Math.max(1, total)) * PIPELINE_STEPS.length),
    PIPELINE_STEPS.length - 1,
  );
  const pctOverall = Math.min(
    100,
    Math.round((progress / Math.max(1, total)) * 100),
  );
  return (
    <Screen>
      <Card padding={24}>
        <View style={styles.importHeader}>
          <View style={{ flex: 1 }}>
            <Text style={styles.importTitle}>
              Importando Sprint: {sprintName}
            </Text>
            <Text style={styles.importSubtitle}>
              ID {jobId} · {providerLabel}
            </Text>
          </View>
          <Button title="Ver logs" variant="secondary" onPress={() => {}} />
        </View>

        <View style={styles.stepsRow}>
          {PIPELINE_STEPS.map((step, idx) => {
            const done = idx < stepIndex;
            const current = idx === stepIndex;
            return (
              <View key={step} style={styles.stepItem}>
                <View style={styles.stepBubbleRow}>
                  <View
                    style={[
                      styles.stepBubble,
                      done && styles.stepBubbleDone,
                      current && styles.stepBubbleCurrent,
                    ]}
                  >
                    {done ? (
                      <Icon name="check" size={14} color="#fff" />
                    ) : (
                      <Text
                        style={[
                          styles.stepBubbleText,
                          current && { color: "#fff" },
                        ]}
                      >
                        {idx + 1}
                      </Text>
                    )}
                  </View>
                  {idx < PIPELINE_STEPS.length - 1 ? (
                    <View
                      style={[
                        styles.stepConnector,
                        done && styles.stepConnectorDone,
                      ]}
                    />
                  ) : null}
                </View>
                <Text
                  style={[
                    styles.stepLabel,
                    (done || current) && styles.stepLabelActive,
                  ]}
                  numberOfLines={2}
                >
                  {step}
                </Text>
              </View>
            );
          })}
        </View>

        <View style={styles.progressRow}>
          <Text style={styles.progressLabel}>Progresso geral</Text>
          <Text style={styles.progressMeta}>
            Tempo decorrido: {formatTime(elapsedSec)}
          </Text>
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${pctOverall}%` }]} />
        </View>

        <Card variant="muted" padding={16} style={{ marginTop: 18 }}>
          <Text style={styles.logsTitle}>Log em tempo real</Text>
          {logs.map((line, idx) => (
            <Text key={idx} style={styles.logLine}>
              {line}
            </Text>
          ))}
        </Card>
      </Card>
    </Screen>
  );
};

const formatTime = (sec: number): string => {
  const h = Math.floor(sec / 3600)
    .toString()
    .padStart(2, "0");
  const m = Math.floor((sec % 3600) / 60)
    .toString()
    .padStart(2, "0");
  const s = (sec % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
};

const styles = StyleSheet.create({
  errorTitle: {
    color: theme.danger,
    fontSize: 13,
    fontWeight: "700",
  },
  errorText: {
    color: theme.danger,
    fontSize: 12,
    fontFamily: theme.fontMono,
    marginTop: 4,
    lineHeight: 18,
  },
  emptyTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginTop: 8,
  },
  emptyText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  sprintRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  sprintIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: theme.primaryFaint,
    alignItems: "center",
    justifyContent: "center",
  },
  sprintName: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  sprintGoal: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 3,
  },
  sprintMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 8,
    flexWrap: "wrap",
  },
  sprintMetaText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  stateBadge: {
    backgroundColor: theme.successSoft,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
  },
  stateBadgeText: {
    color: theme.success,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  importHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 24,
  },
  importTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  importSubtitle: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  stepsRow: {
    flexDirection: "row",
    gap: 4,
    marginTop: 8,
    marginBottom: 28,
  },
  stepItem: {
    flex: 1,
    alignItems: "center",
    minWidth: 80,
  },
  stepBubbleRow: {
    flexDirection: "row",
    alignItems: "center",
    width: "100%",
    justifyContent: "center",
  },
  stepBubble: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: theme.surfaceMuted,
    borderWidth: 1,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
  },
  stepBubbleDone: {
    backgroundColor: theme.success,
    borderColor: theme.success,
  },
  stepBubbleCurrent: {
    backgroundColor: theme.primary,
    borderColor: theme.primary,
  },
  stepBubbleText: {
    color: theme.textMuted,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  stepConnector: {
    flex: 1,
    height: 2,
    backgroundColor: theme.border,
    marginHorizontal: 4,
  },
  stepConnectorDone: {
    backgroundColor: theme.success,
  },
  stepLabel: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
    textAlign: "center",
    marginTop: 8,
    lineHeight: 14,
  },
  stepLabelActive: {
    color: theme.text,
    fontWeight: "600",
  },
  progressRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 6,
  },
  progressLabel: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  progressMeta: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  progressTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.surfaceMuted,
    overflow: "hidden",
    marginTop: 10,
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: theme.primary,
  },
  logsTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginBottom: 8,
  },
  logLine: {
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontMono,
    lineHeight: 18,
  },
});
