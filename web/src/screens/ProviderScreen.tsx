import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import type { Provider } from "../api/types";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Provider">;

const PROVIDERS: { id: Provider; name: string; emoji: string; desc: string }[] = [
  {
    id: "jira",
    name: "Jira / Atlassian",
    emoji: "🟦",
    desc: "Cloud ou Server. Auth via email + API token.",
  },
  {
    id: "azuredevops",
    name: "Azure DevOps",
    emoji: "🟪",
    desc: "Org + project + Personal Access Token.",
  },
];

export const ProviderScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { setProvider } = useSession();

  return (
    <Screen
      title="De onde vem a sprint?"
      subtitle="Escolha o gerenciador de tarefas que o backend vai consultar."
    >
      {PROVIDERS.map((p) => (
        <Card key={p.id} onPress={() => {
          setProvider(p.id);
          nav.navigate("Auth");
        }}>
          <View style={styles.row}>
            <Text style={styles.emoji}>{p.emoji}</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{p.name}</Text>
              <Text style={styles.desc}>{p.desc}</Text>
            </View>
            <Text style={styles.chev}>›</Text>
          </View>
        </Card>
      ))}
    </Screen>
  );
};

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  emoji: { fontSize: 30 },
  name: { color: theme.text, fontSize: 17, fontWeight: "700" },
  desc: { color: theme.textMuted, fontSize: 13, marginTop: 4 },
  chev: { color: theme.primarySoft, fontSize: 28, fontWeight: "300" },
});
