import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import type {
  ProjectMode,
  ProjectSetup,
  RepositoryRegistration,
} from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Screen } from "../components/Screen";
import { ModeChoiceCard } from "../components/setup/ModeChoiceCard";
import { RepositoryForm } from "../components/setup/RepositoryForm";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "ProjectSetup">;

export const ProjectSetupScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { session, setProjectSetup } = useSession();
  const [draft, setDraft] = useState<ProjectSetup>(() =>
    ensureSetup(session.projectSetup),
  );
  const [saving, setSaving] = useState(false);

  const repositories = draft.mode === "single" ? draft.repositories.slice(0, 1) : draft.repositories;

  const setMode = (mode: ProjectMode) => {
    setDraft((current) => {
      const firstRepo = current.repositories[0] ?? createRepository();
      return {
        ...current,
        mode,
        repositories: mode === "single" ? [firstRepo] : current.repositories.length ? current.repositories : [firstRepo],
      };
    });
  };

  const updateRepository = (id: string, next: RepositoryRegistration) => {
    setDraft((current) => ({
      ...current,
      repositories: current.repositories.map((repo) => (repo.id === id ? next : repo)),
    }));
  };

  const addRepository = () => {
    setDraft((current) => ({
      ...current,
      mode: "portfolio",
      repositories: [...current.repositories, createRepository(current.repositories.length)],
    }));
  };

  const removeRepository = (id: string) => {
    setDraft((current) => {
      const repositories = current.repositories.filter((repo) => repo.id !== id);
      return {
        ...current,
        repositories: repositories.length ? repositories : [createRepository()],
      };
    });
  };

  const save = async () => {
    const nextRepositories = draft.mode === "single" ? draft.repositories.slice(0, 1) : draft.repositories;
    const invalid = nextRepositories.find((repo) => !repo.repoPath.trim());
    if (invalid) {
      Alert.alert(
        "Setup incompleto",
        "Informe ao menos um caminho local para cada repositorio registrado.",
      );
      return;
    }
    const remote = nextRepositories.find((repo) => looksRemote(repo.repoPath.trim()));
    if (remote) {
      Alert.alert(
        "Caminho invalido",
        "URLs remotas nao destravam a execucao. Use o caminho local do checkout do repositorio.",
      );
      return;
    }

    setSaving(true);
    try {
      await setProjectSetup({
        ...draft,
        repositories: nextRepositories.map(cleanRepository),
      });
      Alert.alert("Setup salvo", "A configuracao local foi atualizada sem armazenar segredos.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScreenLayout
      onBack={() => nav.navigate("Dashboard")}
      onSave={save}
      saving={saving}
    >
      <Card style={styles.notice}>
        <Text style={styles.noticeLabel}>LOCAL-FIRST SETUP</Text>
        <Text style={styles.noticeTitle}>Modele como o SendSprint deve abrir branches, commits e gates.</Text>
        <Text style={styles.noticeText}>
          Esta tela salva apenas metadados nao secretos no navegador: portfolio,
          repositorios, papeis, projetos, padroes globais e comandos. Tokens, PATs e API keys continuam
          indo direto para o backend local e keyring do sistema.
        </Text>
        <Text style={styles.noticeText}>
          Para liberar play por task, use caminhos locais reais. URLs remotas servem apenas como
          referencia e nao destravam a execucao.
        </Text>
      </Card>

      <Text style={styles.section}>PORTFOLIO RULES</Text>
      <Card style={styles.rulesCard}>
        <Input
          label="Branch pattern"
          value={draft.branchPattern}
          onChangeText={(branchPattern) => setDraft((current) => ({ ...current, branchPattern }))}
          placeholder="feature/{item_key}-{slug}"
          autoCapitalize="none"
          monospace
        />
        <Input
          label="Commit pattern"
          value={draft.commitPattern}
          onChangeText={(commitPattern) => setDraft((current) => ({ ...current, commitPattern }))}
          placeholder="{type}: {summary}"
          autoCapitalize="none"
          monospace
        />
        <Input
          label="Deploy target branch"
          value={draft.deployTargetBranch}
          onChangeText={(deployTargetBranch) => setDraft((current) => ({ ...current, deployTargetBranch }))}
          placeholder="dev"
          autoCapitalize="none"
          monospace
        />
        <Text style={styles.sectionHint}>
          Esses tres campos sao definidos uma vez no portfolio e todos os repositorios respeitam a mesma configuracao geral.
        </Text>
      </Card>

      <Text style={styles.section}>DELIVERY MODE</Text>
      <View style={styles.modeGrid}>
        <ModeChoiceCard
          mode="single"
          selected={draft.mode === "single"}
          title="Single project"
          description="Um repositorio principal recebe o trabalho da sprint."
          meta="1 repo active"
          onPress={() => setMode("single")}
        />
        <ModeChoiceCard
          mode="portfolio"
          selected={draft.mode === "portfolio"}
          title="Portfolio"
          description="Varios repositorios participam com papeis e gates proprios."
          meta={`${draft.repositories.length} repos registered`}
          onPress={() => setMode("portfolio")}
        />
      </View>

      <View style={styles.sectionRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.section}>REPOSITORIES</Text>
          <Text style={styles.sectionHint}>
            {draft.mode === "single"
              ? "Single-project mode usa somente o primeiro repositorio."
              : "Portfolio mode permite um mapa por projeto, papel e validacao. Branch, commit e deploy seguem o portfolio."}
          </Text>
        </View>
        {draft.mode === "portfolio" ? (
          <Button title="Add repo" variant="secondary" onPress={addRepository} />
        ) : null}
      </View>

      {repositories.map((repository, index) => (
        <RepositoryForm
          key={repository.id}
          repository={repository}
          index={index}
          canRemove={draft.mode === "portfolio" && draft.repositories.length > 1}
          onChange={(next) => updateRepository(repository.id, next)}
          onRemove={() => removeRepository(repository.id)}
        />
      ))}

      <Card style={styles.summary}>
        <Text style={styles.summaryLabel}>CURRENT ROUTING</Text>
        <Text style={styles.summaryText}>
          Mode: {draft.mode} | Repos active: {repositories.length} | Saved:{" "}
          {session.projectSetup.updatedAt
            ? new Date(session.projectSetup.updatedAt).toLocaleString()
            : "not yet"}
        </Text>
      </Card>
    </ScreenLayout>
  );
};

const ScreenLayout: React.FC<{
  children: React.ReactNode;
  onBack: () => void;
  onSave: () => void;
  saving: boolean;
}> = ({ children, onBack, onSave, saving }) => {
  return (
    <Screen
      chrome="app"
      eyebrow="Web 11 · Project Setup"
      title="Configuracao do projeto"
      subtitle="Escolha single-project ou portfolio e registre os repositorios que o run loop deve considerar."
      footer={
        <View style={{ gap: 10 }}>
          <Button title="Save setup" onPress={onSave} loading={saving} />
          <Button title="Back to dashboard" variant="secondary" onPress={onBack} />
        </View>
      }
    >
      {children}
    </Screen>
  );
};

const ensureSetup = (setup: ProjectSetup): ProjectSetup => {
  const repositories = setup.repositories.length ? setup.repositories : [createRepository()];
  return {
    ...setup,
    branchPattern: setup.branchPattern?.trim() || "feature/{item_key}-{slug}",
    commitPattern: setup.commitPattern?.trim() || "{type}: {summary}",
    deployTargetBranch: setup.deployTargetBranch?.trim() || "dev",
    repositories: setup.mode === "single" ? repositories.slice(0, 1) : repositories,
  };
};

const createRepository = (index = 0): RepositoryRegistration => ({
  id: `repo-${Date.now().toString(36)}-${index}`,
  name: "",
  repoPath: "",
  role: index === 0 ? "fullstack" : "backend",
  project: "",
  validationCommands: ["npm run typecheck", "npm test"],
});

const cleanRepository = (repo: RepositoryRegistration): RepositoryRegistration => ({
  ...repo,
  name: repo.name.trim() || repo.repoPath.trim().split(/[\\/]/).filter(Boolean).pop() || "repo",
  repoPath: repo.repoPath.trim(),
  project: repo.project.trim(),
  validationCommands: repo.validationCommands.map((cmd) => cmd.trim()).filter(Boolean),
});

const looksRemote = (repoPath: string): boolean =>
  repoPath.startsWith("http://") ||
  repoPath.startsWith("https://") ||
  repoPath.startsWith("git@") ||
  repoPath.startsWith("ssh://");

const styles = StyleSheet.create({
  notice: {
    backgroundColor: "#f1f7ff",
  },
  noticeLabel: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  noticeTitle: {
    color: theme.text,
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "800",
    marginTop: 4,
  },
  noticeText: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 4,
  },
  section: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  modeGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  rulesCard: {
    gap: 12,
  },
  sectionRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    marginTop: 8,
  },
  sectionHint: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 4,
  },
  summary: {
    backgroundColor: "rgba(30,169,124,0.08)",
    borderColor: "rgba(30,169,124,0.2)",
  },
  summaryLabel: {
    color: theme.success,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  summaryText: {
    color: theme.text,
    fontFamily: theme.fontMono,
    fontSize: 12,
    lineHeight: 18,
  },
});
