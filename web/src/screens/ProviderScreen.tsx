import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { Provider } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon, type IconName } from "../components/Icon";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Provider">;

type ProviderOption = {
  id: Provider | "github";
  name: string;
  desc: string;
  icon: IconName;
  iconColor: string;
  available: boolean;
};

const PROVIDERS: ProviderOption[] = [
  {
    id: "jira",
    name: "Jira",
    desc: "Conecte seu Jira Cloud ou Server para importar sprints e issues.",
    icon: "jira",
    iconColor: "#2684ff",
    available: true,
  },
  {
    id: "azuredevops",
    name: "Azure DevOps",
    desc: "Conecte seu Azure DevOps para importar work items e sprints.",
    icon: "azure",
    iconColor: "#0078d4",
    available: true,
  },
  {
    id: "github",
    name: "GitHub",
    desc: "Conecte seu repositório para operações de código, PRs e automações.",
    icon: "github",
    iconColor: "#0f172a",
    available: false,
  },
];

export const ProviderScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { setProvider } = useSession();
  const [selected, setSelected] = useState<Provider | "github">("azuredevops");

  const select = (id: Provider | "github") => {
    setSelected(id);
  };

  const connect = () => {
    if (selected === "github") return;
    void setProvider(selected as Provider);
    nav.navigate("Auth");
  };

  return (
    <Screen>
      <View style={styles.intro}>
        <Text style={styles.title}>Conecte seu provedor de trabalho</Text>
        <Text style={styles.subtitle}>
          Escolha a ferramenta que você usa para gerenciar sprints e issues.
        </Text>
      </View>

      <View style={styles.grid}>
        {PROVIDERS.map((provider) => {
          const isSelected = selected === provider.id;
          return (
            <Pressable
              key={provider.id}
              onPress={() => select(provider.id)}
              style={{ flex: 1, minWidth: 240 }}
            >
              <Card
                selected={isSelected}
                style={[
                  styles.card,
                  !provider.available && styles.cardDisabled,
                ] as any}
                padding={26}
              >
                <View style={styles.iconWrap}>
                  <Icon name={provider.icon} size={48} color={provider.iconColor} />
                </View>
                <Text style={styles.cardName}>{provider.name}</Text>
                <Text style={styles.cardDesc}>{provider.desc}</Text>
                <View style={styles.cardCtaWrap}>
                  <Pressable
                    onPress={() => {
                      if (provider.available) {
                        select(provider.id);
                        void setProvider(provider.id as Provider);
                        nav.navigate("Auth");
                      }
                    }}
                    disabled={!provider.available}
                    style={[
                      styles.cardCta,
                      isSelected && styles.cardCtaActive,
                      !provider.available && styles.cardCtaDisabled,
                    ]}
                  >
                    <Text
                      style={[
                        styles.cardCtaText,
                        isSelected && styles.cardCtaTextActive,
                        !provider.available && styles.cardCtaTextDisabled,
                      ]}
                    >
                      {provider.available
                        ? `Conectar ${provider.name}`
                        : "Em breve"}
                    </Text>
                  </Pressable>
                </View>
              </Card>
            </Pressable>
          );
        })}
      </View>

      <Text style={styles.footnote}>
        Você poderá conectar outros provedores depois nas Configurações.
      </Text>

      {selected !== "github" ? (
        <View style={styles.actionRow}>
          <Button title="Voltar" variant="ghost" onPress={() => nav.goBack()} />
          <Button
            title={`Continuar com ${PROVIDERS.find((p) => p.id === selected)?.name}`}
            iconRight="arrow-right"
            onPress={connect}
          />
        </View>
      ) : null}
    </Screen>
  );
};

const styles = StyleSheet.create({
  intro: {
    alignItems: "center",
    gap: 8,
    paddingTop: 28,
    paddingBottom: 22,
  },
  title: {
    color: theme.text,
    fontSize: 24,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  subtitle: {
    color: theme.textMuted,
    fontSize: 14,
    fontFamily: theme.fontSans,
    textAlign: "center",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
    justifyContent: "center",
  },
  card: {
    alignItems: "center",
    minHeight: 280,
    gap: 14,
    justifyContent: "space-between",
  },
  cardDisabled: {
    opacity: 0.6,
  },
  iconWrap: {
    width: 80,
    height: 80,
    alignItems: "center",
    justifyContent: "center",
  },
  cardName: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  cardDesc: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 19,
    fontFamily: theme.fontSans,
    textAlign: "center",
    paddingHorizontal: 6,
  },
  cardCtaWrap: {
    width: "100%",
    marginTop: 4,
  },
  cardCta: {
    paddingVertical: 11,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
  },
  cardCtaActive: {
    borderColor: theme.primary,
    backgroundColor: theme.primaryFaint,
  },
  cardCtaDisabled: {
    opacity: 0.6,
  },
  cardCtaText: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  cardCtaTextActive: {
    color: theme.primary,
  },
  cardCtaTextDisabled: {
    color: theme.textMuted,
  },
  footnote: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    textAlign: "center",
    marginTop: 18,
  },
  actionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 14,
  },
});
