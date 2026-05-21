import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import type { Provider } from "../api/types";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
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
  status: string;
};

const PROVIDERS: ProviderOption[] = [
  {
    id: "jira",
    name: "Jira / Atlassian",
    initial: "<>",
    desc: "Cloud ou Server. Auth via email + API token com fallback por browser quando necessario.",
    available: true,
    status: "Pronto",
  },
  {
    id: "azuredevops",
    name: "Azure DevOps",
    initial: "[]",
    desc: "Sprint URL atual + Personal Access Token com capture assistida por Playwright e browser agents.",
    available: true,
    status: "Pronto",
  },
  {
    id: "github",
    name: "GitHub Projects",
    initial: "{}",
    desc: "Entrada por issues, projects e milestones fica visivel no shell, mas o intake completo ainda depende do backend.",
    available: false,
    status: "Em breve",
  },
];

export const ProviderScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { setProvider } = useSession();

  return (
    <Screen chrome="app">
      <View style={styles.pageIntro}>
        <Text style={styles.pageTitle}>Conecte seu provider de trabalho</Text>
        <Text style={styles.pageSubtitle}>
          Escolha a ferramenta que voce usa para gerenciar sprints e issues.
        </Text>
      </View>
      <View style={styles.grid}>
        {PROVIDERS.map((provider) => (
          <Card
            key={provider.id}
            style={
              provider.available
                ? styles.providerCard
                : [styles.providerCard, styles.providerCardDisabled]
            }
            onPress={
              provider.available
                ? () => {
                    void setProvider(provider.id as Provider);
                    nav.navigate("Auth");
                  }
                : undefined
            }
          >
            <View style={styles.cardTop}>
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{provider.initial}</Text>
              </View>
              <View
                style={[
                  styles.statusPill,
                  provider.available ? styles.statusReady : styles.statusSoon,
                ]}
              >
                <Text style={styles.statusPillText}>{provider.status}</Text>
              </View>
            </View>
            <Text style={styles.name}>{provider.name}</Text>
            <Text style={styles.desc}>{provider.desc}</Text>
            <Text style={[styles.cta, !provider.available && styles.ctaDisabled]}>
              {provider.available ? `Conectar ${provider.name.split(" ")[0]}` : "Aguardando backend"}
            </Text>
          </Card>
        ))}
      </View>

      <Card style={styles.infoCard}>
        <Text style={styles.infoTitle}>Fluxo comum depois da escolha</Text>
        <Text style={styles.infoText}>
          Login do app, configuracao do provider, autenticao, fallback de browser, captura da sprint e publicacao no backlog interno do SendSprint.
        </Text>
      </Card>
    </Screen>
  );
};

const styles = StyleSheet.create({
  pageIntro: {
    alignItems: "center",
    gap: 8,
    paddingTop: 52,
    paddingBottom: 24,
  },
  pageTitle: {
    color: theme.text,
    fontSize: 26,
    fontWeight: "800",
    textAlign: "center",
  },
  pageSubtitle: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 20,
    textAlign: "center",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
    justifyContent: "center",
  },
  providerCard: {
    width: 238,
    minHeight: 198,
    gap: 12,
    justifyContent: "space-between",
    alignItems: "center",
  },
  providerCardDisabled: {
    backgroundColor: "rgba(248,251,255,0.92)",
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    width: "100%",
  },
  infoCard: {
    marginTop: 16,
    maxWidth: 760,
    alignSelf: "center",
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
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  badgeText: {
    color: theme.primary,
    fontSize: 18,
    fontWeight: "800",
  },
  statusPill: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  statusReady: {
    backgroundColor: "rgba(30,169,124,0.12)",
  },
  statusSoon: {
    backgroundColor: "rgba(255,181,106,0.16)",
  },
  statusPillText: {
    color: theme.text,
    fontSize: 11,
    fontWeight: "800",
  },
  name: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
  desc: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 17,
    textAlign: "center",
  },
  cta: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "800",
    marginTop: "auto",
  },
  ctaDisabled: {
    color: theme.textMuted,
  },
});
