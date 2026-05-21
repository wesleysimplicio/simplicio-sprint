import { CommonActions, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage, getApiErrorStatusLine } from "../api/client";
import type { AuthResponse, CurrentSprint, SprintDetail } from "../api/types";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
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
  if (res.user_display_name) parts.push(`Usuario: ${res.user_display_name}`);
  if (res.ado_team_path) parts.push(`Time: ${res.ado_team_path}`);
  if (res.ado_iteration_path) parts.push(`Iteracao: ${res.ado_iteration_path}`);
  if (res.fallback_used) {
    parts.push(`Fallback: ${res.capture_transport ?? "browser capture"}`);
  }
  return parts.join(" | ");
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
  const [jEmail, setJEmail] = useState("");
  const [jToken, setJToken] = useState("");
  const [jBoardId, setJBoard] = useState("");
  const [jSprintId, setJSprintId] = useState("");
  const [jSprintUrl, setJSprintUrl] = useState("");

  const [aSprintUrl, setASprintUrl] = useState("");
  const [aPat, setAPat] = useState("");
  const [aOrg, setAOrg] = useState("");
  const [aProject, setAProject] = useState("");
  const [aTeam, setATeam] = useState("");

  const goToSprint = (sprintId: string) => {
    nav.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: "Dashboard" }, { name: "SprintDetail", params: { sprintId } }],
      }),
    );
  };

  const importJiraSprint = async (baseUrl: string): Promise<SprintDetail | null> => {
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
    const pat = aPat.trim();
    const organization = aOrg.trim();
    const project = aProject.trim();
    const team = aTeam.trim();

    if (provider === "jira" && (!jiraBase || !jiraEmail || !jiraToken)) {
      setNotice({
        kind: "error",
        title: "Campos obrigatorios",
        message: "Informe Base URL, email e API token para validar o Jira.",
      });
      return;
    }

    if (provider === "azuredevops" && ((!sprintUrl && (!organization || !project)) || !pat)) {
      setNotice({
        kind: "error",
        title: "Campos obrigatorios",
        message:
          "Informe a URL da sprint ou Organization + Project, junto com o Personal Access Token do Azure DevOps.",
      });
      return;
    }

    setBusy(true);
    try {
      if (provider === "jira") {
        setNotice({
          kind: "loading",
          title: "Conectando Jira",
          message:
            "Validando credenciais. Se o backend receber 401 e houver Sprint URL, ele tenta Playwright e os fallbacks de browser agent.",
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

        const imported = await importJiraSprint(jiraBase);
        if (imported) {
          await setCurrentSprint(toJiraCurrentSprint(imported, jiraBase, jiraSprintUrl));
          setNotice({
            kind: "success",
            title: "Jira conectado",
            message: `${formatAuthSuccess(res)}. Sprint ${imported.sprint.name} importada para o backlog.`,
          });
          goToSprint(imported.sprint.id);
          return;
        }

        setNotice({
          kind: "success",
          title: "Jira conectado",
          message: `${formatAuthSuccess(res)}. Nenhuma sprint foi importada automaticamente; abrindo a listagem.`,
        });
        nav.navigate("Sprints");
        return;
      }

      if (provider === "azuredevops") {
        setNotice({
          kind: "loading",
          title: "Conectando Azure DevOps",
          message:
            "Validando a sprint URL e o PAT. Em 401, o backend tenta Playwright primeiro e depois os browser agents instalados.",
        });
        const res = await api.authAzure({
          sprint_url: sprintUrl,
          pat,
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
            message: `${formatAuthSuccess(res)}. O backend conectou, mas nao retornou a iteracao atual.`,
          });
          nav.navigate("Sprints");
          return;
        }

        const imported = await api.getSprint(res.ado_iteration_path, "azuredevops");
        await setCurrentSprint(toAzureCurrentSprint(imported, res, sprintUrl));
        setNotice({
          kind: "success",
          title: "Azure DevOps conectado",
          message: `${formatAuthSuccess(res)}. Sprint ${imported.sprint.name} importada para o backlog.`,
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
        title: provider === "azuredevops" ? "Azure DevOps nao conectou" : "Auth falhou",
        message: getApiErrorMessage(e),
        statusLine: getApiErrorStatusLine(e),
      });
    } finally {
      setBusy(false);
    }
  };

  if (provider === "jira") {
    return (
      <Screen
        title="Jira"
        subtitle="Conecte o Jira e, se houver Sprint URL, importe a sprint imediatamente para o backlog interno do SendSprint."
      >
        <Input
          label="Base URL"
          value={jBase}
          onChangeText={setJBase}
          placeholder="https://org.atlassian.net"
          keyboardType="url"
          monospace
        />
        <Input
          label="Email"
          value={jEmail}
          onChangeText={setJEmail}
          placeholder="dev@org.com"
          keyboardType="email-address"
        />
        <Input
          label="API Token"
          value={jToken}
          onChangeText={setJToken}
          placeholder="ATATT3xFfGF..."
          secureTextEntry
          monospace
        />
        <Input
          label="Board ID (opcional)"
          value={jBoardId}
          onChangeText={setJBoard}
          placeholder="42"
          keyboardType="numeric"
          monospace
        />
        <Input
          label="Sprint ID (opcional)"
          value={jSprintId}
          onChangeText={setJSprintId}
          placeholder="131"
          keyboardType="default"
          monospace
        />
        <Input
          label="Sprint URL (opcional)"
          value={jSprintUrl}
          onChangeText={setJSprintUrl}
          placeholder="https://org.atlassian.net/jira/software/projects/..."
          keyboardType="url"
          monospace
        />
        <StatusNotice notice={notice} />
        <View style={{ height: 8 }} />
        <Button title="Conectar e importar sprint" onPress={submit} loading={busy} />
        <Text style={styles.hint}>
          O token vai para o keyring do sistema. Com Sprint URL, o backend pode degradar para
          Playwright e browser agents quando a API responder 401.
        </Text>
      </Screen>
    );
  }

  return (
    <Screen
      title="Azure DevOps"
      subtitle="Informe a Sprint URL atual e o PAT. Se a API responder 401, o backend inicia o fallback de captura e importa a sprint no backlog."
    >
      <Input
        label="Sprint URL atual"
        value={aSprintUrl}
        onChangeText={setASprintUrl}
        placeholder="https://dev.azure.com/org/project/_sprints/taskboard/..."
        keyboardType="url"
        monospace
      />
      <Input
        label="Personal Access Token"
        value={aPat}
        onChangeText={setAPat}
        placeholder="********"
        secureTextEntry
        monospace
      />
      <Input
        label="Organization (opcional)"
        value={aOrg}
        onChangeText={setAOrg}
        placeholder="DigitalProjects-Americas"
        monospace
      />
      <Input
        label="Project (opcional)"
        value={aProject}
        onChangeText={setAProject}
        placeholder="ONS-16058-MANUTSIS-FORT"
        monospace
      />
      <Input
        label="Team (opcional)"
        value={aTeam}
        onChangeText={setATeam}
        placeholder="Time_019"
        monospace
      />
      <StatusNotice notice={notice} />
      <View style={{ height: 8 }} />
      <Button title="Conectar e importar sprint" onPress={submit} loading={busy} />
      <Text style={styles.hint}>
        O PAT fica no keyring do sistema pelo backend local. Com 401, o backend tenta Playwright
        primeiro e depois Claude, Codex, Hermes e OpenClaw quando instalados/configurados.
      </Text>
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
      {notice.statusLine ? <Text style={styles.noticeMeta}>Backend: {notice.statusLine}</Text> : null}
    </View>
  );
};

const styles = StyleSheet.create({
  hint: { color: theme.textMuted, fontSize: 12, fontFamily: theme.fontMono },
  notice: {
    borderRadius: theme.radius,
    borderWidth: 1,
    padding: 14,
    gap: 4,
  },
  noticeLoading: {
    backgroundColor: theme.surfaceAlt,
    borderColor: theme.primarySoft,
  },
  noticeSuccess: {
    backgroundColor: "rgba(30, 169, 124, 0.10)",
    borderColor: theme.success,
  },
  noticeError: {
    backgroundColor: "rgba(207, 81, 97, 0.10)",
    borderColor: theme.danger,
  },
  noticeTitle: { color: theme.text, fontSize: 14, fontWeight: "800" },
  noticeText: { color: theme.textMuted, fontSize: 13, lineHeight: 18 },
  noticeMeta: { color: theme.textMuted, fontSize: 12, fontFamily: theme.fontMono },
});
