import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage, getApiErrorStatusLine } from "../api/client";
import type { AuthResponse } from "../api/types";
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
  return parts.join(" | ");
};

export const AuthScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { session, api, setAccount, setJiraBoardId, setAdoTeamPath } = useSession();
  const provider = session.provider;

  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [jBase, setJBase] = useState("");
  const [jEmail, setJEmail] = useState("");
  const [jToken, setJToken] = useState("");
  const [jBoardId, setJBoard] = useState("");

  const [aSprintUrl, setASprintUrl] = useState("");
  const [aPat, setAPat] = useState("");

  const submit = async () => {
    if (busy) return;
    setNotice(null);

    const jiraBase = jBase.trim().replace(/\/+$/, "");
    const jiraEmail = jEmail.trim();
    const jiraToken = jToken.trim();
    const jiraBoardId = jBoardId.trim();
    const sprintUrl = aSprintUrl.trim();
    const pat = aPat.trim();

    if (provider === "jira" && (!jiraBase || !jiraEmail || !jiraToken)) {
      setNotice({
        kind: "error",
        title: "Campos obrigatorios",
        message: "Informe Base URL, email e API token para validar o Jira.",
      });
      return;
    }

    if (provider === "azuredevops" && (!sprintUrl || !pat)) {
      setNotice({
        kind: "error",
        title: "Campos obrigatorios",
        message: "Informe a URL da sprint atual e o Personal Access Token do Azure DevOps.",
      });
      return;
    }

    setBusy(true);
    try {
      if (provider === "jira") {
        setNotice({
          kind: "loading",
          title: "Validando Jira",
          message: "Enviando credenciais ao backend local para gravar o token no keyring do SO.",
        });
        const res = await api.authJira({
          base_url: jiraBase,
          email: jiraEmail,
          api_token: jiraToken,
        });
        await setAccount(res.account);
        await setJiraBoardId(jiraBoardId || null);
        setJToken("");
        setNotice({
          kind: "success",
          title: "Jira conectado",
          message: `${formatAuthSuccess(res)}. Listando sprints ativas agora.`,
        });
      } else if (provider === "azuredevops") {
        setNotice({
          kind: "loading",
          title: "Validando Azure DevOps",
          message:
            "Enviando a URL da sprint e o PAT ao backend local; o PAT fica no keyring do SO.",
        });
        const res = await api.authAzure({
          sprint_url: sprintUrl,
          pat,
        });
        await setAccount(res.account);
        await setAdoTeamPath(res.ado_team_path ?? null);
        setAPat("");
        setNotice({
          kind: "success",
          title: "Azure DevOps conectado",
          message: `${formatAuthSuccess(res)}. Listando sprints ativas agora.`,
        });
      } else {
        setNotice({
          kind: "error",
          title: "Provedor ausente",
          message: "Escolha Jira ou Azure DevOps antes de autenticar.",
        });
        return;
      }
      nav.navigate("Sprints");
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
        subtitle="O token fica salvo no keyring do SO no backend local. Ele nao e persistido no app web."
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
        <StatusNotice notice={notice} />
        <View style={{ height: 8 }} />
        <Button title="Autenticar e listar sprints" onPress={submit} loading={busy} />
        <Text style={styles.hint}>
          O token e gerado em https://id.atlassian.com/manage-profile/security/api-tokens
        </Text>
      </Screen>
    );
  }

  return (
    <Screen
      title="Azure DevOps"
      subtitle="Informe a URL da sprint atual e o PAT. O backend infere organization, project e team/iteration."
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
      <StatusNotice notice={notice} />
      <View style={{ height: 8 }} />
      <Button title="Autenticar e listar sprints" onPress={submit} loading={busy} />
      <Text style={styles.hint}>
        O PAT fica no keyring do SO pelo backend local. Use escopo de sprint/work items e code
        se for abrir PRs.
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
