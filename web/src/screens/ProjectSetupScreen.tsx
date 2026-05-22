import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type {
  ProjectSetup,
  RepositoryRegistration,
  RepositoryRole,
} from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon, type IconName } from "../components/Icon";
import { Input, SelectInput } from "../components/Input";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "ProjectSetup">;
type Tab =
  | "general"
  | "repository"
  | "roles"
  | "branches"
  | "ai"
  | "policies"
  | "notifications";

const TABS: Array<{ key: Tab; label: string; icon: IconName }> = [
  { key: "general", label: "Geral", icon: "home" },
  { key: "repository", label: "Repositório", icon: "folder" },
  { key: "roles", label: "Papéis", icon: "users" },
  { key: "branches", label: "Branches", icon: "branch" },
  { key: "ai", label: "IA & Execução", icon: "model" },
  { key: "policies", label: "Políticas", icon: "shield" },
  { key: "notifications", label: "Notificações", icon: "bell" },
];

const ROLE_LABELS: Record<RepositoryRole, string> = {
  frontend: "Frontend",
  backend: "Backend",
  fullstack: "Desenvolvedor",
  mobile: "Mobile",
  infra: "Infra / DevOps",
  docs: "Documentação",
  shared: "Time compartilhado",
  other: "Outro",
};

const ROLE_KEYS = Object.keys(ROLE_LABELS) as RepositoryRole[];

export const ProjectSetupScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { session, setProjectSetup } = useSession();
  const [draft, setDraft] = useState<ProjectSetup>(() =>
    ensureSetup(session.projectSetup),
  );
  const [projectName, setProjectName] = useState("Plataforma");
  const [projectDesc, setProjectDesc] = useState(
    "Serviços e APIs da plataforma principal.",
  );
  const [tab, setTab] = useState<Tab>("general");
  const [saving, setSaving] = useState(false);
  const [showRoleSelect, setShowRoleSelect] = useState(false);

  const primaryRepo: RepositoryRegistration =
    draft.repositories[0] ?? createRepository();

  const updatePrimaryRepo = (patch: Partial<RepositoryRegistration>) => {
    setDraft((current) => {
      const repos = [...(current.repositories ?? [])];
      if (repos.length === 0) repos.push(createRepository());
      repos[0] = { ...repos[0], ...patch };
      return { ...current, repositories: repos };
    });
  };

  const save = async () => {
    if (!primaryRepo.repoPath.trim()) {
      Alert.alert(
        "Setup incompleto",
        "Informe o caminho local do repositório principal.",
      );
      return;
    }
    setSaving(true);
    try {
      await setProjectSetup({
        ...draft,
        repositories: draft.repositories.map(cleanRepository),
      });
      Alert.alert("Setup salvo", "Configurações atualizadas localmente.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen scroll={false}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 28 }}
      >
        <Card padding={0}>
          <View style={styles.setupShell}>
            <View style={styles.subnav}>
              {TABS.map((t) => {
                const active = tab === t.key;
                return (
                  <Pressable
                    key={t.key}
                    onPress={() => setTab(t.key)}
                    style={[
                      styles.subnavItem,
                      active && styles.subnavItemActive,
                    ]}
                  >
                    <Icon
                      name={t.icon}
                      size={16}
                      color={active ? theme.primary : theme.textMuted}
                    />
                    <Text
                      style={[
                        styles.subnavLabel,
                        active && styles.subnavLabelActive,
                      ]}
                    >
                      {t.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            <View style={styles.formArea}>
              {tab === "general" ? (
                <>
                  <Text style={styles.formHeader}>Configuração do projeto</Text>

                  <View style={styles.grid}>
                    <View style={styles.col}>
                      <Input
                        label="Nome do projeto"
                        value={projectName}
                        onChangeText={setProjectName}
                        placeholder="Plataforma"
                      />
                    </View>
                    <View style={styles.col}>
                      <Input
                        label="Descrição"
                        value={projectDesc}
                        onChangeText={setProjectDesc}
                        placeholder="Descreva o projeto…"
                      />
                    </View>
                  </View>

                  <View style={styles.grid}>
                    <View style={styles.col}>
                      <Text style={styles.fieldLabel}>
                        Caminho do repositório
                      </Text>
                      <View style={styles.repoFieldWrap}>
                        <Input
                          label=""
                          value={primaryRepo.repoPath}
                          onChangeText={(repoPath) =>
                            updatePrimaryRepo({ repoPath })
                          }
                          placeholder="sendsprint/platform-api"
                          monospace
                        />
                        <View style={styles.providerBadge}>
                          <Text style={styles.providerBadgeText}>
                            Provedor: GitHub
                          </Text>
                          <View style={styles.providerCheck}>
                            <Icon name="check" size={9} color="#fff" />
                          </View>
                        </View>
                      </View>
                    </View>
                    <View style={styles.col}>
                      <Text style={styles.fieldLabel}>Papel do agente</Text>
                      <SelectInput
                        value={ROLE_LABELS[primaryRepo.role]}
                        onPress={() =>
                          setShowRoleSelect((v) => !v)
                        }
                      />
                      {showRoleSelect ? (
                        <View style={styles.dropdown}>
                          {ROLE_KEYS.map((roleKey) => (
                            <Pressable
                              key={roleKey}
                              style={styles.dropdownItem}
                              onPress={() => {
                                updatePrimaryRepo({ role: roleKey });
                                setShowRoleSelect(false);
                              }}
                            >
                              <Text style={styles.dropdownItemText}>
                                {ROLE_LABELS[roleKey]}
                              </Text>
                            </Pressable>
                          ))}
                        </View>
                      ) : null}
                    </View>
                  </View>

                  <View style={styles.grid}>
                    <View style={styles.col}>
                      <Input
                        label="Padrão de branch (criação)"
                        value={draft.branchPattern}
                        onChangeText={(branchPattern) =>
                          setDraft((current) => ({
                            ...current,
                            branchPattern,
                          }))
                        }
                        placeholder="feature/{issueKey}-{slug}"
                        monospace
                        hint={`Ex: ${draft.branchPattern.replace(
                          /\{?\{issueKey\}?\}/gi,
                          "PLAT-73",
                        ).replace(/\{slug\}/g, "pagamentos")}`}
                      />
                    </View>
                    <View style={styles.col}>
                      <Input
                        label="Branch de destino (padrão)"
                        value={draft.deployTargetBranch}
                        onChangeText={(deployTargetBranch) =>
                          setDraft((current) => ({
                            ...current,
                            deployTargetBranch,
                          }))
                        }
                        placeholder="dev"
                        monospace
                        hint="Branch base para PRs e integrações."
                      />
                    </View>
                  </View>
                </>
              ) : null}

              {tab === "repository" ? (
                <>
                  <Text style={styles.formHeader}>Repositórios</Text>
                  {draft.repositories.map((repo, idx) => (
                    <Card
                      key={repo.id}
                      variant="muted"
                      padding={16}
                      style={{ marginBottom: 12 }}
                    >
                      <Text style={styles.repoCardTitle}>
                        Repositório {idx + 1}
                      </Text>
                      <View style={styles.grid}>
                        <View style={styles.col}>
                          <Input
                            label="Nome"
                            value={repo.name}
                            onChangeText={(name) =>
                              setDraft((current) => ({
                                ...current,
                                repositories: current.repositories.map((r) =>
                                  r.id === repo.id ? { ...r, name } : r,
                                ),
                              }))
                            }
                            placeholder="api-payments"
                          />
                        </View>
                        <View style={styles.col}>
                          <Input
                            label="Caminho local"
                            value={repo.repoPath}
                            onChangeText={(repoPath) =>
                              setDraft((current) => ({
                                ...current,
                                repositories: current.repositories.map((r) =>
                                  r.id === repo.id ? { ...r, repoPath } : r,
                                ),
                              }))
                            }
                            placeholder="/Users/me/code/projeto"
                            monospace
                          />
                        </View>
                      </View>
                    </Card>
                  ))}
                  <Button
                    title="Adicionar repositório"
                    variant="secondary"
                    iconLeft="plus"
                    onPress={() =>
                      setDraft((current) => ({
                        ...current,
                        mode: "portfolio",
                        repositories: [
                          ...current.repositories,
                          createRepository(current.repositories.length),
                        ],
                      }))
                    }
                  />
                </>
              ) : null}

              {tab === "roles" ? (
                <PlaceholderTab
                  title="Papéis"
                  desc="Defina papéis por repositório (frontend, backend, infra, docs, etc.)."
                />
              ) : null}

              {tab === "branches" ? (
                <>
                  <Text style={styles.formHeader}>Branches & commits</Text>
                  <View style={styles.grid}>
                    <View style={styles.col}>
                      <Input
                        label="Padrão de branch"
                        value={draft.branchPattern}
                        onChangeText={(branchPattern) =>
                          setDraft((current) => ({ ...current, branchPattern }))
                        }
                        placeholder="feature/{issueKey}-{slug}"
                        monospace
                      />
                    </View>
                    <View style={styles.col}>
                      <Input
                        label="Padrão de commit"
                        value={draft.commitPattern}
                        onChangeText={(commitPattern) =>
                          setDraft((current) => ({ ...current, commitPattern }))
                        }
                        placeholder="{type}: {summary}"
                        monospace
                      />
                    </View>
                  </View>
                  <Input
                    label="Branch alvo de deploy"
                    value={draft.deployTargetBranch}
                    onChangeText={(deployTargetBranch) =>
                      setDraft((current) => ({
                        ...current,
                        deployTargetBranch,
                      }))
                    }
                    placeholder="dev"
                    monospace
                  />
                </>
              ) : null}

              {tab === "ai" ? (
                <PlaceholderTab
                  title="IA & Execução"
                  desc="Modelo padrão, autonomia e fallback. Toda configuração fica local."
                />
              ) : null}

              {tab === "policies" ? (
                <PlaceholderTab
                  title="Políticas"
                  desc="Quem pode executar, aprovar e fazer deploy."
                />
              ) : null}

              {tab === "notifications" ? (
                <PlaceholderTab
                  title="Notificações"
                  desc="Configure canais de notificação (e-mail, Slack, webhook)."
                />
              ) : null}

              <View style={styles.formFooter}>
                <Button
                  title="Cancelar"
                  variant="ghost"
                  onPress={() => nav.goBack()}
                />
                <Button
                  title={saving ? "Salvando…" : "Salvar configurações"}
                  loading={saving}
                  onPress={save}
                />
              </View>
            </View>
          </View>
        </Card>
      </ScrollView>
    </Screen>
  );
};

const PlaceholderTab: React.FC<{ title: string; desc: string }> = ({
  title,
  desc,
}) => (
  <View style={{ paddingVertical: 30, alignItems: "center", gap: 8 }}>
    <Icon name="settings" size={32} color={theme.textSoft} />
    <Text style={styles.placeholderTitle}>{title}</Text>
    <Text style={styles.placeholderText}>{desc}</Text>
  </View>
);

const createRepository = (index: number = 0): RepositoryRegistration => ({
  id: `repo-${index + 1}-${Math.random().toString(36).slice(2, 8)}`,
  name: index === 0 ? "platform-api" : `repo-${index + 1}`,
  repoPath: index === 0 ? "sendsprint/platform-api" : "",
  role: "fullstack",
  project: "plataforma",
  validationCommands: [],
});

const cleanRepository = (
  repo: RepositoryRegistration,
): RepositoryRegistration => ({
  ...repo,
  name: repo.name.trim() || "repositorio",
  repoPath: repo.repoPath.trim(),
  project: repo.project.trim() || "default",
  validationCommands: repo.validationCommands.map((c) => c.trim()).filter(Boolean),
});

const ensureSetup = (setup: ProjectSetup): ProjectSetup => ({
  mode: setup.mode || "single",
  branchPattern: setup.branchPattern || "feature/{issueKey}-{slug}",
  commitPattern: setup.commitPattern || "{type}: {summary}",
  deployTargetBranch: setup.deployTargetBranch || "dev",
  repositories:
    setup.repositories.length > 0 ? setup.repositories : [createRepository()],
  updatedAt: setup.updatedAt,
});

const styles = StyleSheet.create({
  setupShell: {
    flexDirection: "row",
    minHeight: 580,
  },
  subnav: {
    width: 220,
    paddingVertical: 22,
    paddingHorizontal: 12,
    borderRightWidth: 1,
    borderRightColor: theme.border,
    gap: 4,
  },
  subnavItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
  },
  subnavItemActive: {
    backgroundColor: theme.primaryFaint,
  },
  subnavLabel: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  subnavLabelActive: {
    color: theme.primary,
    fontWeight: "600",
  },
  formArea: {
    flex: 1,
    padding: 28,
    gap: 22,
  },
  formHeader: {
    color: theme.text,
    fontSize: 20,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  col: {
    flex: 1,
    minWidth: 280,
    gap: 6,
  },
  fieldLabel: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  repoFieldWrap: {
    gap: 6,
  },
  providerBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    alignSelf: "flex-end",
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: theme.successSoft,
    borderRadius: 999,
    marginTop: -36,
    marginRight: 8,
  },
  providerBadgeText: {
    color: theme.success,
    fontSize: 11,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  providerCheck: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: theme.success,
    alignItems: "center",
    justifyContent: "center",
  },
  dropdown: {
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 8,
    overflow: "hidden",
    marginTop: 4,
    maxHeight: 220,
  },
  dropdownItem: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  dropdownItemText: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  repoCardTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginBottom: 10,
  },
  formFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 22,
    paddingTop: 18,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  placeholderTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    marginTop: 6,
  },
  placeholderText: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    textAlign: "center",
    maxWidth: 360,
  },
});
