import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
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
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Sprints">;
type NoticeKind = "loading" | "success" | "error" | "empty" | "info";
type Notice = {
  kind: NoticeKind;
  title: string;
  message: string;
  statusLine?: string | null;
};

export const SprintsScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [sprints, setSprints] = useState<SprintSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadNotice, setLoadNotice] = useState<Notice | null>(null);
  const [importNotice, setImportNotice] = useState<Notice | null>(null);
  const [importJob, setImportJob] = useState<{ id: string; status?: ImportStatus } | null>(null);

  const provider = session.provider ?? "jira";
  const providerLabel = provider === "azuredevops" ? "Azure DevOps" : "Jira";
  const listContext =
    provider === "azuredevops"
      ? session.adoTeamPath
        ? `team_path=${session.adoTeamPath}`
        : "team_path salvo no perfil local"
      : session.jiraBoardId
        ? `board_id=${session.jiraBoardId}`
        : "board_id nao informado";

  const load = async () => {
    setLoading(true);
    setLoadNotice({
      kind: "loading",
      title: "Buscando sprints",
      message: `Consultando ${providerLabel} via backend local (${listContext}).`,
    });
    try {
      const list = await api.listSprints(provider, {
        board_id: session.jiraBoardId ?? undefined,
        team_path: session.adoTeamPath ?? undefined,
      });
      setSprints(list);
      setLoadNotice(
        list.length === 0
          ? {
              kind: "empty",
              title: "Nenhuma sprint ativa encontrada",
              message:
                provider === "azuredevops"
                  ? "O backend respondeu sem sprints para o time salvo. Confirme a sprint URL/PAT e tente autenticar novamente se o time estiver incorreto."
                  : "O backend respondeu sem sprints para o board informado. Confirme o Board ID ou tente autenticar novamente.",
            }
          : {
              kind: "success",
              title: "Sprints carregadas",
              message: `${list.length} sprint(s) ativa(s) retornada(s) pelo backend.`,
            },
      );
    } catch (e) {
      setSprints([]);
      setLoadNotice({
        kind: "error",
        title: "Nao foi possivel listar sprints",
        message: getApiErrorMessage(e),
        statusLine: getApiErrorStatusLine(e),
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [provider, session.jiraBoardId, session.adoTeamPath]);

  useEffect(() => {
    if (!importJob?.id) return;
    const jobId = importJob.id;
    let stopped = false;

    const poll = async () => {
      try {
        const status = await api.importStatus(jobId);
        if (stopped) return;
        setImportJob({ id: jobId, status });
        if (status.state === "running") {
          setImportNotice({
            kind: "loading",
            title: "Importando sprints",
            message: `Job ${jobId}: ${status.fetched}/${status.total ?? "?"} sprint(s) lidas.`,
          });
          return;
        }
        setImportNotice({
          kind: status.state === "done" ? "success" : "error",
          title: status.state === "done" ? "Importacao concluida" : "Importacao falhou",
          message:
            status.state === "done"
              ? `Job ${jobId}: ${status.fetched}/${status.total ?? status.fetched} sprint(s) importadas.`
              : status.error || "O backend encerrou o job sem detalhes adicionais.",
        });
        clearInterval(interval);
      } catch (e) {
        if (stopped) return;
        setImportNotice({
          kind: "error",
          title: "Falha ao consultar importacao",
          message: getApiErrorMessage(e),
          statusLine: getApiErrorStatusLine(e),
        });
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
    setImportNotice({
      kind: "loading",
      title: "Iniciando importacao",
      message: "Solicitando um job em background no backend local.",
    });
    try {
      const job = await api.importSprints(provider, {
        board_id: session.jiraBoardId ?? undefined,
        team_path: session.adoTeamPath ?? undefined,
      });
      setImportJob({ id: job.job_id });
      setImportNotice({
        kind: "loading",
        title: "Importacao iniciada",
        message: `Job ${job.job_id} criado. Acompanhando status do backend.`,
      });
    } catch (e) {
      setImportJob(null);
      setImportNotice({
        kind: "error",
        title: "Nao foi possivel importar",
        message: getApiErrorMessage(e),
        statusLine: getApiErrorStatusLine(e),
      });
    }
  };

  const importRunning = importJob?.status?.state === "running" || Boolean(importJob && !importJob.status);

  return (
    <Screen
      title="Sprints ativas"
      subtitle={`Provedor: ${providerLabel}${session.account ? ` | ${session.account}` : ""}`}
      footer={
        <Button
          title={
            importRunning
              ? `Importando... ${importJob?.status?.fetched ?? 0}/${importJob?.status?.total ?? "?"}`
              : "Importar todas em background"
          }
          onPress={handleImportAll}
          variant="secondary"
          loading={importRunning}
        />
      }
    >
      {importNotice ? <NoticePanel notice={importNotice} /> : null}

      {loading ? (
        <NoticePanel notice={loadNotice ?? loadingNotice(providerLabel, listContext)} />
      ) : loadNotice?.kind === "error" ? (
        <NoticePanel notice={loadNotice} actionTitle="Tentar novamente" onAction={load} />
      ) : sprints.length === 0 ? (
        <NoticePanel
          notice={loadNotice ?? emptyNotice(provider)}
          actionTitle="Atualizar"
          onAction={load}
        />
      ) : (
        <>
          {loadNotice ? <NoticePanel notice={loadNotice} compact /> : null}
          <ScrollView
            contentContainerStyle={styles.scroll}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={theme.primary} />}
          >
            {sprints.map((s) => (
              <Card
                key={s.id}
                onPress={() => nav.navigate("SprintDetail", { sprintId: s.id })}
                style={{ marginBottom: 12 }}
              >
                <View style={styles.row}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.name}>{s.name || "Sprint sem nome"}</Text>
                    {s.goal ? <Text style={styles.goal}>"{s.goal}"</Text> : null}
                    <View style={styles.meta}>
                      {s.item_count != null ? (
                        <Text style={styles.metaText}>Itens: {s.item_count}</Text>
                      ) : null}
                      {s.start_date ? (
                        <Text style={styles.metaText}>Inicio: {String(s.start_date).slice(0, 10)}</Text>
                      ) : null}
                      <View style={styles.badge}>
                        <Text style={styles.badgeText}>{s.state || "active"}</Text>
                      </View>
                    </View>
                  </View>
                  <Text style={styles.chev}>&gt;</Text>
                </View>
              </Card>
            ))}
          </ScrollView>
        </>
      )}
    </Screen>
  );
};

const loadingNotice = (providerLabel: string, listContext: string): Notice => ({
  kind: "loading",
  title: "Buscando sprints",
  message: `Consultando ${providerLabel} via backend local (${listContext}).`,
});

const emptyNotice = (provider: "jira" | "azuredevops"): Notice => ({
  kind: "empty",
  title: "Nenhuma sprint ativa encontrada",
  message:
    provider === "azuredevops"
      ? "O backend respondeu sem sprints para o time salvo. Confirme a sprint URL/PAT e tente autenticar novamente se o time estiver incorreto."
      : "O backend respondeu sem sprints para o board informado. Confirme o Board ID ou tente autenticar novamente.",
});

const NoticePanel: React.FC<{
  notice: Notice;
  compact?: boolean;
  actionTitle?: string;
  onAction?: () => void;
}> = ({ notice, compact, actionTitle, onAction }) => (
  <View
    style={[
      styles.notice,
      compact && styles.noticeCompact,
      notice.kind === "loading" && styles.noticeLoading,
      notice.kind === "success" && styles.noticeSuccess,
      notice.kind === "error" && styles.noticeError,
      notice.kind === "empty" && styles.noticeEmpty,
    ]}
  >
    <View style={styles.noticeHeader}>
      {notice.kind === "loading" ? <ActivityIndicator color={theme.primary} size="small" /> : null}
      <Text style={styles.noticeTitle}>{notice.title}</Text>
    </View>
    <Text style={styles.noticeText}>{notice.message}</Text>
    {notice.statusLine ? <Text style={styles.noticeMeta}>Backend: {notice.statusLine}</Text> : null}
    {actionTitle && onAction ? (
      <View style={styles.noticeAction}>
        <Button title={actionTitle} onPress={onAction} variant="secondary" />
      </View>
    ) : null}
  </View>
);

const styles = StyleSheet.create({
  scroll: { paddingBottom: 16 },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  name: { color: theme.text, fontSize: 16, fontWeight: "700" },
  goal: { color: theme.primarySoft, fontSize: 13, fontStyle: "italic", marginTop: 2 },
  meta: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 8, alignItems: "center" },
  metaText: { color: theme.textMuted, fontSize: 12 },
  badge: {
    backgroundColor: "rgba(52, 211, 153, 0.18)",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
  },
  badgeText: { color: theme.success, fontSize: 11, fontWeight: "700", textTransform: "uppercase" },
  chev: { color: theme.primarySoft, fontSize: 22, fontWeight: "500" },
  notice: {
    borderRadius: theme.radius,
    borderWidth: 1,
    padding: 14,
    gap: 6,
    marginBottom: 12,
  },
  noticeCompact: { paddingVertical: 10 },
  noticeLoading: {
    backgroundColor: theme.surfaceAlt,
    borderColor: theme.primarySoft,
  },
  noticeSuccess: {
    backgroundColor: "rgba(30, 169, 124, 0.10)",
    borderColor: theme.success,
  },
  noticeError: {
    backgroundColor: "rgba(207, 81, 97, 0.10)",
    borderColor: theme.danger,
  },
  noticeEmpty: {
    backgroundColor: "rgba(255, 181, 106, 0.14)",
    borderColor: theme.accentWarm,
  },
  noticeHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  noticeTitle: { color: theme.text, fontSize: 14, fontWeight: "800" },
  noticeText: { color: theme.textMuted, fontSize: 13, lineHeight: 18 },
  noticeMeta: { color: theme.textMuted, fontSize: 12, fontFamily: theme.fontMono },
  noticeAction: { marginTop: 6 },
});
