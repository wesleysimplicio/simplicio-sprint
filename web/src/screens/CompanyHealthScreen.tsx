import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type {
  AgentDashboardResponse,
  AuthStatus,
  Health,
  TupleDashboardResponse,
  ValidationDashboardResponse,
  VersionCheckResponse,
} from "../api/types";
import { loadSupportTickets } from "../supportCenterStore";
import { useSession } from "../store/session";
import { theme } from "../theme";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";

type HealthTab = "overview" | "operations" | "governance";

export const CompanyHealthScreen: React.FC = () => {
  const { api, session } = useSession();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [version, setVersion] = useState<VersionCheckResponse | null>(null);
  const [tuples, setTuples] = useState<TupleDashboardResponse | null>(null);
  const [agents, setAgents] = useState<AgentDashboardResponse | null>(null);
  const [validations, setValidations] = useState<ValidationDashboardResponse | null>(null);
  const [supportCount, setSupportCount] = useState(0);
  const [tab, setTab] = useState<HealthTab>("overview");

  const load = async (background = false) => {
    if (!background) setLoading(true);
    setError(null);
    try {
      const [healthState, authState, tupleState, agentState, validationState, versionState, supportTickets] =
        await Promise.all([
          api.health(),
          api.authStatus(),
          api.getTupleDashboard(),
          api.getAgentDashboard(),
          api.getValidationDashboard(),
          api.checkVersion().catch(() => null),
          loadSupportTickets(),
        ]);
      setHealth(healthState);
      setAuth(authState);
      setTuples(tupleState);
      setAgents(agentState);
      setValidations(validationState);
      setVersion(versionState);
      setSupportCount(supportTickets.length);
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

  const risks = useMemo(() => {
    const next: string[] = [];
    if (!health?.providers_configured.azuredevops && !health?.providers_configured.jira) {
      next.push("Nenhum provider de sprint configurado no backend local.");
    }
    if (!session.currentSprint) {
      next.push("Nenhuma sprint importada para o workspace atual.");
    }
    if (session.projectSetup.repositories.length === 0) {
      next.push("Nenhum repositorio local registrado no Project Setup.");
    }
    if ((tuples?.failed_runs ?? 0) > 0) {
      next.push(`${tuples?.failed_runs ?? 0} run(s) falharam e exigem revisao humana.`);
    }
    if ((validations?.lanes ?? []).some((lane) => lane.status === "failed")) {
      next.push("Ao menos uma validation lane terminou em failed.");
    }
    if (version?.status === "unavailable") {
      next.push("A checagem de versao publicada nao esta disponivel neste momento.");
    }
    return next;
  }, [
    health,
    session.currentSprint,
    session.projectSetup.repositories.length,
    tuples?.failed_runs,
    validations?.lanes,
    version?.status,
  ]);

  if (loading) {
    return (
      <Screen
        chrome="app"
        eyebrow="Web 14 - Company Health"
        title="Company health"
        subtitle="Carregando sinais de integracao, execucao e postura operacional..."
      >
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  return (
    <Screen
      chrome="app"
      eyebrow="Web 14 - Company Health"
      title="Saude do workspace"
      subtitle="Postura de integracao, adocao, execucao e suporte do slice Console + Web."
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
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.kicker}>HEALTH ERROR</Text>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        <View style={styles.tabRow}>
          {[
            ["overview", "Overview"],
            ["operations", "Operations"],
            ["governance", "Governance"],
          ].map(([value, label]) => (
            <Pressable
              key={value}
              onPress={() => setTab(value as HealthTab)}
              style={[styles.tab, tab === value && styles.tabActive]}
            >
              <Text style={[styles.tabText, tab === value && styles.tabTextActive]}>{label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.metrics}>
          <MetricCard
            label="Providers ativos"
            value={String(Number(Boolean(auth?.jira_configured)) + Number(Boolean(auth?.azuredevops_configured)))}
          />
          <MetricCard label="Repos locais" value={String(session.projectSetup.repositories.length)} accent="primary" />
          <MetricCard label="Runs ativas" value={String(tuples?.active_runs ?? 0)} accent="success" />
          <MetricCard label="Chamados locais" value={String(supportCount)} accent="warning" />
        </View>

        {tab === "overview" || tab === "operations" ? (
          <View style={styles.grid}>
            <Card style={styles.panel}>
              <Text style={styles.kicker}>INTEGRATION POSTURE</Text>
              <HealthRow label="API local" value={health?.ok ? "online" : "offline"} />
              <HealthRow label="Jira" value={auth?.jira_configured ? "configurado" : "nao configurado"} />
              <HealthRow label="Azure DevOps" value={auth?.azuredevops_configured ? "configurado" : "nao configurado"} />
              <HealthRow label="GitHub CLI" value={auth?.providers.github.configured ? "autenticado" : "nao autenticado"} />
              <HealthRow
                label="Versao"
                value={version ? `${version.current_version}${version.latest_version ? ` / ${version.latest_version}` : ""}` : "nao verificada"}
              />
            </Card>

            <Card style={styles.panel}>
              <Text style={styles.kicker}>OPERATIONS POSTURE</Text>
              <HealthRow label="Sprint atual" value={session.currentSprint?.sprintName ?? "nenhuma"} />
              <HealthRow label="Tuples observadas" value={String(tuples?.total_runs ?? 0)} />
              <HealthRow label="Falhas registradas" value={String(tuples?.failed_runs ?? 0)} />
              <HealthRow label="Agents expostos" value={String(agents?.agents.length ?? 0)} />
              <HealthRow label="Validation events" value={String(validations?.total_events ?? 0)} />
            </Card>
          </View>
        ) : null}

        {tab === "governance" ? (
          <Card>
            <Text style={styles.kicker}>ACTIVE RISKS</Text>
            {risks.length === 0 ? (
              <Text style={styles.bodyText}>Nenhum risco operacional evidente no slice local atual.</Text>
            ) : (
              risks.map((risk) => (
                <Text key={risk} style={styles.riskText}>
                  - {risk}
                </Text>
              ))
            )}
          </Card>
        ) : null}
      </ScrollView>
    </Screen>
  );
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  accent?: "default" | "primary" | "success" | "warning";
}> = ({ label, value, accent = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        accent === "primary" && { color: theme.primary },
        accent === "success" && { color: theme.success },
        accent === "warning" && { color: theme.warning },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const HealthRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.row}>
    <Text style={styles.rowLabel}>{label}</Text>
    <Text style={styles.rowValue}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  scroll: {
    gap: 12,
    paddingBottom: 24,
  },
  tabRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  tab: {
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surfaceAlt,
  },
  tabActive: {
    backgroundColor: "rgba(44,107,237,0.10)",
    borderColor: "rgba(44,107,237,0.24)",
  },
  tabText: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  tabTextActive: {
    color: theme.primary,
  },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  metricCard: {
    flex: 1,
    minWidth: 180,
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
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  panel: {
    flex: 1,
    minWidth: 320,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  rowLabel: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
  },
  rowValue: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  bodyText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
  },
  riskText: {
    color: theme.danger,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 4,
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
