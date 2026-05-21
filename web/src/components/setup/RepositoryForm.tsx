import React from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { RepositoryRegistration, RepositoryRole } from "../../api/types";
import { Button } from "../Button";
import { Card } from "../Card";
import { Input } from "../Input";
import { theme } from "../../theme";

type Props = {
  repository: RepositoryRegistration;
  index: number;
  canRemove: boolean;
  onChange: (repository: RepositoryRegistration) => void;
  onRemove: () => void;
};

const ROLE_OPTIONS: Array<{ id: RepositoryRole; label: string }> = [
  { id: "frontend", label: "Frontend" },
  { id: "backend", label: "Backend" },
  { id: "fullstack", label: "Fullstack" },
  { id: "mobile", label: "Mobile" },
  { id: "infra", label: "Infra" },
  { id: "docs", label: "Docs" },
  { id: "shared", label: "Shared" },
  { id: "other", label: "Other" },
];

export const RepositoryForm: React.FC<Props> = ({
  repository,
  index,
  canRemove,
  onChange,
  onRemove,
}) => {
  const patch = (next: Partial<RepositoryRegistration>) => {
    onChange({ ...repository, ...next });
  };

  return (
    <Card style={styles.card}>
      <View style={styles.header}>
        <View>
          <Text style={styles.kicker}>REPOSITORY {index + 1}</Text>
          <Text style={styles.title}>{repository.name || fallbackRepositoryTitle(repository.repoPath)}</Text>
        </View>
        {canRemove ? <Button title="Remove" variant="ghost" onPress={onRemove} /> : null}
      </View>

      <Input
        label="Repository name"
        value={repository.name}
        onChangeText={(name) => patch({ name })}
        placeholder="web-app"
        autoCapitalize="none"
      />

      <Input
        label="Local repository path"
        value={repository.repoPath}
        onChangeText={(repoPath) => patch({ repoPath })}
        placeholder="C:/workspace/web-app"
        autoCapitalize="none"
        keyboardType="url"
        monospace
      />
      {looksRemote(repository.repoPath.trim()) ? (
        <Text style={styles.help}>Remote URLs nao liberam execucao. Use um checkout local.</Text>
      ) : null}

      <View style={styles.field}>
        <Text style={styles.label}>Role</Text>
        <View style={styles.roleGrid}>
          {ROLE_OPTIONS.map((role) => {
            const selected = repository.role === role.id;
            return (
              <Pressable
                key={role.id}
                onPress={() => patch({ role: role.id })}
                style={({ pressed }) => [
                  styles.roleChip,
                  selected && styles.roleChipSelected,
                  pressed && { opacity: 0.82 },
                ]}
              >
                <Text style={[styles.roleText, selected && styles.roleTextSelected]}>
                  {role.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <Input
        label="Project"
        value={repository.project}
        onChangeText={(project) => patch({ project })}
        placeholder="Payments, Platform, Mobile App"
        autoCapitalize="words"
      />
      <View style={styles.field}>
        <Text style={styles.label}>Validation commands</Text>
        <TextInput
          value={repository.validationCommands.join("\n")}
          onChangeText={(text) => patch({ validationCommands: parseCommands(text) })}
          placeholder={"npm run typecheck\nnpm test\npytest tests/ -v"}
          placeholderTextColor={theme.textMuted}
          multiline
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.textArea}
        />
        <Text style={styles.help}>One command per line. Store commands only, never tokens or PATs.</Text>
      </View>
    </Card>
  );
};

const parseCommands = (text: string): string[] =>
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

const fallbackRepositoryTitle = (repoPath: string): string => {
  const normalized = repoPath.replace(/\\/g, "/").trim();
  if (!normalized) return "New repository";
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] || "New repository";
};

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

const styles = StyleSheet.create({
  card: {
    gap: 14,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  kicker: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  title: {
    color: theme.text,
    fontSize: 20,
    fontWeight: "800",
    marginTop: 4,
  },
  field: {
    gap: 7,
  },
  label: {
    color: theme.textMuted,
    fontSize: 12,
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  roleGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  roleChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  roleChipSelected: {
    backgroundColor: "rgba(44,107,237,0.12)",
    borderColor: theme.primary,
  },
  roleText: {
    color: theme.textMuted,
    fontWeight: "700",
    fontSize: 12,
  },
  roleTextSelected: {
    color: theme.primary,
  },
  textArea: {
    minHeight: 118,
    backgroundColor: theme.surface,
    color: theme.text,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    lineHeight: 20,
    fontFamily: theme.fontMono,
    textAlignVertical: "top",
  },
  help: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
  },
});
