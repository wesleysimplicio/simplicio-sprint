import AsyncStorage from "@react-native-async-storage/async-storage";

export const SUPPORT_STORAGE_KEY = "sendsprint.support-center.v1";

export type SupportTicketStatus = "new" | "triaged" | "backlog_candidate" | "resolved";
export type SupportTicketCategory =
  | "bug"
  | "integration"
  | "billing"
  | "feature"
  | "workflow"
  | "question";

export type SupportTicket = {
  id: string;
  category: SupportTicketCategory;
  status: SupportTicketStatus;
  title: string;
  description: string;
  linkedRunId?: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  backlogReason?: string | null;
  diagnostics: {
    provider?: string | null;
    sprintId?: string | null;
    sprintName?: string | null;
    repoCount: number;
    runCount: number;
  };
};

export const loadSupportTickets = async (): Promise<SupportTicket[]> => {
  const raw = await AsyncStorage.getItem(SUPPORT_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as SupportTicket[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

export const saveSupportTickets = async (tickets: SupportTicket[]): Promise<void> => {
  await AsyncStorage.setItem(SUPPORT_STORAGE_KEY, JSON.stringify(tickets));
};
