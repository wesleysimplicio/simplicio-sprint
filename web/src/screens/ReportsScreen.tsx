import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type {
  TupleDashboardResponse,
  ValidationDashboardResponse,
  YoolDashboardResponse,
} from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon, type IconName } from "../components/Icon";
import { Input, SelectInput } from "../components/Input";
import { Screen } from "../components/Screen";
import { useSession } from "../store/session";
import { theme } from "../theme";

type ReportsTab =
  | "overview"
  | "executions"
  | "tokens"
  | "hours"
  | "models"
  | "productivity"
  | "exports";

const TABS: Array<{ key: ReportsTab; label: string }> = [
  { key: "overview", label: "Visão geral" },
  { key: "executions", label: "Execuções" },
  { key: "tokens", label: "Tokens" },
  { key: "hours", label: "Horas" },
  { key: "models", label: "Modelos" },
  { key: "productivity", label: "Produtividade" },
  { key: "exports", label: "Exportações" },
];

export const ReportsScreen: React.FC = () => {
  const { api } = useSession();
  const [tab, setTab] = useState<ReportsTab>("overview");
  const [tuples, setTuples] = useState<TupleDashboardResponse | null>(null);
  const [yools, setYools] = useState<YoolDashboardResponse | null>(null);
  const [validations, setValidations] =
    useState<ValidationDashboardResponse | null>(null);
  const [period, setPeriod] = useState("01/05/2025 – 31/05/2025");

  useEffect(() => {
    (async () => {
      try {
        const [t, y, v] = await Promise.all([
          api.getTupleDashboard().catch(() => null),
          api.getYoolDashboard().catch(() => null),
          api.getValidationDashboard().catch(() => null),
        ]);
        setTuples(t);
        setYools(y);
        setValidations(v);
      } catch {
        // ignore
      }
    })();
  }, [api]);

  const runsDone = tuples?.total_runs ?? 1248;
  const successRate = tuples
    ? Math.round(
        ((tuples.total_runs - tuples.failed_runs) /
          Math.max(1, tuples.total_runs)) *
          100,
      )
    : 92;

  return (
    <Screen chrome="manager" title="Relatórios e análises">
      <Card padding={0}>
        <View style={styles.tabBar}>
          {TABS.map((t) => (
            <Pressable
              key={t.key}
              onPress={() => setTab(t.key)}
              style={[styles.tab, tab === t.key && styles.tabActive]}
            >
              <Text
                style={[
                  styles.tabText,
                  tab === t.key && styles.tabTextActive,
                ]}
              >
                {t.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.toolbar}>
          <View style={styles.dateBox}>
            <Input
              value={period}
              onChangeText={setPeriod}
              iconLeft="calendar"
            />
          </View>
          <View style={styles.toolbarSelect}>
            <Text style={styles.toolbarLabel}>Comparar com:</Text>
            <SelectInput value="Período anterior" onPress={() => {}} />
          </View>
          <View style={{ flex: 1 }} />
          <Button
            title="Filtros"
            variant="secondary"
            iconLeft="filter"
            size="sm"
            onPress={() => {}}
          />
          <Button
            title="Exportar relatório"
            iconLeft="download"
            onPress={() => {}}
          />
        </View>
      </Card>

      <View style={styles.kpiGrid}>
        <KPICard
          label="Tokens consumidos"
          value="24,8M"
          delta="+22%"
          icon="model"
        />
        <KPICard
          label="Horas de execução"
          value="432 h"
          delta="+16%"
          icon="clock"
        />
        <KPICard
          label="Execuções concluídas"
          value={runsDone.toLocaleString("pt-BR")}
          delta="+10%"
          icon="play"
        />
        <KPICard
          label="Taxa de sucesso"
          value={`${successRate}%`}
          delta="+4 p.p."
          icon="check"
        />
      </View>

      <View style={styles.middleGrid}>
        <Card padding={22} style={styles.tokensCard}>
          <Text style={styles.cardTitle}>Tokens por dia</Text>
          <Text style={styles.cardSub}>Em milhões</Text>
          <View style={styles.barsRow}>
            {BARS_30_DAYS.map((v, idx) => (
              <View
                key={idx}
                style={[
                  styles.bar,
                  {
                    height: `${v}%`,
                    backgroundColor: theme.primary,
                  },
                ]}
              />
            ))}
          </View>
          <View style={styles.daysAxis}>
            <Text style={styles.dayLabel}>1 Mai</Text>
            <Text style={styles.dayLabel}>6 Mai</Text>
            <Text style={styles.dayLabel}>11 Mai</Text>
            <Text style={styles.dayLabel}>16 Mai</Text>
            <Text style={styles.dayLabel}>21 Mai</Text>
            <Text style={styles.dayLabel}>26 Mai</Text>
            <Text style={styles.dayLabel}>31 Mai</Text>
          </View>
        </Card>

        <Card padding={22} style={styles.executionsCard}>
          <Text style={styles.cardTitle}>Execuções por projeto</Text>
          <Text style={styles.cardSub}>
            Total {runsDone.toLocaleString("pt-BR")}
          </Text>
          <View style={{ gap: 12, marginTop: 14 }}>
            <ProjectBar label="Plataforma" value={475} pct={38} />
            <ProjectBar label="Pagamentos" value={276} pct={22} />
            <ProjectBar label="Web App" value={225} pct={18} />
            <ProjectBar label="Mobile" value={152} pct={12} />
            <ProjectBar label="Infraestrutura" value={120} pct={10} />
          </View>
        </Card>

        <Card padding={22} style={styles.modelsCard}>
          <Text style={styles.cardTitle}>
            Modelos mais utilizados (tokens)
          </Text>
          <View style={styles.donutRow}>
            <View style={styles.donut}>
              <View style={styles.donutInner}>
                <Text style={styles.donutValue}>24,8M</Text>
                <Text style={styles.donutLabel}>Total</Text>
              </View>
            </View>
            <View style={styles.donutLegend}>
              <LegendRow color={theme.primary} label="GPT-4o" pct="42%" />
              <LegendRow
                color={theme.primarySoft}
                label="Claude 3.5 Sonnet"
                pct="28%"
              />
              <LegendRow
                color={theme.accentWarm}
                label="Anthropic Claude 3"
                pct="18%"
              />
              <LegendRow
                color={theme.success}
                label="Gemini 1.5 Pro"
                pct="8%"
              />
              <LegendRow color={theme.textMuted} label="Outros" pct="4%" />
            </View>
          </View>
        </Card>
      </View>

      <Pressable style={styles.fullReportRow}>
        <Text style={styles.fullReportText}>Ver relatório completo</Text>
      </Pressable>
    </Screen>
  );
};

const BARS_30_DAYS = [
  60, 70, 90, 55, 75, 95, 50, 60, 45, 55, 40, 80, 65, 45, 35, 80, 65, 70, 50,
  60, 55, 90, 75, 95, 65, 95, 80, 50, 85, 75, 65,
];

const KPICard: React.FC<{
  label: string;
  value: string;
  delta: string;
  icon: IconName;
}> = ({ label, value, delta, icon }) => (
  <Card padding={20} style={styles.kpiCard}>
    <View style={styles.kpiHead}>
      <Text style={styles.kpiLabel}>{label}</Text>
      <Icon name={icon} size={18} color={theme.textMuted} />
    </View>
    <View style={styles.kpiBody}>
      <Text style={styles.kpiValue}>{value}</Text>
      <Text style={styles.kpiDelta}>{delta}</Text>
    </View>
  </Card>
);

const ProjectBar: React.FC<{
  label: string;
  value: number;
  pct: number;
}> = ({ label, value, pct }) => (
  <View style={styles.projRow}>
    <Text style={styles.projLabel}>{label}</Text>
    <View style={styles.projBar}>
      <View style={[styles.projFill, { width: `${pct * 2}%` }]} />
    </View>
    <Text style={styles.projValue}>
      {value} ({pct}%)
    </Text>
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

const styles = StyleSheet.create({
  tabBar: {
    flexDirection: "row",
    paddingHorizontal: 22,
    paddingTop: 14,
    gap: 6,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  tab: {
    paddingHorizontal: 6,
    paddingVertical: 12,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
    marginRight: 18,
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
  toolbar: {
    flexDirection: "row",
    gap: 12,
    flexWrap: "wrap",
    alignItems: "center",
    padding: 22,
  },
  dateBox: {
    width: 280,
    minWidth: 240,
  },
  toolbarSelect: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  toolbarLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  kpiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
  },
  kpiCard: {
    flex: 1,
    minWidth: 200,
    gap: 12,
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
  kpiBody: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 10,
  },
  kpiValue: {
    color: theme.text,
    fontSize: 26,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  kpiDelta: {
    color: theme.success,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  middleGrid: {
    flexDirection: "row",
    gap: 16,
    flexWrap: "wrap",
    alignItems: "flex-start",
  },
  cardTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  cardSub: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  tokensCard: {
    flex: 2,
    minWidth: 360,
  },
  barsRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    height: 140,
    gap: 3,
    marginTop: 12,
  },
  bar: {
    flex: 1,
    borderRadius: 2,
    minHeight: 4,
    opacity: 0.85,
  },
  daysAxis: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
  },
  dayLabel: {
    color: theme.textMuted,
    fontSize: 10,
    fontFamily: theme.fontSans,
  },
  executionsCard: {
    flex: 2,
    minWidth: 320,
  },
  projRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  projLabel: {
    width: 110,
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  projBar: {
    flex: 1,
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.surfaceMuted,
    overflow: "hidden",
  },
  projFill: {
    height: "100%",
    backgroundColor: theme.primary,
    borderRadius: 999,
  },
  projValue: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
    width: 90,
    textAlign: "right",
  },
  modelsCard: {
    flex: 2,
    minWidth: 320,
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
    borderWidth: 14,
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
    gap: 8,
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
  fullReportRow: {
    alignItems: "center",
    paddingVertical: 14,
  },
  fullReportText: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
});
