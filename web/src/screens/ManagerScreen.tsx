import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type {
  ControlPlaneRunSummary,
  SprintDetail,
} from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
import { Input, SelectInput } from "../components/Input";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Manager">;
type ManagerTab = "team" | "tasks" | "runs" | "alerts";

type EmployeeRollup = {
  email: string;
  displayName: string;
  role: string;
  project: string;
  running: number;
  done: number;
  blocked: number;
  awaitingReview: number;
  lastActivity: string;
};

const TABS: Array<{ key: ManagerTab; label: string }> = [
  { key: "team", label: "Minha equipe" },
  { key: "tasks", label: "Status das tarefas" },
  { key: "runs", label: "Execuções recentes" },
  { key: "alerts", label: "Alertas" },
];

const PLACEHOLDER_TEAM: EmployeeRollup[] = [
  {
    email: "joao.operador",
    displayName: "João Operador",
    role: "Desenvolvedor Sênior",
    project: "Plataforma",
    running: 4,
    done: 8,
    blocked: 0,
    awaitingReview: 1,
    lastActivity: "Há 5 min",
  },
  {
    email: "marina.costa",
    displayName: "Marina Costa",
    role: "Dev Backend",
    project: "Pagamentos",
    running: 3,
    done: 7,
    blocked: 1,
    awaitingReview: 2,
    lastActivity: "Há 12 min",
  },
  {
    email: "lucas.almeida",
    displayName: "Lucas Almeida",
    role: "Dev Frontend",
    project: "Web App",
    running: 2,
    done: 6,
    blocked: 0,
    awaitingReview: 1,
    lastActivity: "Há 18 min",
  },
  {
    email: "beatriz.lima",
    displayName: "Beatriz Lima",
    role: "QA Engineer",
    project: "Plataforma",
    running: 1,
    done: 5,
    blocked: 0,
    awaitingReview: 0,
    lastActivity: "Há 25 min",
  },
  {
    email: "rafael.nogueira",
    displayName: "Rafael Nogueira",
    role: "DevOps",
    project: "Infra",
    running: 2,
    done: 4,
    blocked: 1,
    awaitingReview: 1,
    lastActivity: "Há 31 min",
  },
  {
    email: "camila.souza",
    displayName: "Camila Souza",
    role: "Product Engineer",
    project: "Mobile",
    running: 1,
    done: 3,
    blocked: 0,
    awaitingReview: 2,
    lastActivity: "Há 40 min",
  },
  {
    email: "thiago.martins",
    displayName: "Thiago Martins",
    role: "Desenvolvedor",
    project: "Relatórios",
    running: 1,
    done: 3,
    blocked: 1,
    awaitingReview: 0,
    lastActivity: "Há 52 min",
  },
];

export const ManagerScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [tab, setTab] = useState<ManagerTab>("team");
  const [search, setSearch] = useState("");
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [detail, setDetail] = useState<SprintDetail | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [runList, sprintDetail] = await Promise.all([
          api.listControlPlaneRuns(),
          session.currentSprint
            ? api.getSprint(
                session.currentSprint.sprintId,
                session.currentSprint.provider,
              )
            : Promise.resolve(null),
        ]);
        setRuns(runList);
        setDetail(sprintDetail);
      } catch {
        // ignore
      }
    })();
  }, [api, session.currentSprint]);

  const team = useMemo(() => {
    if (!detail) return PLACEHOLDER_TEAM;
    const rollups = new Map<string, EmployeeRollup>();
    for (const item of detail.items) {
      const email = (item.assignee_email ?? item.assignee ?? "operator").toString();
      const existing = rollups.get(email) ?? {
        email,
        displayName: item.assignee ?? email,
        role: "Membro",
        project: session.currentSprint?.projectName ?? "Plataforma",
        running: 0,
        done: 0,
        blocked: 0,
        awaitingReview: 0,
        lastActivity: "—",
      };
      const status = item.status.toLowerCase();
      if (status.includes("block")) existing.blocked++;
      else if (status.includes("review")) existing.awaitingReview++;
      else if (status.includes("done") || status.includes("clos"))
        existing.done++;
      else existing.running++;
      rollups.set(email, existing);
    }
    const rows = Array.from(rollups.values());
    return rows.length > 0 ? rows : PLACEHOLDER_TEAM;
  }, [detail, session.currentSprint]);

  const filteredTeam = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return team;
    return team.filter(
      (e) =>
        e.displayName.toLowerCase().includes(q) ||
        e.project.toLowerCase().includes(q),
    );
  }, [search, team]);

  const totals = useMemo(
    () => ({
      members: team.length,
      running: team.reduce((acc, e) => acc + e.running, 0),
      done: team.reduce((acc, e) => acc + e.done, 0),
      blocked: team.reduce((acc, e) => acc + e.blocked, 0),
      awaitingReview: team.reduce((acc, e) => acc + e.awaitingReview, 0),
    }),
    [team],
  );

  const completion = Math.min(
    100,
    Math.round(
      (totals.done /
        Math.max(1, totals.done + totals.running + totals.blocked)) *
        100,
    ),
  );

  return (
    <Screen
      chrome="manager"
      title="Operações"
      actions={
        <View style={styles.headerActions}>
          <View style={styles.updateMeta}>
            <Icon name="refresh" size={13} color={theme.textMuted} />
            <Text style={styles.updateText}>Atualizado há 2 min</Text>
          </View>
          <Button
            title="Iniciar execução"
            iconLeft="plus"
            onPress={() => nav.navigate("Sprints")}
          />
        </View>
      }
    >
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
          <View style={{ flex: 2, minWidth: 280 }}>
            <Input
              value={search}
              onChangeText={setSearch}
              placeholder="Buscar por colaborador ou projeto…"
              iconLeft="search"
            />
          </View>
          <View style={styles.toolbarSelect}>
            <Text style={styles.toolbarSelectLabel}>Projeto:</Text>
            <SelectInput value="Todos" onPress={() => {}} />
          </View>
          <View style={styles.toolbarSelect}>
            <Text style={styles.toolbarSelectLabel}>Período:</Text>
            <SelectInput value="Últimos 7 dias" onPress={() => {}} />
          </View>
          <Button
            title="Filtros"
            variant="secondary"
            iconLeft="filter"
            size="sm"
            onPress={() => {}}
          />
          <Button
            title="Exportar"
            iconLeft="download"
            size="sm"
            onPress={() => {}}
          />
        </View>
      </Card>

      {tab === "team" ? (
        <View style={styles.teamGrid}>
          <Card padding={20} style={styles.summaryCard}>
            <Text style={styles.summaryTitle}>Resumo da equipe</Text>
            <Text style={styles.summaryBig}>{totals.members}</Text>
            <Text style={styles.summaryBigLabel}>Colaboradores</Text>

            <View style={styles.summaryStats}>
              <StatLine
                label="Em andamento"
                value={totals.running}
                tone={theme.info}
              />
              <StatLine
                label="Concluídas"
                value={totals.done}
                tone={theme.success}
              />
              <StatLine
                label="Bloqueadas"
                value={totals.blocked}
                tone={theme.danger}
              />
              <StatLine
                label="Aguardando revisão"
                value={totals.awaitingReview}
                tone={theme.warning}
              />
            </View>

            <View style={{ marginTop: 18 }}>
              <View style={styles.taxaRow}>
                <Text style={styles.taxaLabel}>Taxa de conclusão</Text>
                <Text style={styles.taxaValue}>{completion}%</Text>
              </View>
              <View style={styles.progressBar}>
                <View
                  style={[styles.progressFill, { width: `${completion}%` }]}
                />
              </View>
            </View>
          </Card>

          <Card padding={0} style={{ flex: 1, minWidth: 600 }}>
            <View style={styles.teamHeader}>
              <View style={[styles.teamCol, { flex: 2 }]}>
                <Text style={styles.teamColLabel}>Colaborador</Text>
              </View>
              <View style={styles.teamCol}>
                <Text style={styles.teamColLabel}>Projeto</Text>
              </View>
              <View style={styles.teamCol}>
                <Text
                  style={[styles.teamColLabel, { textAlign: "center" }]}
                >
                  Em andamento
                </Text>
              </View>
              <View style={styles.teamCol}>
                <Text
                  style={[styles.teamColLabel, { textAlign: "center" }]}
                >
                  Concluídas
                </Text>
              </View>
              <View style={styles.teamCol}>
                <Text
                  style={[styles.teamColLabel, { textAlign: "center" }]}
                >
                  Bloqueadas
                </Text>
              </View>
              <View style={styles.teamCol}>
                <Text
                  style={[styles.teamColLabel, { textAlign: "center" }]}
                >
                  Aguard. rev.
                </Text>
              </View>
              <View style={styles.teamCol}>
                <Text style={styles.teamColLabel}>Última atividade</Text>
              </View>
            </View>

            <ScrollView style={{ maxHeight: 540 }}>
              {filteredTeam.map((emp) => (
                <View key={emp.email} style={styles.teamRow}>
                  <View
                    style={[
                      styles.teamCol,
                      {
                        flex: 2,
                        flexDirection: "row",
                        alignItems: "center",
                        gap: 10,
                      },
                    ]}
                  >
                    <View style={styles.teamAvatar}>
                      <Text style={styles.teamAvatarText}>
                        {initials(emp.displayName)}
                      </Text>
                    </View>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text style={styles.teamName} numberOfLines={1}>
                        {emp.displayName}
                      </Text>
                      <Text style={styles.teamRole} numberOfLines={1}>
                        {emp.role}
                      </Text>
                    </View>
                  </View>
                  <View style={styles.teamCol}>
                    <Text style={styles.teamValue}>{emp.project}</Text>
                  </View>
                  <View style={styles.teamCol}>
                    <Text style={[styles.teamValue, styles.teamValueCenter]}>
                      {emp.running}
                    </Text>
                  </View>
                  <View style={styles.teamCol}>
                    <Text style={[styles.teamValue, styles.teamValueCenter]}>
                      {emp.done}
                    </Text>
                  </View>
                  <View style={styles.teamCol}>
                    <Text style={[styles.teamValue, styles.teamValueCenter]}>
                      {emp.blocked}
                    </Text>
                  </View>
                  <View style={styles.teamCol}>
                    <Text style={[styles.teamValue, styles.teamValueCenter]}>
                      {emp.awaitingReview}
                    </Text>
                  </View>
                  <View style={styles.teamCol}>
                    <Text style={[styles.teamValue, { color: theme.textMuted }]}>
                      {emp.lastActivity}
                    </Text>
                  </View>
                </View>
              ))}
            </ScrollView>

            <View style={styles.paginator}>
              <Text style={styles.paginatorText}>
                Mostrando 1 a {filteredTeam.length} de {team.length} colaboradores
              </Text>
              <View style={styles.pageDots}>
                <Pressable style={styles.pageBtn}>
                  <Icon
                    name="chevron-left"
                    size={14}
                    color={theme.textMuted}
                  />
                </Pressable>
                <View style={[styles.pageBtn, styles.pageBtnActive]}>
                  <Text style={styles.pageBtnTextActive}>1</Text>
                </View>
                <View style={styles.pageBtn}>
                  <Text style={styles.pageBtnText}>2</Text>
                </View>
                <Pressable style={styles.pageBtn}>
                  <Icon
                    name="chevron-right"
                    size={14}
                    color={theme.textMuted}
                  />
                </Pressable>
              </View>
            </View>
          </Card>
        </View>
      ) : null}

      {tab === "tasks" ? (
        <Card padding={22}>
          <Text style={styles.placeholderTitle}>Status das tarefas</Text>
          <Text style={styles.placeholderText}>
            {detail
              ? `${detail.items.length} tarefas na sprint atual.`
              : "Importe uma sprint para ver o status das tarefas."}
          </Text>
        </Card>
      ) : null}

      {tab === "runs" ? (
        <Card padding={22}>
          <Text style={styles.placeholderTitle}>Execuções recentes</Text>
          <Text style={styles.placeholderText}>
            {runs.length} execuções registradas no control plane.
          </Text>
        </Card>
      ) : null}

      {tab === "alerts" ? (
        <Card padding={22}>
          <Text style={styles.placeholderTitle}>Alertas</Text>
          <Text style={styles.placeholderText}>
            Nenhum alerta crítico no momento.
          </Text>
        </Card>
      ) : null}
    </Screen>
  );
};

const StatLine: React.FC<{
  label: string;
  value: number;
  tone: string;
}> = ({ label, value, tone }) => (
  <View style={styles.statLine}>
    <View style={[styles.statLineDot, { backgroundColor: tone }]} />
    <Text style={styles.statLineLabel}>{label}</Text>
    <Text style={styles.statLineValue}>{value}</Text>
  </View>
);

const initials = (value: string): string => {
  const parts = value.split(/[\s.]+/).filter(Boolean);
  return (
    (parts[0]?.[0] ?? "F").toUpperCase() + (parts[1]?.[0] ?? "S").toUpperCase()
  );
};

const styles = StyleSheet.create({
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  updateMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  updateText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
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
    marginRight: 22,
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
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    padding: 22,
  },
  toolbarSelect: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  toolbarSelectLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  teamGrid: {
    flexDirection: "row",
    gap: 16,
    flexWrap: "wrap",
    alignItems: "flex-start",
  },
  summaryCard: {
    width: 280,
    minWidth: 240,
  },
  summaryTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  summaryBig: {
    color: theme.text,
    fontSize: 36,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    marginTop: 18,
  },
  summaryBigLabel: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: -4,
  },
  summaryStats: {
    gap: 10,
    marginTop: 20,
  },
  statLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  statLineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statLineLabel: {
    flex: 1,
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  statLineValue: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  taxaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  taxaLabel: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  taxaValue: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  progressBar: {
    height: 6,
    borderRadius: 999,
    backgroundColor: theme.surfaceMuted,
    overflow: "hidden",
    marginTop: 8,
  },
  progressFill: {
    height: "100%",
    backgroundColor: theme.primary,
    borderRadius: 999,
  },
  teamHeader: {
    flexDirection: "row",
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  teamCol: {
    flex: 1,
    paddingHorizontal: 4,
  },
  teamColLabel: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  teamRow: {
    flexDirection: "row",
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    alignItems: "center",
  },
  teamAvatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: theme.primaryFaint,
    alignItems: "center",
    justifyContent: "center",
  },
  teamAvatarText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  teamName: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  teamRole: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  teamValue: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  teamValueCenter: {
    textAlign: "center",
  },
  paginator: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 18,
  },
  paginatorText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  pageDots: {
    flexDirection: "row",
    gap: 4,
  },
  pageBtn: {
    width: 28,
    height: 28,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
  },
  pageBtnActive: {
    backgroundColor: theme.primary,
    borderColor: theme.primary,
  },
  pageBtnText: {
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  pageBtnTextActive: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  placeholderTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  placeholderText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: 6,
  },
});
