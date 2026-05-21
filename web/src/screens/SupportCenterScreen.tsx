import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { ControlPlaneRunSummary } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import {
  loadSupportTickets,
  saveSupportTickets,
  type SupportTicket,
  type SupportTicketCategory,
} from "../supportCenterStore";
import { useSession } from "../store/session";
import { theme } from "../theme";

const CATEGORIES: Array<{ key: SupportTicketCategory; label: string }> = [
  { key: "bug", label: "Bug" },
  { key: "integration", label: "Integracao" },
  { key: "workflow", label: "Workflow" },
  { key: "feature", label: "Feature" },
  { key: "question", label: "Pergunta" },
  { key: "billing", label: "Billing" },
];

export const SupportCenterScreen: React.FC = () => {
  const { api, session } = useSession();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [category, setCategory] = useState<SupportTicketCategory>("bug");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [linkedRunId, setLinkedRunId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async (background = false) => {
    if (!background) setLoading(true);
    setError(null);
    try {
      const [runList, localTickets] = await Promise.all([
        api.listControlPlaneRuns(),
        loadSupportTickets(),
      ]);
      setRuns(runList);
      setTickets(localTickets.sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)));
    } catch (nextError) {
      setError(getApiErrorMessage(nextError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [session.currentSprint?.sprintId]);

  const relevantRuns = useMemo(() => {
    if (!session.currentSprint) return runs.slice(0, 8);
    return runs
      .filter(
        (run) =>
          run.sprint_id === session.currentSprint?.sprintId &&
          String(run.provider) === String(session.currentSprint?.provider),
      )
      .slice(0, 8);
  }, [runs, session.currentSprint]);

  const metrics = useMemo(
    () => ({
      newCount: tickets.filter((ticket) => ticket.status === "new").length,
      triagedCount: tickets.filter((ticket) => ticket.status === "triaged").length,
      backlogCount: tickets.filter((ticket) => ticket.status === "backlog_candidate").length,
      resolvedCount: tickets.filter((ticket) => ticket.status === "resolved").length,
    }),
    [tickets],
  );

  const createTicket = async () => {
    if (!title.trim() || !description.trim()) return;
    setSaving(true);
    try {
      const now = new Date().toISOString();
      const next: SupportTicket = {
        id: `support-${Date.now().toString(36)}`,
        category,
        status: "new",
        title: title.trim(),
        description: description.trim(),
        linkedRunId,
        createdBy: session.appUser?.email ?? "local-operator",
        createdAt: now,
        updatedAt: now,
        diagnostics: {
          provider: session.currentSprint?.provider ?? session.provider ?? null,
          sprintId: session.currentSprint?.sprintId ?? null,
          sprintName: session.currentSprint?.sprintName ?? null,
          repoCount: session.projectSetup.repositories.length,
          runCount: relevantRuns.length,
        },
      };
      const updated = [next, ...tickets];
      await saveSupportTickets(updated);
      setTickets(updated);
      setTitle("");
      setDescription("");
      setLinkedRunId(null);
      setCategory("bug");
    } finally {
      setSaving(false);
    }
  };

  const setTicketStatus = async (
    ticketId: string,
    status: SupportTicket["status"],
    backlogReason?: string | null,
  ) => {
    const now = new Date().toISOString();
    const updated = tickets.map((ticket) =>
      ticket.id === ticketId
        ? {
            ...ticket,
            status,
            backlogReason: backlogReason ?? ticket.backlogReason ?? null,
            updatedAt: now,
          }
        : ticket,
    );
    setTickets(updated);
    await saveSupportTickets(updated);
  };

  if (loading) {
    return (
      <Screen
        chrome="app"
        eyebrow="Web 15 · Support Center"
        title="Support center"
        subtitle="Carregando tickets locais, runs e diagnosticos do workspace..."
      >
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  return (
    <Screen
      chrome="app"
      eyebrow="Web 15 · Support Center"
      title="Support center"
      subtitle="Cada item de suporte pode ser tratado, resolvido localmente ou promovido para backlog candidato."
      scroll={false}
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
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.kicker}>SUPPORT ERROR</Text>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        <View style={styles.metrics}>
          <MetricCard label="Novos" value={String(metrics.newCount)} />
          <MetricCard label="Triados" value={String(metrics.triagedCount)} accent="primary" />
          <MetricCard label="Candidatos backlog" value={String(metrics.backlogCount)} accent="warning" />
          <MetricCard label="Resolvidos" value={String(metrics.resolvedCount)} accent="success" />
        </View>

        <View style={styles.split}>
          <Card style={styles.primaryPanel}>
            <Text style={styles.kicker}>ABRIR NOVO CASO</Text>
            <View style={styles.categoryRow}>
              {CATEGORIES.map((option) => (
                <Card
                  key={option.key}
                  onPress={() => setCategory(option.key)}
                  selected={category === option.key}
                  style={styles.categoryCard}
                >
                  <Text style={styles.categoryLabel}>{option.label}</Text>
                </Card>
              ))}
            </View>

            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>Titulo</Text>
              <TextInput
                value={title}
                onChangeText={setTitle}
                placeholder="Ex: Azure fallback nao importou a sprint"
                placeholderTextColor={theme.textMuted}
                style={styles.input}
              />
            </View>

            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>Descricao</Text>
              <TextInput
                value={description}
                onChangeText={setDescription}
                placeholder="Descreva o problema, o impacto e os passos para reproduzir."
                placeholderTextColor={theme.textMuted}
                multiline
                textAlignVertical="top"
                style={[styles.input, styles.textarea]}
              />
            </View>

            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>Run vinculada</Text>
              <View style={styles.runChoices}>
                <Button
                  title={linkedRunId ? "Limpar vinculo" : "Sem vinculo"}
                  variant="secondary"
                  onPress={() => setLinkedRunId(null)}
                />
                {relevantRuns.slice(0, 4).map((run) => (
                  <Button
                    key={run.run_id}
                    title={run.run_id.slice(0, 10)}
                    variant={linkedRunId === run.run_id ? "primary" : "secondary"}
                    onPress={() => setLinkedRunId(run.run_id)}
                  />
                ))}
              </View>
            </View>

            <Button
              title="Registrar suporte"
              onPress={() => void createTicket()}
              loading={saving}
              disabled={!title.trim() || !description.trim()}
            />
          </Card>

          <Card style={styles.sidePanel}>
            <Text style={styles.kicker}>DIAGNOSTICOS ANEXADOS</Text>
            <SupportRow label="Usuario" value={session.appUser?.email ?? "local-operator"} />
            <SupportRow label="Sprint" value={session.currentSprint?.sprintName ?? "nenhuma"} />
            <SupportRow label="Provider" value={session.currentSprint?.provider ?? session.provider ?? "nao definido"} />
            <SupportRow label="Repos locais" value={String(session.projectSetup.repositories.length)} />
            <SupportRow label="Runs recentes" value={String(relevantRuns.length)} />
            <Text style={styles.sideNote}>
              O case fica salvo localmente e ja nasce com contexto suficiente para triagem ou promocao para backlog.
            </Text>
          </Card>
        </View>

        <Card>
          <Text style={styles.kicker}>CASOS ABERTOS</Text>
          {tickets.length === 0 ? (
            <Text style={styles.emptyText}>Nenhum caso local registrado ainda.</Text>
          ) : (
            tickets.map((ticket) => (
              <View key={ticket.id} style={styles.ticketRow}>
                <View style={{ flex: 1 }}>
                  <View style={styles.ticketHead}>
                    <Text style={styles.ticketTitle}>{ticket.title}</Text>
                    <StatusPill status={ticket.status} />
                  </View>
                  <Text style={styles.ticketMeta}>
                    {ticket.category} · {ticket.createdBy} · {ticket.updatedAt.slice(0, 16).replace("T", " ")}
                  </Text>
                  <Text style={styles.ticketBody}>{ticket.description}</Text>
                  <Text style={styles.ticketMeta}>
                    sprint={ticket.diagnostics.sprintName ?? "none"} · repos={ticket.diagnostics.repoCount} · runs={ticket.diagnostics.runCount}
                    {ticket.linkedRunId ? ` · run=${ticket.linkedRunId}` : ""}
                  </Text>
                  {ticket.backlogReason ? (
                    <Text style={styles.ticketBacklog}>backlog: {ticket.backlogReason}</Text>
                  ) : null}
                </View>
                <View style={styles.ticketActions}>
                  <Button
                    title="Triar"
                    variant="secondary"
                    onPress={() => void setTicketStatus(ticket.id, "triaged")}
                  />
                  <Button
                    title="Virar backlog"
                    variant="secondary"
                    onPress={() =>
                      void setTicketStatus(
                        ticket.id,
                        "backlog_candidate",
                        "Triage local sinalizou gap de produto ou fluxo.",
                      )
                    }
                  />
                  <Button
                    title="Resolver"
                    variant="secondary"
                    onPress={() => void setTicketStatus(ticket.id, "resolved")}
                  />
                </View>
              </View>
            ))
          )}
        </Card>
      </ScrollView>
    </Screen>
  );
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  accent?: "default" | "primary" | "warning" | "success";
}> = ({ label, value, accent = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        accent === "primary" && { color: theme.primary },
        accent === "warning" && { color: theme.warning },
        accent === "success" && { color: theme.success },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const SupportRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.inlineRow}>
    <Text style={styles.inlineLabel}>{label}</Text>
    <Text style={styles.inlineValue}>{value}</Text>
  </View>
);

const StatusPill: React.FC<{ status: SupportTicket["status"] }> = ({ status }) => {
  const label =
    status === "backlog_candidate"
      ? "backlog"
      : status === "resolved"
        ? "resolved"
        : status;
  return (
    <View
      style={[
        styles.statusPill,
        status === "triaged" && styles.statusTriaged,
        status === "backlog_candidate" && styles.statusBacklog,
        status === "resolved" && styles.statusResolved,
      ]}
    >
      <Text style={styles.statusText}>{label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  scroll: {
    gap: 12,
    paddingBottom: 24,
  },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  metricCard: {
    flex: 1,
    minWidth: 170,
  },
  metricLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    textTransform: "uppercase",
  },
  metricValue: {
    color: theme.text,
    fontSize: 28,
    fontWeight: "800",
    marginTop: 6,
  },
  split: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  primaryPanel: {
    flex: 1,
    minWidth: 420,
  },
  sidePanel: {
    width: 340,
    minWidth: 320,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 8,
  },
  categoryRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 12,
  },
  categoryCard: {
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  categoryLabel: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
  },
  formField: {
    gap: 6,
    marginBottom: 12,
  },
  fieldLabel: {
    color: theme.textMuted,
    fontSize: 12,
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  input: {
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: theme.text,
    fontSize: 15,
  },
  textarea: {
    minHeight: 120,
  },
  runChoices: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  inlineRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  inlineLabel: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
  },
  inlineValue: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  sideNote: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 10,
  },
  ticketRow: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  ticketHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "center",
  },
  ticketTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
    flex: 1,
  },
  ticketMeta: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 4,
    lineHeight: 18,
  },
  ticketBody: {
    color: theme.text,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 8,
  },
  ticketBacklog: {
    color: theme.warning,
    fontSize: 12,
    marginTop: 8,
    fontFamily: theme.fontMono,
  },
  ticketActions: {
    width: 150,
    gap: 8,
  },
  statusPill: {
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.10)",
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  statusTriaged: {
    backgroundColor: "rgba(255,181,106,0.16)",
  },
  statusBacklog: {
    backgroundColor: "rgba(193,138,23,0.14)",
  },
  statusResolved: {
    backgroundColor: "rgba(30,169,124,0.12)",
  },
  statusText: {
    color: theme.text,
    fontSize: 11,
    fontWeight: "800",
  },
  emptyText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
  },
  errorCard: {
    backgroundColor: "rgba(207,81,97,0.08)",
    borderColor: "rgba(207,81,97,0.22)",
  },
  errorText: {
    color: theme.danger,
    fontSize: 13,
    lineHeight: 20,
  },
});
