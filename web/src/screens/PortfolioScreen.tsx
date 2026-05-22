import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type {
  ControlPlaneRunSummary,
  TupleDashboardResponse,
} from "../api/types";
import { Card } from "../components/Card";
import { Icon, type IconName } from "../components/Icon";
import { SelectInput } from "../components/Input";
import { Screen } from "../components/Screen";
import { useSession } from "../store/session";
import { theme } from "../theme";

type ProjectRow = {
  name: string;
  icon: IconName;
  iconColor: string;
  health: "Saudável" | "Atenção";
  executions: number;
  executionsDelta: string;
  successPct: number;
  successDelta: string;
  hours: number;
  hoursDelta: string;
  tokens: string;
  tokensDelta: string;
  backlog: number;
  trend: number[];
};

const PROJECTS: ProjectRow[] = [
  {
    name: "Plataforma",
    icon: "azure",
    iconColor: "#0078d4",
    health: "Saudável",
    executions: 475,
    executionsDelta: "+20%",
    successPct: 94,
    successDelta: "+5 p.p.",
    hours: 156,
    hoursDelta: "+18%",
    tokens: "8,9M",
    tokensDelta: "+25%",
    backlog: 86,
    trend: [30, 50, 35, 45, 55, 65, 50, 60, 70, 65],
  },
  {
    name: "Pagamentos",
    icon: "azure",
    iconColor: "#2684ff",
    health: "Saudável",
    executions: 276,
    executionsDelta: "+16%",
    successPct: 91,
    successDelta: "+3 p.p.",
    hours: 98,
    hoursDelta: "+12%",
    tokens: "5,4M",
    tokensDelta: "+20%",
    backlog: 42,
    trend: [40, 45, 30, 50, 45, 55, 60, 50, 65, 70],
  },
  {
    name: "Web App",
    icon: "user",
    iconColor: "#2563eb",
    health: "Atenção",
    executions: 225,
    executionsDelta: "+10%",
    successPct: 89,
    successDelta: "+2 p.p.",
    hours: 72,
    hoursDelta: "+8%",
    tokens: "3,8M",
    tokensDelta: "+15%",
    backlog: 67,
    trend: [50, 40, 45, 55, 40, 50, 45, 55, 60, 55],
  },
  {
    name: "Mobile",
    icon: "compass",
    iconColor: "#0f172a",
    health: "Saudável",
    executions: 152,
    executionsDelta: "+15%",
    successPct: 93,
    successDelta: "+6 p.p.",
    hours: 54,
    hoursDelta: "+14%",
    tokens: "2,9M",
    tokensDelta: "+18%",
    backlog: 38,
    trend: [35, 45, 50, 45, 55, 50, 60, 55, 65, 60],
  },
  {
    name: "Infraestrutura",
    icon: "settings",
    iconColor: "#0ea5e9",
    health: "Atenção",
    executions: 120,
    executionsDelta: "-5%",
    successPct: 85,
    successDelta: "-1 p.p.",
    hours: 52,
    hoursDelta: "+5%",
    tokens: "3,1M",
    tokensDelta: "+10%",
    backlog: 66,
    trend: [55, 50, 45, 50, 45, 50, 55, 50, 45, 55],
  },
];

export const PortfolioScreen: React.FC = () => {
  const { api } = useSession();
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [tuples, setTuples] = useState<TupleDashboardResponse | null>(null);
  const [viewMode, setViewMode] = useState<"summary" | "table" | "detail">(
    "summary",
  );

  useEffect(() => {
    (async () => {
      try {
        const [r, t] = await Promise.all([
          api.listControlPlaneRuns().catch(() => []),
          api.getTupleDashboard().catch(() => null),
        ]);
        setRuns(r);
        setTuples(t);
      } catch {
        // ignore
      }
    })();
  }, [api]);

  return (
    <Screen
      chrome="manager"
      title="Visão de portfólio (multi-projetos)"
      actions={
        <View style={styles.headerActions}>
          <View style={styles.refreshTag}>
            <Icon name="refresh" size={13} color={theme.textMuted} />
            <Text style={styles.refreshText}>Atualizado há 3 min</Text>
          </View>
        </View>
      }
    >
      <Card padding={0}>
        <View style={styles.toolbar}>
          <View style={{ width: 200 }}>
            <SelectInput value="Todos os projetos" onPress={() => {}} />
          </View>
          <View style={{ width: 200 }}>
            <SelectInput value="Todos os times" onPress={() => {}} />
          </View>
          <View style={{ width: 200 }}>
            <SelectInput value="Últimos 30 dias" onPress={() => {}} />
          </View>
          <View style={{ flex: 1 }} />
          <View style={styles.modeSwitch}>
            {(["summary", "table", "detail"] as const).map((mode) => (
              <Pressable
                key={mode}
                onPress={() => setViewMode(mode)}
                style={[
                  styles.modeBtn,
                  viewMode === mode && styles.modeBtnActive,
                ]}
              >
                <Icon
                  name={
                    mode === "summary"
                      ? "home"
                      : mode === "table"
                        ? "kanban"
                        : "chart"
                  }
                  size={13}
                  color={viewMode === mode ? theme.primary : theme.textMuted}
                />
                <Text
                  style={[
                    styles.modeBtnText,
                    viewMode === mode && styles.modeBtnTextActive,
                  ]}
                >
                  {mode === "summary"
                    ? "Resumo"
                    : mode === "table"
                      ? "Tabela"
                      : "Detalhado"}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      </Card>

      <View style={styles.kpiGrid}>
        <Kpi label="Projetos ativos" value="12" />
        <Kpi
          label="Execuções concluídas"
          value={(tuples?.total_runs ?? 1248).toLocaleString("pt-BR")}
          delta="+16%"
        />
        <Kpi label="Horas de execução" value="432 h" delta="+16%" />
        <Kpi label="Tokens consumidos" value="24,8M" delta="+22%" />
        <Kpi label="Taxa de sucesso média" value="92%" delta="+4 p.p." />
        <Kpi label="Backlog total" value="342 itens" />
      </View>

      <Card padding={0}>
        <Text style={styles.tableTitle}>Visão por projeto</Text>

        <View style={styles.tableHead}>
          <Text style={[styles.headCell, { flex: 1.5 }]}>Projeto</Text>
          <Text style={styles.headCell}>Saúde</Text>
          <Text style={styles.headCell}>Execuções</Text>
          <Text style={styles.headCell}>Sucesso</Text>
          <Text style={styles.headCell}>Horas</Text>
          <Text style={styles.headCell}>Tokens</Text>
          <Text style={styles.headCell}>Backlog</Text>
          <Text style={[styles.headCell, { flex: 1.2 }]}>Tendência (30 dias)</Text>
        </View>

        {PROJECTS.map((p) => (
          <View key={p.name} style={styles.tableRow}>
            <View style={[styles.cell, { flex: 1.5, flexDirection: "row", alignItems: "center", gap: 10 }]}>
              <Icon name={p.icon} size={20} color={p.iconColor} />
              <Text style={styles.projectName}>{p.name}</Text>
            </View>
            <View style={styles.cell}>
              <View style={styles.healthBadge}>
                <View
                  style={[
                    styles.healthDot,
                    {
                      backgroundColor:
                        p.health === "Saudável" ? theme.success : theme.warning,
                    },
                  ]}
                />
                <Text
                  style={[
                    styles.healthText,
                    {
                      color:
                        p.health === "Saudável" ? theme.success : theme.warning,
                    },
                  ]}
                >
                  {p.health}
                </Text>
              </View>
            </View>
            <View style={styles.cell}>
              <Text style={styles.cellValue}>{p.executions}</Text>
              <Text style={deltaStyle(p.executionsDelta)}>
                {p.executionsDelta}
              </Text>
            </View>
            <View style={styles.cell}>
              <Text style={styles.cellValue}>{p.successPct}%</Text>
              <Text style={deltaStyle(p.successDelta)}>
                {p.successDelta}
              </Text>
            </View>
            <View style={styles.cell}>
              <Text style={styles.cellValue}>{p.hours} h</Text>
              <Text style={deltaStyle(p.hoursDelta)}>
                {p.hoursDelta}
              </Text>
            </View>
            <View style={styles.cell}>
              <Text style={styles.cellValue}>{p.tokens}</Text>
              <Text style={deltaStyle(p.tokensDelta)}>
                {p.tokensDelta}
              </Text>
            </View>
            <View style={styles.cell}>
              <Text style={styles.cellValue}>{p.backlog}</Text>
            </View>
            <View style={[styles.cell, { flex: 1.2 }]}>
              <Sparkline values={p.trend} />
            </View>
          </View>
        ))}

        <Pressable style={styles.tableFooter}>
          <Text style={styles.tableFooterText}>Ver portfólio detalhado</Text>
        </Pressable>
      </Card>
    </Screen>
  );
};

const Kpi: React.FC<{
  label: string;
  value: string;
  delta?: string;
}> = ({ label, value, delta }) => (
  <Card padding={18} style={styles.kpiCard}>
    <Text style={styles.kpiLabel}>{label}</Text>
    <View style={styles.kpiValueRow}>
      <Text style={styles.kpiValue}>{value}</Text>
      {delta ? (
        <Text
          style={[
            styles.kpiDelta,
            { color: delta.startsWith("-") ? theme.danger : theme.success },
          ]}
        >
          {delta}
        </Text>
      ) : null}
    </View>
  </Card>
);

const deltaStyle = (delta: string) => [
  styles.cellDelta,
  { color: delta.startsWith("-") ? theme.danger : theme.success },
];

const Sparkline: React.FC<{ values: number[] }> = ({ values }) => {
  const max = Math.max(...values, 1);
  const min = Math.min(...values);
  return (
    <View style={styles.sparkRow}>
      {values.map((v, idx) => {
        const h = ((v - min) / Math.max(1, max - min)) * 100;
        return (
          <View
            key={idx}
            style={[
              styles.sparkBar,
              { height: `${Math.max(20, h)}%` },
            ]}
          />
        );
      })}
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
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
    padding: 18,
  },
  modeSwitch: {
    flexDirection: "row",
    gap: 4,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 8,
    padding: 3,
    backgroundColor: theme.surfaceAlt,
  },
  modeBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 6,
  },
  modeBtnActive: {
    backgroundColor: theme.surface,
  },
  modeBtnText: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  modeBtnTextActive: {
    color: theme.primary,
  },
  kpiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
  },
  kpiCard: {
    flex: 1,
    minWidth: 170,
    gap: 6,
  },
  kpiLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  kpiValueRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 6,
  },
  kpiValue: {
    color: theme.text,
    fontSize: 22,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  kpiDelta: {
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  tableTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    padding: 18,
    paddingBottom: 14,
  },
  tableHead: {
    flexDirection: "row",
    paddingHorizontal: 18,
    paddingVertical: 10,
    backgroundColor: theme.surfaceAlt,
  },
  headCell: {
    flex: 1,
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  cell: {
    flex: 1,
  },
  projectName: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  healthBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  healthDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  healthText: {
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  cellValue: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  cellDelta: {
    fontSize: 11,
    fontWeight: "700" as const,
    fontFamily: theme.fontSans,
    marginTop: 3,
  },
  sparkRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    height: 24,
    gap: 2,
  },
  sparkBar: {
    flex: 1,
    backgroundColor: theme.primary,
    borderRadius: 1,
    minHeight: 3,
  },
  tableFooter: {
    paddingVertical: 16,
    alignItems: "center",
  },
  tableFooterText: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
});
