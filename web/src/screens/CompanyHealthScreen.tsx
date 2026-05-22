import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type {
  AgentDashboardResponse,
  AuthStatus,
  Health,
  TupleDashboardResponse,
  ValidationDashboardResponse,
} from "../api/types";
import { Card } from "../components/Card";
import { Icon, type IconName } from "../components/Icon";
import { SelectInput } from "../components/Input";
import { Screen } from "../components/Screen";
import { useSession } from "../store/session";
import { theme } from "../theme";

export const CompanyHealthScreen: React.FC = () => {
  const { api } = useSession();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [tuples, setTuples] = useState<TupleDashboardResponse | null>(null);
  const [agents, setAgents] = useState<AgentDashboardResponse | null>(null);
  const [validations, setValidations] =
    useState<ValidationDashboardResponse | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [h, a, t, ag, v] = await Promise.all([
          api.health().catch(() => null),
          api.authStatus().catch(() => null),
          api.getTupleDashboard().catch(() => null),
          api.getAgentDashboard().catch(() => null),
          api.getValidationDashboard().catch(() => null),
        ]);
        setHealth(h);
        setAuth(a);
        setTuples(t);
        setAgents(ag);
        setValidations(v);
      } catch (e) {
        setError(getApiErrorMessage(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [api]);

  const adoption = 72;
  const activeUsers = 86;
  const totalLicensed = 120;
  const runsDone = tuples?.total_runs ?? 1248;
  const successRate = tuples
    ? Math.round(
        ((tuples.total_runs - tuples.failed_runs) /
          Math.max(1, tuples.total_runs)) *
          100,
      )
    : 92;

  return (
    <Screen
      chrome="manager"
      title="Saúde da empresa"
      subtitle="Visão consolidada da adoção, integrações e eficiência da sua organização."
      actions={
        <View style={styles.headerActions}>
          <View style={styles.refreshTag}>
            <Icon name="refresh" size={13} color={theme.textMuted} />
            <Text style={styles.refreshText}>Atualizado há 5 min</Text>
          </View>
          <SelectInput value="Últimos 30 dias" onPress={() => {}} />
        </View>
      }
    >
      <View style={styles.kpiGrid}>
        <KPICard
          label="Adoção ativa"
          value={`${adoption}%`}
          hint="+8 p.p. vs. período anterior"
          icon="trending"
          sparkline
        />
        <KPICard
          label="Usuários ativos"
          value={String(activeUsers)}
          hint={`de ${totalLicensed} licenciados`}
          icon="users"
        />
        <KPICard
          label="Execuções concluídas"
          value={runsDone.toLocaleString("pt-BR")}
          hint="+10% vs. período anterior"
          icon="play"
          sparkline
        />
        <KPICard
          label="Taxa de sucesso"
          value={`${successRate}%`}
          hint="+4 p.p. vs. período anterior"
          icon="check"
        />
      </View>

      <View style={styles.middleGrid}>
        <Card padding={22} style={styles.integrationsCard}>
          <Text style={styles.cardTitle}>Saúde das integrações</Text>
          <View style={styles.integrationList}>
            <IntegrationRow
              icon="jira"
              iconColor="#2684ff"
              name="Jira"
              health={
                auth?.providers.jira.configured ? "Saudável" : "Pendente"
              }
              pct={100}
            />
            <IntegrationRow
              icon="azure"
              iconColor="#0078d4"
              name="Azure DevOps"
              health={
                auth?.providers.azuredevops.configured
                  ? "Saudável"
                  : "Pendente"
              }
              pct={99}
            />
            <IntegrationRow
              icon="github"
              iconColor="#0f172a"
              name="GitHub"
              health={
                auth?.providers.github.configured ? "Saudável" : "Pendente"
              }
              pct={98}
            />
            <IntegrationRow
              icon="microsoft"
              iconColor="#0078d4"
              name="SSO (Microsoft)"
              health="Saudável"
              pct={100}
            />
          </View>
          <Text style={styles.cardLink}>Ver todas as integrações</Text>
        </Card>

        <Card padding={22} style={styles.usageCard}>
          <Text style={styles.cardTitle}>Uso de recursos (últimos 30 dias)</Text>
          <View style={styles.usageRow}>
            <Text style={styles.usageLabel}>Tokens consumidos</Text>
          </View>
          <View style={styles.usageRow}>
            <Text style={styles.usageBig}>24,8M</Text>
            <Text style={styles.usageTrend}>+22%</Text>
          </View>
          <MiniSparkline values={[40, 50, 35, 60, 75, 55, 85, 70, 95]} />

          <View style={[styles.usageRow, { marginTop: 14 }]}>
            <Text style={styles.usageLabel}>Horas de execução</Text>
          </View>
          <View style={styles.usageRow}>
            <Text style={styles.usageBig}>432 h</Text>
            <Text style={styles.usageTrend}>+16%</Text>
          </View>
          <MiniSparkline values={[20, 30, 45, 40, 60, 70, 65, 85, 90]} />
        </Card>

        <Card padding={22} style={styles.distributionCard}>
          <Text style={styles.cardTitle}>Distribuição de execuções por projeto</Text>
          <View style={styles.donutRow}>
            <Donut total={runsDone.toLocaleString("pt-BR")} />
            <View style={styles.donutLegend}>
              <LegendRow color={theme.primary} label="Plataforma" pct="38%" />
              <LegendRow color={theme.primarySoft} label="Pagamentos" pct="22%" />
              <LegendRow color={theme.accent} label="Web App" pct="18%" />
              <LegendRow color={theme.warning} label="Mobile" pct="12%" />
              <LegendRow color={theme.textMuted} label="Infraestrutura" pct="10%" />
            </View>
          </View>
        </Card>
      </View>

      <Card padding={22}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle}>Alertas recentes</Text>
          <Text style={styles.cardLink}>Ver todos os alertas</Text>
        </View>
        <View style={styles.alertList}>
          <AlertRow
            title="Falha na sincronização do Jira"
            project="Plataforma"
            time="Há 12 min"
            severity="warning"
          />
          <AlertRow
            title="Aumento de falhas de execução"
            project="Infraestrutura"
            time="Há 1 h"
            severity="warning"
          />
          <AlertRow
            title="Alta taxa de bloqueios"
            project="Web App"
            time="Há 1 h"
            severity="info"
          />
        </View>
      </Card>

      {error ? (
        <Card padding={14} variant="muted">
          <Text style={{ color: theme.danger, fontSize: 12 }}>{error}</Text>
        </Card>
      ) : null}
      {!health && loading ? (
        <Text style={{ color: theme.textMuted, fontSize: 12 }}>
          Carregando dados…
        </Text>
      ) : null}
    </Screen>
  );
};

const KPICard: React.FC<{
  label: string;
  value: string;
  hint: string;
  icon: IconName;
  sparkline?: boolean;
}> = ({ label, value, hint, icon, sparkline }) => (
  <Card padding={20} style={styles.kpiCard}>
    <View style={styles.kpiHead}>
      <Text style={styles.kpiLabel}>{label}</Text>
      <View style={styles.kpiIcon}>
        <Icon name={icon} size={16} color={theme.textMuted} />
      </View>
    </View>
    <Text style={styles.kpiValue}>{value}</Text>
    {sparkline ? <MiniSparkline values={[20, 40, 30, 55, 70, 60, 85]} /> : null}
    <Text style={[styles.kpiHint, { color: theme.success }]}>{hint}</Text>
  </Card>
);

const MiniSparkline: React.FC<{ values: number[] }> = ({ values }) => {
  const max = Math.max(...values, 1);
  return (
    <View style={styles.sparkRow}>
      {values.map((v, idx) => (
        <View
          key={idx}
          style={[
            styles.sparkBar,
            {
              height: `${(v / max) * 100}%`,
              backgroundColor: theme.primary,
            },
          ]}
        />
      ))}
    </View>
  );
};

const IntegrationRow: React.FC<{
  icon: IconName;
  iconColor: string;
  name: string;
  health: string;
  pct: number;
}> = ({ icon, iconColor, name, health, pct }) => (
  <View style={styles.integrationRow}>
    <Icon name={icon} size={20} color={iconColor} />
    <Text style={styles.integrationName}>{name}</Text>
    <View style={styles.integrationStatus}>
      <View
        style={[styles.statusDot, { backgroundColor: theme.success }]}
      />
      <Text style={[styles.statusText, { color: theme.success }]}>{health}</Text>
    </View>
    <View style={styles.healthBar}>
      <View style={[styles.healthBarFill, { width: `${pct}%` }]} />
    </View>
    <Text style={styles.healthPct}>{pct}%</Text>
  </View>
);

const LegendRow: React.FC<{
  color: string;
  label: string;
  pct: string;
}> = ({ color, label, pct }) => (
  <View style={styles.legendRow}>
    <View style={[styles.legendDot, { backgroundColor: color }]} />
    <Text style={styles.legendLabel}>{label}</Text>
    <Text style={styles.legendPct}>{pct}</Text>
  </View>
);

const Donut: React.FC<{ total: string }> = ({ total }) => (
  <View style={styles.donut}>
    <View style={styles.donutInner}>
      <Text style={styles.donutValue}>{total}</Text>
      <Text style={styles.donutLabel}>Total</Text>
    </View>
  </View>
);

const AlertRow: React.FC<{
  title: string;
  project: string;
  time: string;
  severity: "warning" | "info" | "danger";
}> = ({ title, project, time, severity }) => {
  const tone =
    severity === "warning"
      ? theme.warning
      : severity === "danger"
        ? theme.danger
        : theme.info;
  const toneSoft =
    severity === "warning"
      ? theme.warningSoft
      : severity === "danger"
        ? theme.dangerSoft
        : theme.infoSoft;
  return (
    <View style={styles.alertRow}>
      <Icon name="alert" size={16} color={tone} />
      <View style={{ flex: 1 }}>
        <Text style={styles.alertTitle}>{title}</Text>
        <Text style={styles.alertMeta}>
          Projeto: {project} · {time}
        </Text>
      </View>
      <View style={[styles.severityChip, { backgroundColor: toneSoft }]}>
        <Text style={[styles.severityChipText, { color: tone }]}>
          {severity === "warning"
            ? "Atenção"
            : severity === "danger"
              ? "Crítico"
              : "Informativo"}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  refreshTag: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  refreshText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  kpiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  kpiCard: {
    flex: 1,
    minWidth: 220,
    gap: 8,
  },
  kpiHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  kpiLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  kpiIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: theme.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  kpiValue: {
    color: theme.text,
    fontSize: 28,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  kpiHint: {
    fontSize: 11,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  sparkRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    height: 28,
    gap: 3,
    marginTop: 6,
  },
  sparkBar: {
    flex: 1,
    borderRadius: 2,
    opacity: 0.6,
    minHeight: 4,
  },
  middleGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
    alignItems: "flex-start",
  },
  integrationsCard: {
    flex: 1,
    minWidth: 280,
  },
  usageCard: {
    flex: 1,
    minWidth: 280,
  },
  distributionCard: {
    flex: 1,
    minWidth: 320,
  },
  cardTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardLink: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
    marginTop: 10,
  },
  integrationList: {
    gap: 14,
    marginTop: 14,
  },
  integrationRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  integrationName: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
    width: 100,
  },
  integrationStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  healthBar: {
    flex: 1,
    height: 5,
    backgroundColor: theme.surfaceMuted,
    borderRadius: 999,
    overflow: "hidden",
  },
  healthBarFill: {
    height: "100%",
    backgroundColor: theme.success,
    borderRadius: 999,
  },
  healthPct: {
    color: theme.text,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    width: 36,
    textAlign: "right",
  },
  usageRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 10,
    marginTop: 8,
  },
  usageLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  usageBig: {
    color: theme.text,
    fontSize: 22,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  usageTrend: {
    color: theme.success,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  donutRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 18,
    marginTop: 14,
  },
  donut: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 16,
    borderColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  donutInner: {
    alignItems: "center",
  },
  donutValue: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  donutLabel: {
    color: theme.textMuted,
    fontSize: 10,
    fontFamily: theme.fontSans,
  },
  donutLegend: {
    flex: 1,
    gap: 10,
  },
  legendRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendLabel: {
    flex: 1,
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  legendPct: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  alertList: {
    gap: 12,
  },
  alertRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surfaceAlt,
  },
  alertTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  alertMeta: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
    marginTop: 3,
  },
  severityChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  severityChipText: {
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
});
