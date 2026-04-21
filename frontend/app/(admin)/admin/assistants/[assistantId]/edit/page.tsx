"use client";

import { useParams } from "next/navigation";

import { AssistantWorkbench } from "@/components/admin/assistants/AssistantWorkbench";

export default function AssistantEditPage() {
  const params = useParams<{ assistantId: string }>();
  const assistantId = Number(params.assistantId);

  return <AssistantWorkbench mode="edit" assistantId={assistantId} />;
}
