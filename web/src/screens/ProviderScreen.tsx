import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { Provider } from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Provider">;

type ProviderOption = {
  id: Provider | "github";
  name: string;
  initial: string;
  desc: string;
  available: boolean;
};

const PROVIDERS: ProviderOption[] = [
  {
    id: "jira",
    name: "Jira / Atlassian",
    initial: "J",
    desc: "Cloud ou Server. Auth via email + API token.",
    available: true,
  },
  {
    id: "azuredevops",
    name: "Azure DevOps",
    initial: "A",
    desc: "Sprint URL atual + Personal Access Token.",
    available: true,
  },
  {
    id: "github",
    name: "GitHub",
    initial: "G",
    desc: "Ja visivel na origem do trabalho. Intake completo entra quando o backend expor issues e projects.",
    available: false,
  },
];

export const ProviderScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { setProvider } = useSession();

  return (
    <Screen
      title="De onde vem o trabalho?"
      subtitle="Escolha a origem que o backend vai consultar. GitHub aparece no fluxo web mesmo antes do intake completo."
    >
      {PROVIDERS.map((provider) => (
        <Card
          key={provider.id}
          onPress={() => {
            if (!provider.available) {
              Alert.alert(
                "GitHub em preparo",
                "A autenticacao do CLI ja aparece no painel. A captura completa de issues e projects ainda depende do backend.",
              );
              return;
            }
            setProvider(provider.id as Provider);
            nav.navigate("Auth");
          }}
        >
          <View style={styles.row}>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{provider.initial}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{provider.name}</Text>
              <Text style={styles.desc}>{provider.desc}</Text>
            </View>
            <Text style={styles.chev}>{provider.available ? ">" : "i"}</Text>
          </View>
        </Card>
      ))}
    </Screen>
  );
};

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  badge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  badgeText: {
    color: theme.primary,
    fontSize: 14,
    fontWeight: "800",
  },
  name: { color: theme.text, fontSize: 17, fontWeight: "700" },
  desc: { color: theme.textMuted, fontSize: 13, marginTop: 4, lineHeight: 18 },
  chev: { color: theme.primarySoft, fontSize: 22, fontWeight: "700" },
});
