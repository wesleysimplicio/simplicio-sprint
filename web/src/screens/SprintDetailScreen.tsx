import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import type { RunMode, SprintItem, SprintDetail } from "../api/types";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "SprintDetail">;
type Rt = RouteProp<RootStackParamList, "SprintDetail">;

const MODES: { id: RunMode; label: string; desc: string; emoji: string }[] = [
  { id: "all", label: "Sprint inteira", desc: "Roda todos os itens", emoji: "🌐" },
  { id: "mine", label: "Só meus", desc: "Filtra pelo usuário autenticado", emoji: "👤" },
  { id: "selected", label: "Itens escolhidos", desc: "Marque abaixo", emoji: "🎯" },
];

export const SprintDetailScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const route = useRoute<Rt>();
  const { api, session } = useSession();

  const [detail, setDetail] = useState<SprintDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<RunMode>("all");
  const [picked, setPicked] = useState<Set<string>>(new Set());

  useEffect(() => {
    (async () => {
      try {
        const d = await api.getSprint(route.params.sprintId, session.provider ?? "jira");
        setDetail(d);
      } catch (e) {
        Alert.alert("Falha", String((e as Error).message ?? e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const items = detail?.items ?? [];
  const visibleItems = useMemo<SprintItem[]>(() => {
    if (mode !== "mine" || !session.account) return items;
    return items.filter((i) =>
      [i.assignee, i.assignee_email].some(
        (x) => x && session.account && x.toLowerCase().includes(String(session.account).toLowerCase()),
      ),
    );
  }, [items, mode, session.account]);

  const toggle = (key: string) => {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const start = () => {
    const keys = mode === "selected" ? Array.from(picked) : [];
    if (mode === "selected" && keys.length === 0) {
      Alert.alert("Selecione ao menos 1 item");
      return;
    }
    nav.navigate("Run", { sprintId: route.params.sprintId, mode, itemKeys: keys });
  };

  if (loading) {
    return (
      <Screen title="Carregando…">
        <ActivityIndicator color={theme.primary} />
      </Screen>
    );
  }

  return (
    <Screen
      title={detail?.sprint.name ?? "Sprint"}
      subtitle={
        detail?.sprint.goal
          ? `"${detail.sprint.goal}" · ${visibleItems.length} item(s)`
          : `${visibleItems.length} item(s)`
      }
      footer={
        <Button
          title={mode === "selected" ? `Iniciar com ${picked.size} item(s)` : "Iniciar entrega"}
          onPress={start}
          icon="▶"
        />
      }
    >
      <Text style={styles.section}>MODO</Text>
      <View style={{ gap: 10 }}>
        {MODES.map((m) => (
          <Card key={m.id} onPress={() => setMode(m.id)} selected={mode === m.id}>
            <View style={styles.modeRow}>
              <Text style={styles.modeEmoji}>{m.emoji}</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.modeLabel}>{m.label}</Text>
                <Text style={styles.modeDesc}>{m.desc}</Text>
              </View>
              {mode === m.id ? <Text style={styles.check}>✓</Text> : null}
            </View>
          </Card>
        ))}
      </View>

      <Text style={[styles.section, { marginTop: 14 }]}>
        ITENS{mode === "mine" ? " · FILTRADOS POR VOCÊ" : ""}
      </Text>
      {visibleItems.map((it) => {
        const selectable = mode === "selected";
        const isPicked = picked.has(it.key);
        return (
          <Pressable
            key={it.id}
            onPress={() => selectable && toggle(it.key)}
            style={({ pressed }) => [styles.item, isPicked && styles.itemPicked, pressed && { opacity: 0.85 }]}
          >
            <View style={styles.itemHead}>
              <Text style={styles.itemKey}>{it.key}</Text>
              <View style={[styles.typeBadge, typeColor(it.type)]}>
                <Text style={styles.typeText}>{it.type}</Text>
              </View>
              <View style={{ flex: 1 }} />
              {selectable ? (
                <View style={[styles.cb, isPicked && styles.cbOn]}>
                  {isPicked ? <Text style={styles.cbCheck}>✓</Text> : null}
                </View>
              ) : null}
            </View>
            <Text style={styles.itemTitle}>{it.title}</Text>
            <View style={styles.itemMeta}>
              <Text style={styles.metaText}>📌 {it.status}</Text>
              {it.assignee ? <Text style={styles.metaText}>👤 {it.assignee}</Text> : null}
              {it.story_points != null ? (
                <Text style={styles.metaText}>⚡ {it.story_points} sp</Text>
              ) : null}
            </View>
          </Pressable>
        );
      })}
    </Screen>
  );
};

const typeColor = (t: string) => {
  const map: Record<string, { backgroundColor: string }> = {
    Story: { backgroundColor: "rgba(34, 211, 238, 0.18)" },
    Task: { backgroundColor: "rgba(124, 92, 255, 0.18)" },
    Bug: { backgroundColor: "rgba(248, 113, 113, 0.18)" },
    Epic: { backgroundColor: "rgba(255, 138, 61, 0.18)" },
  };
  return map[t] ?? { backgroundColor: "rgba(154, 163, 199, 0.18)" };
};

const styles = StyleSheet.create({
  section: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    marginTop: 6,
  },
  modeRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  modeEmoji: { fontSize: 22 },
  modeLabel: { color: theme.text, fontSize: 16, fontWeight: "700" },
  modeDesc: { color: theme.textMuted, fontSize: 12, marginTop: 2 },
  check: { color: theme.primary, fontSize: 22, fontWeight: "700" },
  item: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    borderWidth: 1,
    borderColor: theme.border,
    marginTop: 8,
    gap: 6,
  },
  itemPicked: { borderColor: theme.primary },
  itemHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  itemKey: { color: theme.primarySoft, fontFamily: theme.fontMono, fontSize: 13 },
  typeBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999 },
  typeText: { color: theme.text, fontSize: 11, fontWeight: "700" },
  itemTitle: { color: theme.text, fontSize: 15, fontWeight: "600" },
  itemMeta: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 4 },
  metaText: { color: theme.textMuted, fontSize: 12 },
  cb: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
  },
  cbOn: { backgroundColor: theme.primary, borderColor: theme.primary },
  cbCheck: { color: "white", fontSize: 16, fontWeight: "800" },
});
