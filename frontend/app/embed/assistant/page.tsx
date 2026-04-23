"use client";

import { EmbedAssistantChat } from "@/features/embed/components/EmbedAssistantChat";
import { Suspense } from "react";

export default function EmbedAssistantPage() {
  return (
    <Suspense fallback={<div className="w-full h-full flex items-center justify-center">Loading...</div>}>
      <EmbedAssistantChat />
    </Suspense>
  );
}
