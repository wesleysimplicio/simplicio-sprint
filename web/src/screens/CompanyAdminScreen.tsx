import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { AuthStatus } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon, type IconName } from "../components/Icon";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "CompanyAdmin">;
type Tab =
  | "overview"
  | "users"
  | "approvals"
  | "policies"
  | "sso"
  | "security"
  | "audit"
  | "licensing";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "overview", label: "Visão geral" },
  { key: "users", label: "Usuários" },
  { key: "approvals", label: "Aprovações" },
  { key: "policies", label: "Políticas" },
  { key: "sso", label: "SSO" },
  { key: "security", label: "Segurança" },
  { key: "audit", label: "Auditoria" },
  { key: "licensing", label: "Licenciamento" },
];

type PendingApproval = {
  id: string;
  type: string;
  requester: string;
  details: string;
  reason: string;
  when: string;
};

const PENDING: PendingApproval[] = [
  {
    id: "ap-1",
    type: "Novo provedor",
    requester: "Lucas Almeida",
    details: "Conectar Bitbucket Cloud",
    reason: "Integração com repositórios",
    when: "Hoje, 09:12",
  },
  {
    id: "ap-2",
    type: "Modelo de IA",
    requester: "Camila Souza",
    details: "Habilitar Claude 3.5 Opus",
    reason: "Melhor qualidade de output",
    when: "Hoje, 08:45",
  },
  {
    id: "ap-3",
    type: "Aumento de cota",
    requester: "Rafael Nogueira",
    details: "+20% tokens mensais",
    reason: "Projeto com maior volume",
    when: "Ontem, 17:30",
  },
  {
    id: "ap-4",
    type: "Acesso de usuário",
    requester: "Beatriz Lima",
    details: "Acesso admin – Thiago Martins",
    reason: "Permissão para suporte",
    when: "Ontem, 16:05",
  },
];

export const CompanyAdminScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api } = useSession();
  const [tab, setTab] = useState<Tab>("approvals");
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [approvals, setApprovals] = useState<PendingApproval[]>(PENDING);

  useEffect(() => {
    (async () => {
      try {
        setStatus(await api.authStatus());
      } catch {
        // ignore
      }
    })();
  }, [api]);

  const approve = (id: string, action: "approve" | "deny") => {
    setApprovals((current) => current.filter((a) => a.id !== id));
  };

  return (
    <Screen chrome="manager" title="Administração da empresa">
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

      {tab === "approvals" ? (
        <View style={styles.layout}>
          <Card padding={22} style={{ flex: 1, minWidth: 600 }}>
            <Text style={styles.sectionTitle}>Aprovações pendentes</Text>

            <View style={styles.approvalsHead}>
              <Text style={[styles.approvalsCol, { flex: 1 }]}>Tipo</Text>
              <Text style={[styles.approvalsCol, { flex: 1 }]}>
                Solicitante
              </Text>
              <Text style={[styles.approvalsCol, { flex: 2 }]}>Detalhes</Text>
              <Text style={[styles.approvalsCol, { flex: 2 }]}>Motivo</Text>
              <Text style={[styles.approvalsCol, { flex: 1 }]}>Data</Text>
              <Text style={[styles.approvalsCol, { width: 80 }]}>Ações</Text>
            </View>

            {approvals.map((a) => (
              <View key={a.id} style={styles.approvalRow}>
                <Text style={[styles.approvalCell, { flex: 1 }]}>
                  {a.type}
                </Text>
                <Text style={[styles.approvalCell, { flex: 1 }]}>
                  {a.requester}
                </Text>
                <Text style={[styles.approvalCell, { flex: 2 }]}>
                  {a.details}
                </Text>
                <Text style={[styles.approvalCell, { flex: 2 }]}>
                  {a.reason}
                </Text>
                <Text style={[styles.approvalCell, { flex: 1 }]}>
                  {a.when}
                </Text>
                <View style={[styles.approvalActions, { width: 80 }]}>
                  <Pressable
                    onPress={() => approve(a.id, "approve")}
                    style={[styles.actionBtn, styles.actionApprove]}
                  >
                    <Icon name="check" size={13} color={theme.success} />
                  </Pressable>
                  <Pressable
                    onPress={() => approve(a.id, "deny")}
                    style={[styles.actionBtn, styles.actionDeny]}
                  >
                    <Icon name="x" size={13} color={theme.danger} />
                  </Pressable>
                </View>
              </View>
            ))}

            {approvals.length === 0 ? (
              <View style={styles.empty}>
                <Text style={styles.emptyText}>
                  Nenhuma aprovação pendente.
                </Text>
              </View>
            ) : null}
          </Card>

          <Card padding={22} style={styles.policiesCard}>
            <Text style={styles.sectionTitle}>Políticas ativas</Text>
            <View style={styles.policiesList}>
              <PolicyRow
                title="Uso de modelos"
                desc="Restringir modelos não aprovados"
                active
              />
              <PolicyRow
                title="Limite de tokens"
                desc="Quota mensal por projeto"
                active
              />
              <PolicyRow
                title="Retenção de dados"
                desc="Logs e artefatos por 90 dias"
                active
              />
              <PolicyRow
                title="Execução fora de horário"
                desc="Permitir execução automática"
                active
              />
            </View>
            <View style={{ height: 12 }} />
            <Text style={styles.cardLink}>Gerenciar políticas</Text>
          </Card>
        </View>
      ) : null}

      {tab === "approvals" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>SSO e segurança</Text>
          <View style={styles.ssoGrid}>
            <SSOCard
              icon="microsoft"
              iconColor={theme.primary}
              title="SSO (Microsoft Entra ID)"
              status="Ativo"
              meta="Última sincronização: há 5 min"
            />
            <SSOCard
              icon="lock"
              iconColor={theme.text}
              title="MFA obrigatório"
              status="Ativo"
              meta="Todos os usuários"
            />
            <SSOCard
              icon="users"
              iconColor={theme.text}
              title="Sessões ativas"
              status="128 sessões"
              meta=""
              actionLabel="Ver sessões"
            />
            <SSOCard
              icon="doc"
              iconColor={theme.text}
              title="Auditoria"
              status="Última: há 2 min"
              meta=""
              actionLabel="Ver auditoria"
            />
          </View>
        </Card>
      ) : null}

      {tab === "overview" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Visão geral</Text>
          <Text style={styles.placeholderText}>
            Indicadores resumidos da empresa: licenças ativas, usuários,
            integrações e cota.
          </Text>
        </Card>
      ) : null}

      {tab === "users" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Usuários</Text>
          <Text style={styles.placeholderText}>
            Listagem de usuários, roles e permissões.
          </Text>
        </Card>
      ) : null}

      {tab === "policies" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Políticas</Text>
          <View style={styles.policiesList}>
            <PolicyRow
              title="Uso de modelos"
              desc="Restringir modelos não aprovados"
              active
            />
            <PolicyRow
              title="Limite de tokens"
              desc="Quota mensal por projeto"
              active
            />
            <PolicyRow
              title="Retenção de dados"
              desc="Logs e artefatos por 90 dias"
              active
            />
            <PolicyRow
              title="Execução fora de horário"
              desc="Permitir execução automática"
              active
            />
          </View>
        </Card>
      ) : null}

      {tab === "sso" || tab === "security" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>SSO e segurança</Text>
          <View style={styles.ssoGrid}>
            <SSOCard
              icon="microsoft"
              iconColor={theme.primary}
              title="SSO (Microsoft Entra ID)"
              status="Ativo"
              meta="Última sincronização: há 5 min"
            />
            <SSOCard
              icon="lock"
              iconColor={theme.text}
              title="MFA obrigatório"
              status="Ativo"
              meta="Todos os usuários"
            />
          </View>
        </Card>
      ) : null}

      {tab === "audit" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Auditoria</Text>
          <Text style={styles.placeholderText}>
            Eventos de autenticação, execução e configuração.
          </Text>
        </Card>
      ) : null}

      {tab === "licensing" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Licenciamento</Text>
          <Text style={styles.placeholderText}>
            Plano atual, quota de tokens, horas de execução e usuários.
          </Text>
        </Card>
      ) : null}
    </Screen>
  );
};

const PolicyRow: React.FC<{
  title: string;
  desc: string;
  active: boolean;
}> = ({ title, desc, active }) => (
  <View style={styles.policyRow}>
    <View style={{ flex: 1 }}>
      <Text style={styles.policyTitle}>{title}</Text>
      <Text style={styles.policyDesc}>{desc}</Text>
    </View>
    <View
      style={[
        styles.policyBadge,
        { backgroundColor: theme.successSoft },
      ]}
    >
      <Text style={[styles.policyBadgeText, { color: theme.success }]}>
        {active ? "Ativo" : "Inativo"}
      </Text>
    </View>
  </View>
);

const SSOCard: React.FC<{
  icon: IconName;
  iconColor: string;
  title: string;
  status: string;
  meta: string;
  actionLabel?: string;
}> = ({ icon, iconColor, title, status, meta, actionLabel }) => (
  <Card padding={18} style={styles.ssoCard}>
    <View style={styles.ssoIcon}>
      <Icon name={icon} size={22} color={iconColor} />
    </View>
    <Text style={styles.ssoTitle}>{title}</Text>
    <Text style={[styles.ssoStatus, { color: theme.success }]}>{status}</Text>
    {meta ? <Text style={styles.ssoMeta}>{meta}</Text> : null}
    <View style={{ flex: 1 }} />
    <Button
      title={actionLabel ?? "Configurar"}
      variant="secondary"
      size="sm"
      onPress={() => {}}
      fullWidth
    />
  </Card>
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
  sectionTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginBottom: 16,
  },
  approvalsHead: {
    flexDirection: "row",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  approvalsCol: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    textTransform: "uppercase",
    letterSpacing: 0.4,
    paddingHorizontal: 6,
  },
  approvalRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  approvalCell: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
    paddingHorizontal: 6,
  },
  approvalActions: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 6,
  },
  actionBtn: {
    width: 28,
    height: 28,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  actionApprove: {
    borderColor: theme.border,
  },
  actionDeny: {
    borderColor: theme.border,
  },
  empty: {
    paddingVertical: 24,
    alignItems: "center",
  },
  emptyText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  policiesCard: {
    width: 320,
    minWidth: 280,
  },
  policiesList: {
    gap: 14,
    marginTop: 4,
  },
  policyRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  policyTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  policyDesc: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 3,
  },
  policyBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
  },
  policyBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  cardLink: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "600",
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  ssoGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
  },
  ssoCard: {
    flex: 1,
    minWidth: 220,
    alignItems: "flex-start",
    gap: 6,
  },
  ssoIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: theme.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  ssoTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginTop: 6,
  },
  ssoStatus: {
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  ssoMeta: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  placeholderText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: 6,
  },
});
