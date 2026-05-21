import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { Provider } from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Provider">;

type ProviderOption = {
  id: Provider;
  name: string;
  initial: string;
  desc: string;
};

const PROVIDERS: ProviderOption[] = [
  {
    id: "jira",
    name: "Jira / Atlassian",
    initial: "J",
    desc: "Cloud ou Server. Auth via email + API token.",
  },
  {
    id: "azuredevops",
    name: "Azure DevOps",
    initial: "A",
    desc: "Sprint URL atual + Personal Access Token.",
  },
];

export const ProviderScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { setProvider } = useSession();

  return (
    <Screen
      chrome="app"
      eyebrow="Web 03 · Provider Picker"
      title="Conecte seu provider de trabalho"
      subtitle="Escolha a ferramenta que voce usa para gerenciar sprints e issues."
    >
      <View style={styles.grid}>
        {PROVIDERS.map((provider) => (
          <Card
            key={provider.id}
            style={styles.providerCard}
            onPress={() => {
              setProvider(provider.id);
              nav.navigate("Auth");
            }}
          >
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{provider.initial}</Text>
            </View>
            <Text style={styles.name}>{provider.name}</Text>
            <Text style={styles.desc}>{provider.desc}</Text>
            <Text style={styles.cta}>{`Conectar ${provider.name.split(" ")[0]}`}</Text>
          </Card>
        ))}
      </View>
      <Card style={styles.infoCard}>
        <Text style={styles.infoTitle}>GitHub continua visivel no shell</Text>
        <Text style={styles.infoText}>
          O CLI autenticado e o contexto de repo seguem expostos em Configuracoes. O intake completo de issues e projects do GitHub fica fora deste fluxo ate o backend expor essa origem de sprint.
        </Text>
      </Card>
    </Screen>
  );
};

const styles = StyleSheet.create({
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  providerCard: {
    width: 260,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    paddingVertical: 28,
  },
  infoCard: {
    marginTop: 16,
    maxWidth: 720,
    backgroundColor: "rgba(239,245,255,0.9)",
  },
  infoTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
  },
  infoText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
  },
  badge: {
    width: 54,
    height: 54,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  badgeText: {
    color: theme.primary,
    fontSize: 22,
    fontWeight: "800",
  },
  name: { color: theme.text, fontSize: 19, fontWeight: "700", textAlign: "center" },
  desc: { color: theme.textMuted, fontSize: 13, lineHeight: 20, textAlign: "center" },
  cta: { color: theme.primary, fontSize: 13, fontWeight: "800", marginTop: 4 },
});
