import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { AuthStatus, VersionCheckResponse } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon, type IconName } from "../components/Icon";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Settings">;
type SettingsTab =
  | "connections"
  | "models"
  | "execution"
  | "security"
  | "notifications"
  | "preferences";

const TABS: Array<{ key: SettingsTab; label: string }> = [
  { key: "connections", label: "Conexões" },
  { key: "models", label: "Modelos" },
  { key: "execution", label: "Execução" },
  { key: "security", label: "Segurança" },
  { key: "notifications", label: "Notificações" },
  { key: "preferences", label: "Preferências" },
];

export const SettingsScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api } = useSession();
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [versionCheck, setVersionCheck] = useState<VersionCheckResponse | null>(
    null,
  );
  const [versionError, setVersionError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [tab, setTab] = useState<SettingsTab>("connections");

  useEffect(() => {
    (async () => {
      try {
        setStatus(await api.authStatus());
      } catch {
        // ignore
      }
    })();
  }, [api]);

  const checkForUpdates = async () => {
    setChecking(true);
    setVersionError(null);
    setVersionCheck(null);
    try {
      setVersionCheck(await api.checkVersion());
    } catch (e) {
      setVersionError(getApiErrorMessage(e));
    } finally {
      setChecking(false);
    }
  };

  return (
    <Screen
      title="Configurações"
      subtitle="Conexões, modelos, execução e preferências do workspace local."
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

      {tab === "connections" ? (
        <Card padding={22}>
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>Provedores conectados</Text>
            <Button
              title="Adicionar conexão"
              iconLeft="plus"
              size="sm"
              onPress={() => nav.navigate("Provider")}
            />
          </View>

          <View style={styles.providerList}>
            <ProviderRow
              icon="jira"
              iconColor="#2684ff"
              name="Jira"
              account={
                status?.providers.jira.account ?? "suaempresa.atlassian.net"
              }
              connected={status?.providers.jira.configured ?? true}
              onTest={() => nav.navigate("Auth")}
            />
            <ProviderRow
              icon="azure"
              iconColor="#0078d4"
              name="Azure DevOps"
              account={
                status?.providers.azuredevops.account ??
                "dev.azure.com/sua-organizacao"
              }
              connected={status?.providers.azuredevops.configured ?? true}
              onTest={() => nav.navigate("Auth")}
            />
            <ProviderRow
              icon="github"
              iconColor="#0f172a"
              name="GitHub"
              account={
                status?.providers.github.configured
                  ? "github.com/autenticado"
                  : "github.com/suaempresa"
              }
              connected={status?.providers.github.configured ?? true}
              onTest={() => nav.navigate("Provider")}
              isLast
            />
          </View>

          <Text style={[styles.sectionTitle, { marginTop: 28 }]}>
            Modelos de IA
          </Text>

          <View style={styles.modelHeader}>
            <View style={styles.modelHeaderCell}>
              <Text style={styles.modelHeaderText}>Nome</Text>
            </View>
            <View style={styles.modelHeaderCell}>
              <Text style={styles.modelHeaderText}>Modelo</Text>
            </View>
            <View style={styles.modelHeaderCell}>
              <Text style={styles.modelHeaderText}>Fornecedor</Text>
            </View>
            <View style={styles.modelHeaderCell}>
              <Text style={styles.modelHeaderText}>Context Window</Text>
            </View>
            <View style={styles.modelHeaderCell}>
              <Text style={styles.modelHeaderText}>Status</Text>
            </View>
            <View style={{ width: 80 }} />
          </View>

          <ModelRow
            name="Modelo padrão"
            model="GPT-4o"
            provider="OpenAI"
            context="128k"
            status="Ativo"
            statusOn
          />
          <ModelRow
            name="Modelo secundário"
            model="Claude 3.5 Sonnet"
            provider="Anthropic"
            context="200k"
            status=""
            statusOn={false}
          />
        </Card>
      ) : null}

      {tab === "models" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Modelos & fallbacks</Text>
          <View style={{ gap: 14, marginTop: 14 }}>
            <Card variant="muted" padding={16}>
              <Text style={styles.subSectionTitle}>Chat e providers</Text>
              <Text style={styles.subSectionText}>
                OpenAI · Anthropic · OpenRouter · Codex · Claude · Hermes ·
                Ollama
              </Text>
            </Card>
            <Card variant="muted" padding={16}>
              <Text style={styles.subSectionTitle}>Browser fallbacks</Text>
              <Text style={styles.subSectionText}>
                Playwright primeiro · Claude, Codex, Hermes e OpenClaw como
                fallback quando o backend não resolve sozinho.
              </Text>
            </Card>
          </View>
        </Card>
      ) : null}

      {tab === "execution" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Execução</Text>
          <Text style={styles.subSectionText}>
            Política de execução, repositórios locais ativos, autonomia e
            modo dry-run são configurados em Projetos → Configurar.
          </Text>
          <View style={{ height: 12 }} />
          <Button
            title="Abrir configuração de projeto"
            variant="secondary"
            iconRight="arrow-right"
            onPress={() => nav.navigate("ProjectSetup")}
          />
        </Card>
      ) : null}

      {tab === "security" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Segurança</Text>
          <Text style={styles.subSectionText}>
            SSO, MFA, sessões ativas e auditoria são gerenciados em
            Administração da empresa.
          </Text>
          <View style={{ height: 12 }} />
          <Button
            title="Abrir administração"
            variant="secondary"
            iconRight="arrow-right"
            onPress={() => nav.navigate("CompanyAdmin")}
          />
        </Card>
      ) : null}

      {tab === "notifications" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Notificações</Text>
          <View style={{ gap: 12, marginTop: 12 }}>
            <ToggleRow label="Falhas de execução" defaultOn />
            <ToggleRow label="Importações concluídas" defaultOn />
            <ToggleRow label="PRs aguardando review" defaultOn />
            <ToggleRow label="Bloqueios de quality gate" />
          </View>
        </Card>
      ) : null}

      {tab === "preferences" ? (
        <Card padding={22}>
          <Text style={styles.sectionTitle}>Preferências</Text>
          <View style={{ gap: 12, marginTop: 12 }}>
            <ToggleRow label="Modo escuro" />
            <ToggleRow label="Atalhos de teclado" defaultOn />
            <ToggleRow label="Tour guiado ao abrir nova sprint" />
          </View>
          <View style={{ height: 20 }} />
          <View style={styles.versionBox}>
            <View style={{ flex: 1 }}>
              <Text style={styles.versionTitle}>Versão do SendSprint</Text>
              <Text style={styles.versionText}>
                {versionCheck
                  ? versionCheck.update_available
                    ? `Update disponível: ${versionCheck.latest_version}`
                    : `Atualizado · ${versionCheck.current_version}`
                  : "Verifique se há nova versão publicada no PyPI."}
              </Text>
              {versionError ? (
                <Text style={styles.versionError}>{versionError}</Text>
              ) : null}
            </View>
            <Button
              title={checking ? "Verificando…" : "Verificar update"}
              variant="secondary"
              loading={checking}
              onPress={checkForUpdates}
            />
          </View>
        </Card>
      ) : null}
    </Screen>
  );
};

const ProviderRow: React.FC<{
  icon: IconName;
  iconColor: string;
  name: string;
  account: string;
  connected: boolean;
  onTest: () => void;
  isLast?: boolean;
}> = ({ icon, iconColor, name, account, connected, onTest, isLast }) => (
  <View style={[styles.providerRow, !isLast && styles.providerRowBorder]}>
    <View style={styles.providerIcon}>
      <Icon name={icon} size={24} color={iconColor} />
    </View>
    <View style={styles.providerName}>
      <Text style={styles.providerNameText}>{name}</Text>
    </View>
    <Text style={styles.providerAccount} numberOfLines={1}>
      {account}
    </Text>
    <View style={styles.providerStatus}>
      <View
        style={[
          styles.statusDot,
          connected ? styles.statusDotOn : styles.statusDotOff,
        ]}
      />
      <Text
        style={[
          styles.statusText,
          {
            color: connected ? theme.success : theme.textMuted,
          },
        ]}
      >
        {connected ? "Conectado" : "Pendente"}
      </Text>
    </View>
    <Pressable style={styles.providerActionBtn} onPress={onTest}>
      <Icon name="refresh" size={12} color={theme.text} />
      <Text style={styles.providerActionText}>Testar</Text>
    </Pressable>
    <Pressable style={styles.providerMore}>
      <Icon name="more" size={16} color={theme.textMuted} />
    </Pressable>
  </View>
);

const ModelRow: React.FC<{
  name: string;
  model: string;
  provider: string;
  context: string;
  status: string;
  statusOn: boolean;
}> = ({ name, model, provider, context, status, statusOn }) => (
  <View style={styles.modelRow}>
    <View style={styles.modelCell}>
      <Text style={styles.modelName}>{name}</Text>
    </View>
    <View style={styles.modelCell}>
      <Text style={styles.modelValue}>{model}</Text>
    </View>
    <View style={styles.modelCell}>
      <Text style={styles.modelValue}>{provider}</Text>
    </View>
    <View style={styles.modelCell}>
      <Text style={styles.modelValue}>{context}</Text>
    </View>
    <View style={styles.modelCell}>
      {statusOn ? (
        <Text style={[styles.modelValue, { color: theme.success, fontWeight: "700" }]}>
          {status}
        </Text>
      ) : (
        <Toggle on={false} />
      )}
    </View>
    <Pressable style={styles.modelEditBtn}>
      <Text style={styles.modelEditText}>
        {statusOn ? "Editar" : "Ativar"}
      </Text>
    </Pressable>
  </View>
);

const ToggleRow: React.FC<{
  label: string;
  defaultOn?: boolean;
}> = ({ label, defaultOn }) => {
  const [on, setOn] = useState(!!defaultOn);
  return (
    <View style={styles.toggleRow}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <Pressable onPress={() => setOn((v) => !v)}>
        <Toggle on={on} />
      </Pressable>
    </View>
  );
};

const Toggle: React.FC<{ on: boolean }> = ({ on }) => (
  <View style={[styles.toggleTrack, on && styles.toggleTrackOn]}>
    <View style={[styles.toggleThumb, on && styles.toggleThumbOn]} />
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
  sectionHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  sectionTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  subSectionTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  subSectionText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    lineHeight: 19,
    marginTop: 4,
  },
  providerList: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    overflow: "hidden",
  },
  providerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 14,
    gap: 14,
  },
  providerRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  providerIcon: {
    width: 28,
    alignItems: "center",
  },
  providerName: {
    width: 120,
  },
  providerNameText: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  providerAccount: {
    flex: 1,
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  providerStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    width: 110,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusDotOn: {
    backgroundColor: theme.success,
  },
  statusDotOff: {
    backgroundColor: theme.textSoft,
  },
  statusText: {
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  providerActionBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: theme.border,
  },
  providerActionText: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  providerMore: {
    padding: 6,
  },
  modelHeader: {
    flexDirection: "row",
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginTop: 12,
    backgroundColor: theme.surfaceAlt,
    borderRadius: 8,
  },
  modelHeaderCell: {
    flex: 1,
  },
  modelHeaderText: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  modelRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  modelCell: {
    flex: 1,
  },
  modelName: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  modelValue: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  modelEditBtn: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: theme.border,
    minWidth: 80,
    alignItems: "center",
  },
  modelEditText: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  toggleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  toggleLabel: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  toggleTrack: {
    width: 40,
    height: 22,
    borderRadius: 11,
    backgroundColor: theme.borderStrong,
    padding: 3,
  },
  toggleTrackOn: {
    backgroundColor: theme.primary,
  },
  toggleThumb: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: "#fff",
  },
  toggleThumbOn: {
    transform: [{ translateX: 18 }],
  },
  versionBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: 16,
    backgroundColor: theme.surfaceAlt,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: theme.border,
  },
  versionTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  versionText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: 4,
  },
  versionError: {
    color: theme.danger,
    fontSize: 11,
    fontFamily: theme.fontMono,
    marginTop: 6,
  },
});
