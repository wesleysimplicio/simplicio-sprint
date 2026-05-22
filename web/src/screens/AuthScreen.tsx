import { CommonActions, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage, getApiErrorStatusLine } from "../api/client";
import type { AuthResponse, CurrentSprint, SprintDetail } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
import { Input, SelectInput } from "../components/Input";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Auth">;
type NoticeKind = "loading" | "success" | "error";
type Notice = {
  kind: NoticeKind;
  title: string;
  message: string;
  statusLine?: string | null;
};

const formatAuthSuccess = (res: AuthResponse): string => {
  const parts = [`Conta: ${res.account}`];
  if (res.user_display_name) parts.push(`Usuário: ${res.user_display_name}`);
  if (res.ado_team_path) parts.push(`Time: ${res.ado_team_path}`);
  if (res.ado_iteration_path) parts.push(`Iteração: ${res.ado_iteration_path}`);
  if (res.fallback_used) {
    parts.push(`Fallback: ${res.capture_transport ?? "browser capture"}`);
  }
  return parts.join(" · ");
};

const toJiraCurrentSprint = (
  detail: SprintDetail,
  baseUrl: string,
  sprintUrl: string,
): CurrentSprint => {
  const host = safeHostname(baseUrl);
  return {
    provider: "jira",
    sprintId: detail.sprint.id,
    sprintName: detail.sprint.name,
    sprintUrl: sprintUrl || null,
    portfolioName: host ? host.split(".")[0] : "jira",
    projectName: host ?? "jira",
    teamName: null,
  };
};

const toAzureCurrentSprint = (
  detail: SprintDetail,
  res: AuthResponse,
  sprintUrl: string,
): CurrentSprint => {
  const [portfolioName, projectName, teamName] = (res.ado_team_path ?? "")
    .split("/")
    .filter(Boolean);
  return {
    provider: "azuredevops",
    sprintId: detail.sprint.id,
    sprintName: detail.sprint.name,
    sprintUrl: sprintUrl || null,
    portfolioName: portfolioName ?? null,
    projectName: projectName ?? null,
    teamName: teamName ?? null,
  };
};

const safeHostname = (value: string): string | null => {
  try {
    return new URL(value).hostname;
  } catch {
    return null;
  }
};

export const AuthScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const {
    session,
    api,
    setAccount,
    setAdoTeamPath,
    setCurrentSprint,
    setJiraBoardId,
  } = useSession();
  const provider = session.provider;

  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [jBase, setJBase] = useState("");
  const [jEmail, setJEmail] = useState(session.appUser?.email ?? "");
  const [jToken, setJToken] = useState("");
  const [jBoardId, setJBoard] = useState("");
  const [jSprintId, setJSprintId] = useState("");
  const [jSprintUrl, setJSprintUrl] = useState("");

  const [aSprintUrl, setASprintUrl] = useState("");
  const [aUserEmail, setAUserEmail] = useState(session.appUser?.email ?? "");
  const [aPat, setAPat] = useState("");
  const [aOrg, setAOrg] = useState("");
  const [aProject, setAProject] = useState("");
  const [aTeam, setATeam] = useState("");

  const goToSprint = (sprintId: string) => {
    nav.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [
          { name: "Dashboard" },
          { name: "SprintDetail", params: { sprintId } },
        ],
      }),
    );
  };

  const importJiraSprint = async (): Promise<SprintDetail | null> => {
    const boardId = jBoardId.trim();
    const sprintId = jSprintId.trim() || "browser-captured";
    const sprintUrl = jSprintUrl.trim();
    if (boardId) {
      const sprints = await api.listSprints("jira", { board_id: boardId });
      const first = sprints[0];
      if (!first) return null;
      return api.getSprint(first.id, "jira");
    }
    if (sprintUrl) {
      return api.getSprint(sprintId, "jira");
    }
    return null;
  };

  const submit = async () => {
    if (busy) return;
    setNotice(null);

    const jiraBase = jBase.trim().replace(/\/+$/, "");
    const jiraEmail = jEmail.trim();
    const jiraToken = jToken.trim();
    const jiraBoardId = jBoardId.trim();
    const jiraSprintId = jSprintId.trim();
    const jiraSprintUrl = jSprintUrl.trim();
    const sprintUrl = aSprintUrl.trim();
    const azureUserEmail = aUserEmail.trim().toLowerCase();
    const pat = aPat.trim();
    const organization = aOrg.trim();
    const project = aProject.trim();
    const team = aTeam.trim();

    if (provider === "jira" && (!jiraBase || !jiraEmail || !jiraToken)) {
      setNotice({
        kind: "error",
        title: "Campos obrigatórios",
        message: "Informe Base URL, email e API token para validar o Jira.",
      });
      return;
    }

    if (
      provider === "azuredevops" &&
      ((!sprintUrl && (!organization || !project)) ||
        !azureUserEmail ||
        !pat)
    ) {
      setNotice({
        kind: "error",
        title: "Campos obrigatórios",
        message:
          "Informe o e-mail, a URL da sprint ou Organização + Projeto e o Personal Access Token.",
      });
      return;
    }

    setBusy(true);
    try {
      if (provider === "jira") {
        setNotice({
          kind: "loading",
          title: "Conectando Jira",
          message: "Validando credenciais…",
        });
        const res = await api.authJira({
          base_url: jiraBase,
          email: jiraEmail,
          api_token: jiraToken,
          sprint_url: jiraSprintUrl || undefined,
          sprint_id: jiraSprintId || undefined,
        });
        await setAccount(res.account);
        await setJiraBoardId(jiraBoardId || null);
        await setAdoTeamPath(null);
        setJToken("");

        const imported = await importJiraSprint();
        if (imported) {
          await setCurrentSprint(
            toJiraCurrentSprint(imported, jiraBase, jiraSprintUrl),
          );
          setNotice({
            kind: "success",
            title: "Jira conectado",
            message: `${formatAuthSuccess(res)} · Sprint ${imported.sprint.name} importada.`,
          });
          goToSprint(imported.sprint.id);
          return;
        }

        setNotice({
          kind: "success",
          title: "Jira conectado",
          message: `${formatAuthSuccess(res)} · Nenhuma sprint importada.`,
        });
        nav.navigate("Sprints");
        return;
      }

      if (provider === "azuredevops") {
        setNotice({
          kind: "loading",
          title: "Conectando Azure DevOps",
          message: "Validando a sprint URL e o PAT…",
        });
        const res = await api.authAzure({
          sprint_url: sprintUrl,
          pat,
          user_email: azureUserEmail,
          organization: organization || undefined,
          project: project || undefined,
          team: team || undefined,
        });
        await setAccount(res.account);
        await setAdoTeamPath(res.ado_team_path ?? null);
        await setJiraBoardId(null);
        setAPat("");

        if (!res.ado_iteration_path) {
          setNotice({
            kind: "success",
            title: "Azure DevOps conectado",
            message: `${formatAuthSuccess(res)} · Iteração atual não detectada.`,
          });
          nav.navigate("Sprints");
          return;
        }

        const imported = await api.getSprint(
          res.ado_iteration_path,
          "azuredevops",
        );
        await setCurrentSprint(toAzureCurrentSprint(imported, res, sprintUrl));
        setNotice({
          kind: "success",
          title: "Azure DevOps conectado",
          message: `${formatAuthSuccess(res)} · Sprint ${imported.sprint.name} importada.`,
        });
        goToSprint(imported.sprint.id);
        return;
      }

      setNotice({
        kind: "error",
        title: "Provedor ausente",
        message: "Escolha Jira ou Azure DevOps antes de autenticar.",
      });
    } catch (e) {
      setNotice({
        kind: "error",
        title:
          provider === "azuredevops"
            ? "Azure DevOps não conectou"
            : "Autenticação falhou",
        message: getApiErrorMessage(e),
        statusLine: getApiErrorStatusLine(e),
      });
    } finally {
      setBusy(false);
    }
  };

  if (provider === "jira") {
    return (
      <Screen>
        <Card style={styles.formCard} padding={28}>
          <View style={styles.formHeader}>
            <View style={styles.providerIcon}>
              <Icon name="jira" size={36} color="#2684ff" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.formTitle}>Conectar Jira</Text>
              <Text style={styles.formSubtitle}>
                Conecte seu Jira para importar sprints e issues.
              </Text>
              <Pressable>
                <Text style={styles.learnLink}>Saiba como gerar um token</Text>
              </Pressable>
            </View>
          </View>

          <View style={styles.formGrid}>
            <View style={styles.formCol}>
              <Input
                label="Base URL"
                value={jBase}
                onChangeText={setJBase}
                placeholder="https://suaempresa.atlassian.net"
                keyboardType="url"
                monospace
              />
            </View>
            <View style={styles.formCol}>
              <Input
                label="Board ID"
                value={jBoardId}
                onChangeText={setJBoard}
                placeholder="Ex: 123"
                keyboardType="numeric"
              />
            </View>
            <View style={styles.formCol}>
              <Input
                label="E-mail"
                value={jEmail}
                onChangeText={setJEmail}
                placeholder="voce@empresa.com"
                keyboardType="email-address"
              />
            </View>
            <View style={styles.formCol}>
              <Input
                label="Sprint ID"
                value={jSprintId}
                onChangeText={setJSprintId}
                placeholder="Ex: 456"
              />
            </View>
            <View style={styles.formCol}>
              <Input
                label="Token API"
                value={jToken}
                onChangeText={setJToken}
                placeholder="••••••••••••••••••"
                secureTextEntry
                monospace
              />
            </View>
            <View style={styles.formCol}>
              <Input
                label="Sprint URL (opcional)"
                value={jSprintUrl}
                onChangeText={setJSprintUrl}
                placeholder="https://suaempresa.atlassian.net/browse/SPR-1"
                keyboardType="url"
                monospace
              />
            </View>
          </View>

          <StatusNotice notice={notice} />

          <View style={styles.formActions}>
            <Button title="Cancelar" variant="ghost" onPress={() => nav.goBack()} />
            <Button
              title={busy ? "Conectando…" : "Conectar"}
              onPress={submit}
              loading={busy}
            />
          </View>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={styles.azureSplit}>
        <Card style={styles.formCard} padding={28}>
          <View style={styles.formHeader}>
            <View style={styles.providerIcon}>
              <Icon name="azure" size={36} color="#0078d4" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.formTitle}>Conectar Azure DevOps</Text>
              <Text style={styles.formSubtitle}>
                Conecte sua organização para importar sprints, work items e equipes.
              </Text>
              <Pressable>
                <Text style={styles.learnLink}>Saiba como gerar um PAT</Text>
              </Pressable>
            </View>
          </View>

          <Input
            label="URL da Organização"
            value={aSprintUrl}
            onChangeText={setASprintUrl}
            placeholder="https://dev.azure.com/sua-organizacao"
            keyboardType="url"
            monospace
          />

          <Input
            label="Personal Access Token (PAT)"
            value={aPat}
            onChangeText={setAPat}
            placeholder="••••••••••••••••••••••••"
            secureTextEntry
            monospace
          />

          <Input
            label="E-mail do usuário"
            value={aUserEmail}
            onChangeText={setAUserEmail}
            placeholder="voce@empresa.com"
            keyboardType="email-address"
          />

          <View style={styles.organizationField}>
            <Text style={styles.fieldLabel}>Organização</Text>
            {aOrg ? (
              <Input
                label=""
                value={aOrg}
                onChangeText={setAOrg}
                placeholder="contoso"
              />
            ) : (
              <SelectInput
                value={aOrg}
                placeholder="Selecione a organização"
                onPress={() => setAOrg("contoso")}
              />
            )}
          </View>

          <View style={styles.formGrid}>
            <View style={styles.formCol}>
              <Text style={styles.fieldLabel}>Projeto</Text>
              {aProject ? (
                <Input
                  label=""
                  value={aProject}
                  onChangeText={setAProject}
                  placeholder="Plataforma"
                />
              ) : (
                <SelectInput
                  value={aProject}
                  placeholder="Selecione o projeto"
                  onPress={() => setAProject("Plataforma")}
                />
              )}
            </View>
            <View style={styles.formCol}>
              <Text style={styles.fieldLabel}>Equipe (opcional)</Text>
              {aTeam ? (
                <Input
                  label=""
                  value={aTeam}
                  onChangeText={setATeam}
                  placeholder="Time A"
                />
              ) : (
                <SelectInput
                  value={aTeam}
                  placeholder="Selecione a equipe"
                  onPress={() => setATeam("Time A")}
                />
              )}
            </View>
          </View>

          <StatusNotice notice={notice} />

          <View style={styles.formActions}>
            <Button title="Cancelar" variant="ghost" onPress={() => nav.goBack()} />
            <Button
              title={busy ? "Conectando…" : "Conectar"}
              onPress={submit}
              loading={busy}
            />
          </View>
        </Card>

        <Card style={styles.fallbackCard} variant="muted" padding={22}>
          <Text style={styles.fallbackTitle}>Sobre o fallback</Text>
          <Text style={styles.fallbackText}>
            Caso alguma API do Azure DevOps não esteja disponível em sua
            organização, o SendSprint utilizará APIs alternativas e técnicas de
            fallback para garantir a importação e continuidade do processo.
          </Text>
          <Pressable>
            <Text style={styles.learnLink}>Saiba mais</Text>
          </Pressable>
        </Card>
      </View>
    </Screen>
  );
};

const StatusNotice: React.FC<{ notice: Notice | null }> = ({ notice }) => {
  if (!notice) return null;
  return (
    <View
      style={[
        styles.notice,
        notice.kind === "loading" && styles.noticeLoading,
        notice.kind === "success" && styles.noticeSuccess,
        notice.kind === "error" && styles.noticeError,
      ]}
    >
      <Text style={styles.noticeTitle}>{notice.title}</Text>
      <Text style={styles.noticeText}>{notice.message}</Text>
      {notice.statusLine ? (
        <Text style={styles.noticeMeta}>Backend: {notice.statusLine}</Text>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  formCard: {
    flex: 1,
    minWidth: 480,
    gap: 16,
  },
  azureSplit: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
    alignItems: "flex-start",
  },
  fallbackCard: {
    width: 280,
    minWidth: 240,
    gap: 10,
  },
  fallbackTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  fallbackText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 19,
    fontFamily: theme.fontSans,
  },
  formHeader: {
    flexDirection: "row",
    gap: 14,
    alignItems: "flex-start",
    marginBottom: 6,
  },
  providerIcon: {
    width: 52,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
  },
  formTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  formSubtitle: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: 4,
    lineHeight: 18,
  },
  learnLink: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
    marginTop: 6,
  },
  organizationField: {
    gap: 6,
  },
  fieldLabel: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  formGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
  },
  formCol: {
    flex: 1,
    minWidth: 220,
    gap: 6,
  },
  formActions: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 12,
  },
  notice: {
    borderRadius: theme.radius,
    borderWidth: 1,
    padding: 14,
    gap: 4,
  },
  noticeLoading: {
    backgroundColor: theme.infoSoft,
    borderColor: theme.info,
  },
  noticeSuccess: {
    backgroundColor: theme.successSoft,
    borderColor: theme.success,
  },
  noticeError: {
    backgroundColor: theme.dangerSoft,
    borderColor: theme.danger,
  },
  noticeTitle: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  noticeText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    lineHeight: 18,
  },
  noticeMeta: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontMono,
  },
});
