import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { AuthStatus } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "CompanyAdmin">;
type AdminTab = "overview" | "users" | "approvals" | "policies";

export const CompanyAdminScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [tab, setTab] = useState<AdminTab>("overview");

  const load = async (background = false) => {
    if (!background) setLoading(true);
    setError(null);
    try {
      setStatus(await api.authStatus());
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

  const deployTargets = useMemo(
    () =>
      Array.from(
        new Set(
          [session.projectSetup.deployTargetBranch.trim()].filter(Boolean),
        ),
      ),
    [session.projectSetup.deployTargetBranch],
  );

  const validationCommands = useMemo(
    () =>
      session.projectSetup.repositories.reduce(
        (sum, repository) => sum + repository.validationCommands.length,
        0,
      ),
    [session.projectSetup.repositories],
  );

  const approvals = useMemo(
    () => [
      {
        label: "Run all backlog",
        value: session.appUser?.permissions?.canRunAllBacklog ? "Liberado" : "Restrito",
      },
      {
        label: "Deploy target",
        value: deployTargets.join(", ") || "dev",
      },
      {
        label: "Provider padrao",
        value: status?.default_provider ?? session.provider ?? "none",
      },
    ],
    [deployTargets, session.appUser?.permissions?.canRunAllBacklog, session.provider, status?.default_provider],
  );

  if (loading) {
    return (
      <Screen
        chrome="app"
        eyebrow="Web 16 - Company Admin"
        title="Company admin"
        subtitle="Carregando politica local, identidade e configuracao operacional..."
      >
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  return (
    <Screen
      chrome="app"
      eyebrow="Web 16 - Company Admin"
      title="Admin center"
      subtitle="Painel administrativo local para identidade, providers e politicas de entrega do slice web."
      scroll={false}
      footer={
        <View style={{ gap: 10 }}>
          <Button title="Abrir configuracoes" onPress={() => nav.navigate("Settings")} />
          <Button title="Revisar project setup" variant="secondary" onPress={() => nav.navigate("ProjectSetup")} />
          <Button title="Ir para suporte" variant="secondary" onPress={() => nav.navigate("Support")} />
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
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.kicker}>ADMIN ERROR</Text>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        <View style={styles.tabRow}>
          {[
            ["overview", "Visao geral"],
            ["users", "Usuarios"],
            ["approvals", "Aprovacoes"],
            ["policies", "Politicas"],
          ].map(([value, label]) => (
            <Pressable
              key={value}
              onPress={() => setTab(value as AdminTab)}
              style={[styles.tab, tab === value && styles.tabActive]}
            >
              <Text style={[styles.tabText, tab === value && styles.tabTextActive]}>{label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.metrics}>
          <MetricCard label="Usuario ativo" value={session.appUser?.active ? "yes" : "no"} />
          <MetricCard
            label="Run all backlog"
            value={session.appUser?.permissions?.canRunAllBacklog ? "allowed" : "restricted"}
            accent="primary"
          />
          <MetricCard
            label="Providers ativos"
            value={String(Number(Boolean(status?.jira_configured)) + Number(Boolean(status?.azuredevops_configured)))}
          />
          <MetricCard label="Branches de deploy" value={String(deployTargets.length)} accent="success" />
        </View>

        {tab === "overview" || tab === "policies" ? (
          <View style={styles.grid}>
            <Card style={styles.panel}>
              <Text style={styles.kicker}>IDENTITY AND ACCESS</Text>
              <AdminRow label="Display name" value={session.appUser?.displayName ?? "local operator"} />
              <AdminRow label="Email" value={session.appUser?.email ?? "not defined"} />
              <AdminRow label="Account active" value={session.appUser?.active ? "true" : "false"} />
              <AdminRow label="Default provider" value={status?.default_provider ?? session.provider ?? "none"} />
            </Card>

            <Card style={styles.panel}>
              <Text style={styles.kicker}>PROVIDER POLICY</Text>
              <AdminRow label="Jira" value={status?.jira_configured ? "configured" : "not configured"} />
              <AdminRow label="Azure DevOps" value={status?.azuredevops_configured ? "configured" : "not configured"} />
              <AdminRow label="GitHub CLI" value={status?.providers.github.configured ? "authenticated" : "not authenticated"} />
              <AdminRow label="Current sprint" value={session.currentSprint?.sprintName ?? "none"} />
            </Card>
          </View>
        ) : null}

        {tab === "users" ? (
          <Card>
            <Text style={styles.kicker}>USERS AND WORKSPACE ACCESS</Text>
            <AdminRow label="Usuario atual" value={session.appUser?.email ?? "local-operator"} />
            <AdminRow label="Repos registrados" value={String(session.projectSetup.repositories.length)} />
            <AdminRow label="Validation commands" value={String(validationCommands)} />
          </Card>
        ) : null}

        {tab === "approvals" ? (
          <Card>
            <Text style={styles.kicker}>APPROVAL FLOWS</Text>
            {approvals.map((approval) => (
              <AdminRow key={approval.label} label={approval.label} value={approval.value} />
            ))}
          </Card>
        ) : null}

        <Card>
          <Text style={styles.kicker}>DELIVERY POLICY</Text>
          <AdminRow label="Project mode" value={session.projectSetup.mode} />
          <AdminRow label="Repositories" value={String(session.projectSetup.repositories.length)} />
          <AdminRow label="Validation commands" value={String(validationCommands)} />
          <AdminRow label="Deploy targets" value={deployTargets.join(", ") || "dev"} />
        </Card>

        <Card>
          <Text style={styles.kicker}>LOCAL ADMIN NOTES</Text>
          <Text style={styles.bodyText}>
            Este painel cobre a administracao operacional local que ja existe hoje.
            Cadastro real de empresa, funcionarios, licencas e SSO corporativo continuam fora deste slice sem cobranca.
          </Text>
        </Card>
      </ScrollView>
    </Screen>
  );
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  accent?: "default" | "primary" | "success";
}> = ({ label, value, accent = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        accent === "primary" && { color: theme.primary },
        accent === "success" && { color: theme.success },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const AdminRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
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
