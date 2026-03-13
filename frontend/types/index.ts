export interface Agent {
  id: string;
  name: string;
  status: "idle" | "processing" | "completed" | "error";
  progress?: number;
}

export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: Date;
}

export interface StreamEvent {
  node: string;
  status: string;
  data?: any;
}
