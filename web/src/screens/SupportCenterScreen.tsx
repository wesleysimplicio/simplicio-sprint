import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { ControlPlaneRunSummary } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
import { Input, SelectInput } from "../components/Input";
import { Screen } from "../components/Screen";
import {
  loadSupportTickets,
  saveSupportTickets,
  type SupportTicket,
  type SupportTicketCategory,
  type SupportTicketStatus,
} from "../supportCenterStore";
import { useSession } from "../store/session";
import { theme } from "../theme";

const CATEGORIES: Array<{ key: SupportTicketCategory; label: string }> = [
  { key: "bug", label: "Bug" },
  { key: "integration", label: "Integração" },
  { key: "workflow", label: "Workflow" },
  { key: "feature", label: "Feature" },
  { key: "question", label: "Pergunta" },
  { key: "billing", label: "Billing" },
];

type Tab = "tickets" | "knowledge" | "backlog";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "tickets", label: "Chamados" },
  { key: "knowledge", label: "Base de conhecimento" },
  { key: "backlog", label: "Backlog de promoções" },
];

const PLACEHOLDER_TICKETS: SupportTicket[] = [
  {
    id: "4821",
    category: "integration",
    status: "new",
    title: "Falha ao importar sprint do Jira",
    description:
      "Ao tentar importar o sprint Sprint 24, ocorre erro 400 ao buscar issues.",
    linkedRunId: null,
    createdBy: "joao.operador",
    createdAt: new Date(Date.now() - 15 * 60_000).toISOString(),
    updatedAt: new Date().toISOString(),
    diagnostics: {
      provider: "jira",
      sprintId: "24",
      sprintName: "Sprint 24",
      repoCount: 3,
      runCount: 0,
    },
  },
  {
    id: "4815",
    category: "bug",
    status: "triaged",
    title: "Execução travada no passo 7",
    description: "Run não avança do passo 7 (Fix loop).",
    linkedRunId: "run-001",
    createdBy: "marina.costa",
    createdAt: new Date(Date.now() - 42 * 60_000).toISOString(),
    updatedAt: new Date().toISOString(),
    diagnostics: {
      provider: "azuredevops",
      sprintId: null,
      sprintName: "Pagamentos",
      repoCount: 1,
      runCount: 1,
    },
  },
  {
    id: "4807",
    category: "integration",
    status: "new",
    title: "Integração GitHub indisponível",
    description: "GitHub MCP retornando 503.",
    linkedRunId: null,
    createdBy: "rafael.nogueira",
    createdAt: new Date(Date.now() - 3600_000).toISOString(),
    updatedAt: new Date().toISOString(),
    diagnostics: {
      provider: "github",
      sprintId: null,
      sprintName: "Infraestrutura",
      repoCount: 2,
      runCount: 0,
    },
  },
  {
    id: "4799",
    category: "question",
    status: "resolved",
    title: "Erro de autenticação SSO",
    description: "Resolvido após renovação do certificado.",
    linkedRunId: null,
    createdBy: "thiago.martins",
    createdAt: new Date(Date.now() - 2 * 3600_000).toISOString(),
    updatedAt: new Date().toISOString(),
    diagnostics: {
      provider: null,
      sprintId: null,
      sprintName: "Todos",
      repoCount: 0,
      runCount: 0,
    },
  },
  {
    id: "4791",
    category: "feature",
    status: "new",
    title: "Solicitação de novo provedor",
    description: "Solicitação para integrar Bitbucket.",
    linkedRunId: null,
    createdBy: "camila.souza",
    createdAt: new Date(Date.now() - 3 * 3600_000).toISOString(),
    updatedAt: new Date().toISOString(),
    diagnostics: {
      provider: null,
      sprintId: null,
      sprintName: "Mobile",
      repoCount: 1,
      runCount: 0,
    },
  },
];

export const SupportCenterScreen: React.FC = () => {
  const { api, session } = useSession();
  const [tab, setTab] = useState<Tab>("tickets");
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<SupportTicketStatus | "all">(
    "all",
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [improvementTitle, setImprovementTitle] = useState(
    "Melhorar robustez da importação de sprints do Jira",
  );
  const [improvementCategory, setImprovementCategory] = useState("Integração");
  const [improvementPriority, setImprovementPriority] = useState("Alta");
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);

  useEffect(() => {
    (async () => {
      const stored = await loadSupportTickets();
      const seeded = stored.length > 0 ? stored : PLACEHOLDER_TICKETS;
      setTickets(seeded);
      setSelectedId(seeded[0]?.id ?? null);
      try {
        setRuns(await api.listControlPlaneRuns());
      } catch {
        // ignore
      }
    })();
  }, [api]);

  const filtered = useMemo(() => {
    let list = tickets;
    if (statusFilter !== "all") {
      list = list.filter((t) => t.status === statusFilter);
    }
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.id.includes(q) ||
          t.diagnostics.sprintName?.toLowerCase().includes(q),
      );
    }
    return list;
  }, [tickets, search, statusFilter]);

  const selected = useMemo(
    () => tickets.find((t) => t.id === selectedId) ?? filtered[0] ?? null,
    [filtered, selectedId, tickets],
  );

  const promoteTicket = async () => {
    if (!selected) return;
    const next = tickets.map((t) =>
      t.id === selected.id
        ? {
            ...t,
            status: "backlog_candidate" as SupportTicketStatus,
            backlogReason: improvementTitle,
          }
        : t,
    );
    setTickets(next);
    await saveSupportTickets(next);
  };

  return (
    <Screen
      chrome="manager"
      title="Central de suporte"
      actions={
        <Button
          title="Novo chamado"
          iconLeft="plus"
          onPress={() => {}}
        />
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
      </Card>

      {tab === "tickets" ? (
        <View style={styles.layout}>
          <View style={styles.listCol}>
            <View style={styles.toolbar}>
              <View style={{ flex: 1, minWidth: 160 }}>
                <Input
                  value={search}
                  onChangeText={setSearch}
                  placeholder="Buscar chamados…"
                  iconLeft="search"
                />
              </View>
              <SelectInput
                value={
                  statusFilter === "all" ? "Status: Todos" : statusFilter
                }
                onPress={() =>
                  setStatusFilter(
                    statusFilter === "all" ? "new" : "all",
                  )
                }
              />
              <SelectInput
                value="Prioridade: Todas"
                onPress={() => {}}
              />
              <SelectInput value="Mais filtros" onPress={() => {}} />
            </View>

            <View style={{ gap: 10 }}>
              {filtered.map((t) => (
                <Pressable
                  key={t.id}
                  onPress={() => setSelectedId(t.id)}
                  style={[
                    styles.ticketCard,
                    selected?.id === t.id && styles.ticketCardActive,
                  ]}
                >
                  <View style={styles.ticketHead}>
                    <Text style={styles.ticketId}>#{t.id}</Text>
                    <Text style={styles.ticketTime}>
                      {timeAgo(t.createdAt)}
                    </Text>
                  </View>
                  <Text style={styles.ticketTitle} numberOfLines={1}>
                    {t.title}
                  </Text>
                  <View style={styles.ticketBottom}>
                    <Text style={styles.ticketProject}>
                      {t.diagnostics.sprintName ?? "—"}
                    </Text>
                    <StatusBadge status={t.status} />
                    <PriorityBadge category={t.category} />
                  </View>
                </Pressable>
              ))}
            </View>

            <View style={styles.paginator}>
              <Text style={styles.paginatorText}>
                Mostrando 1 a {filtered.length} de {tickets.length} chamados
              </Text>
              <View style={styles.pageDots}>
                <View style={styles.pageBtn}>
                  <Icon name="chevron-left" size={14} color={theme.textMuted} />
                </View>
                <View style={[styles.pageBtn, styles.pageBtnActive]}>
                  <Text style={styles.pageBtnTextActive}>1</Text>
                </View>
                <View style={styles.pageBtn}>
                  <Text style={styles.pageBtnText}>2</Text>
                </View>
                <View style={styles.pageBtn}>
                  <Text style={styles.pageBtnText}>3</Text>
                </View>
                <View style={styles.pageBtn}>
                  <Text style={styles.pageBtnText}>4</Text>
                </View>
                <View style={styles.pageBtn}>
                  <Text style={styles.pageBtnText}>5</Text>
                </View>
                <View style={styles.pageBtn}>
                  <Icon
                    name="chevron-right"
                    size={14}
                    color={theme.textMuted}
                  />
                </View>
              </View>
            </View>
          </View>

          {selected ? (
            <View style={styles.detailCol}>
              <Card padding={22}>
                <View style={styles.detailHeader}>
                  <View style={{ flex: 1 }}>
                    <View style={styles.detailHeadRow}>
                      <Text style={styles.detailId}>#{selected.id}</Text>
                      <Text style={styles.detailTitle}>{selected.title}</Text>
                      <StatusBadge status={selected.status} />
                      <PriorityBadge category={selected.category} />
                    </View>
                    <Text style={styles.detailMeta}>
                      {selected.diagnostics.sprintName ?? "—"} · Criado por{" "}
                      {selected.createdBy} · {timeAgo(selected.createdAt)}
                    </Text>
                  </View>
                </View>

                <View style={styles.detailTabs}>
                  <Text style={[styles.detailTab, styles.detailTabActive]}>
                    Detalhes
                  </Text>
                  <Text style={styles.detailTab}>Atividade</Text>
                  <Text style={styles.detailTab}>Anexos</Text>
                  <Text style={styles.detailTab}>Relacionados</Text>
                </View>

                <View style={styles.detailBody}>
                  <Text style={styles.detailSection}>Descrição</Text>
                  <Text style={styles.detailText}>{selected.description}</Text>
                  {selected.diagnostics.sprintName ? (
                    <>
                      <Text style={[styles.detailSection, { marginTop: 18 }]}>
                        Ambiente
                      </Text>
                      <Text style={styles.detailText}>
                        {selected.diagnostics.provider ?? "—"} · Sprint{" "}
                        {selected.diagnostics.sprintName} · Projeto{" "}
                        {selected.diagnostics.sprintName}
                      </Text>
                    </>
                  ) : null}
                  <Text style={[styles.detailSection, { marginTop: 18 }]}>
                    Impacto
                  </Text>
                  <Text style={styles.detailText}>
                    Bloqueando importação de sprints e execução de tarefas.
                  </Text>

                  <Text style={[styles.detailSection, { marginTop: 18 }]}>
                    Atribuído para
                  </Text>
                  <View style={styles.assigneeRow}>
                    <View style={styles.assigneeAvatar}>
                      <Text style={styles.assigneeAvatarText}>SN</Text>
                    </View>
                    <Text style={styles.assigneeName}>Suporte Nível 2</Text>
                  </View>
                </View>
              </Card>

              <Card padding={20} style={styles.promoteCard}>
                <Text style={styles.promoteTitle}>Promoção para backlog</Text>
                <Text style={styles.promoteSub}>
                  Transforme este caso em uma melhoria do produto.
                </Text>

                <View style={{ height: 12 }} />
                <Input
                  label="Título da melhoria"
                  value={improvementTitle}
                  onChangeText={setImprovementTitle}
                />
                <View style={{ height: 12 }} />
                <Text style={styles.fieldLabel}>Categoria</Text>
                <SelectInput
                  value={improvementCategory}
                  onPress={() => setImprovementCategory("Integração")}
                />
                <View style={{ height: 12 }} />
                <Text style={styles.fieldLabel}>Prioridade sugerida</Text>
                <SelectInput
                  value={improvementPriority}
                  onPress={() => setImprovementPriority("Alta")}
                />

                <View style={{ height: 16 }} />
                <Button
                  title="Promover para backlog"
                  fullWidth
                  onPress={() => void promoteTicket()}
                />
              </Card>
            </View>
          ) : null}
        </View>
      ) : null}

      {tab === "knowledge" ? (
        <Card padding={22}>
          <Text style={styles.placeholderTitle}>Base de conhecimento</Text>
          <Text style={styles.placeholderText}>
            Artigos, runbooks e respostas comuns para o time de suporte.
          </Text>
        </Card>
      ) : null}

      {tab === "backlog" ? (
        <Card padding={22}>
          <Text style={styles.placeholderTitle}>Backlog de promoções</Text>
          <Text style={styles.placeholderText}>
            Chamados promovidos a melhorias de produto, agrupados por categoria.
          </Text>
        </Card>
      ) : null}
    </Screen>
  );
};

const StatusBadge: React.FC<{ status: SupportTicketStatus }> = ({ status }) => {
  const map: Record<
    SupportTicketStatus,
    { label: string; bg: string; fg: string }
  > = {
    new: { label: "Aberto", bg: theme.successSoft, fg: theme.success },
    triaged: { label: "Em análise", bg: theme.warningSoft, fg: theme.warning },
    backlog_candidate: {
      label: "Promovido",
      bg: theme.infoSoft,
      fg: theme.info,
    },
    resolved: { label: "Resolvido", bg: theme.surfaceMuted, fg: theme.textMuted },
  };
  const cfg = map[status];
  return (
    <View style={[styles.statusBadge, { backgroundColor: cfg.bg }]}>
      <Text style={[styles.statusBadgeText, { color: cfg.fg }]}>
        {cfg.label}
      </Text>
    </View>
  );
};

const PriorityBadge: React.FC<{ category: SupportTicketCategory }> = ({
  category,
}) => {
  const tone =
    category === "bug" || category === "integration"
      ? { bg: theme.dangerSoft, fg: theme.danger, label: "Alta" }
      : category === "billing" || category === "workflow"
        ? { bg: theme.warningSoft, fg: theme.warning, label: "Média" }
        : { bg: theme.successSoft, fg: theme.success, label: "Baixa" };
  return (
    <View style={[styles.priorityBadge, { backgroundColor: tone.bg }]}>
      <Text style={[styles.statusBadgeText, { color: tone.fg }]}>
        {tone.label}
      </Text>
    </View>
  );
};

const timeAgo = (iso: string): string => {
  const ms = Date.now() - Date.parse(iso);
  const min = Math.floor(ms / 60000);
  if (min < 60) return `Há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `Há ${h} h`;
  const d = Math.floor(h / 24);
  return `Há ${d} d`;
};

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
  layout: {
    flexDirection: "row",
    gap: 16,
    flexWrap: "wrap",
    alignItems: "flex-start",
  },
  listCol: {
    flex: 1,
    minWidth: 480,
    gap: 12,
  },
  detailCol: {
    width: 460,
    minWidth: 380,
    gap: 16,
  },
  toolbar: {
    flexDirection: "row",
    gap: 10,
    flexWrap: "wrap",
    alignItems: "center",
  },
  ticketCard: {
    backgroundColor: theme.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: theme.border,
    padding: 14,
    gap: 8,
  },
  ticketCardActive: {
    borderColor: theme.primary,
    backgroundColor: theme.primaryFaint,
  },
  ticketHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  ticketId: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontMono,
  },
  ticketTime: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  ticketTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  ticketBottom: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  ticketProject: {
    flex: 1,
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
  },
  statusBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  priorityBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
  },
  paginator: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 8,
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
  detailHeader: {
    marginBottom: 12,
  },
  detailHeadRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  detailId: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "800",
    fontFamily: theme.fontMono,
  },
  detailTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    flexShrink: 1,
  },
  detailMeta: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 6,
  },
  detailTabs: {
    flexDirection: "row",
    gap: 18,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    marginBottom: 12,
  },
  detailTab: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
    paddingBottom: 4,
  },
  detailTabActive: {
    color: theme.primary,
    borderBottomWidth: 2,
    borderBottomColor: theme.primary,
  },
  detailBody: {
    gap: 4,
  },
  detailSection: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  detailText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    lineHeight: 19,
    marginTop: 4,
  },
  assigneeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 6,
  },
  assigneeAvatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: theme.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  assigneeAvatarText: {
    color: theme.textMuted,
    fontSize: 10,
    fontWeight: "800",
  },
  assigneeName: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  promoteCard: {
    backgroundColor: theme.surface,
  },
  promoteTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  promoteSub: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  fieldLabel: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
    marginBottom: 6,
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
