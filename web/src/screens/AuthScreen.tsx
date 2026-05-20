import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Auth">;

export const AuthScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { session, api, setAccount, setJiraBoardId, setAdoTeamPath } = useSession();
  const provider = session.provider;

  const [busy, setBusy] = useState(false);
  const [jBase, setJBase] = useState("");
  const [jEmail, setJEmail] = useState("");
  const [jToken, setJToken] = useState("");
  const [jBoardId, setJBoard] = useState("");

  const [aSprintUrl, setASprintUrl] = useState("");
  const [aPat, setAPat] = useState("");

  const submit = async () => {
    setBusy(true);
    try {
      if (provider === "jira") {
        const res = await api.authJira({
          base_url: jBase,
          email: jEmail,
          api_token: jToken,
        });
        await setAccount(res.account);
        if (jBoardId) await setJiraBoardId(jBoardId);
      } else if (provider === "azuredevops") {
        const res = await api.authAzure({
          sprint_url: aSprintUrl,
          pat: aPat,
        });
        await setAccount(res.account);
        await setAdoTeamPath(res.ado_team_path ?? null);
      }
      nav.navigate("Sprints");
    } catch (e) {
      Alert.alert("Auth falhou", String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  };

  if (provider === "jira") {
    return (
      <Screen
        title="Jira"
        subtitle="O token fica salvo no keyring do SO no backend (chmod 600). Não trafega depois."
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
          placeholder="ATATT3xFfGF…"
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
        <View style={{ height: 8 }} />
        <Button title="Autenticar e listar sprints" onPress={submit} loading={busy} />
        <Text style={styles.hint}>
          O token é gerado em https://id.atlassian.com/manage-profile/security/api-tokens
        </Text>
      </Screen>
    );
  }

  return (
    <Screen
      title="Azure DevOps"
      subtitle="Informe sÃ³ a URL da sprint atual e o PAT. O backend infere organization, project e team/iteration."
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
        placeholder="••••••••"
        secureTextEntry
        monospace
      />
      <View style={{ height: 8 }} />
      <Button title="Autenticar e listar sprints" onPress={submit} loading={busy} />
      <Text style={styles.hint}>
        O PAT fica no keyring do SO. Use escopo ao menos para sprint/work items e code se for abrir PRs.
      </Text>
    </Screen>
  );
};

const styles = StyleSheet.create({
  hint: { color: theme.textMuted, fontSize: 12, fontFamily: theme.fontMono },
});
