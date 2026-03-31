export interface SseEnvelope<TData = Record<string, unknown>> {
  type: string;
  data: TData;
}

export function parseSseBlock(block: string): SseEnvelope | null {
  const match = block.match(/event:\s*\w+\ndata:\s*(.+)/s);
  if (!match) return null;

  let raw = match[1].trim();
  if (raw.endsWith("\n")) {
    raw = raw.replace(/\n+$/, "");
  }

  try {
    const parsed = JSON.parse(raw) as SseEnvelope;
    if (
      typeof parsed.type === "string" &&
      parsed.data &&
      typeof parsed.data === "object"
    ) {
      return parsed;
    }
  } catch {
    return null;
  }

  return null;
}

export async function consumeSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: SseEnvelope) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const block of parts) {
      if (!block.trim()) continue;
      const event = parseSseBlock(block);
      if (event) onEvent(event);
    }
  }
}
