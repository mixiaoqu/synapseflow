export interface SseEnvelope<TData = Record<string, unknown>> {
  type: string;
  data: TData;
  workflow_id?: string | null;
  node_id?: string;
  node_name?: string;
  timestamp?: number;
  run_id?: string | null;
}

function extractDataLine(block: string): string | null {
  const lines = block.split(/\r?\n/);
  const dataLines = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""));

  if (dataLines.length === 0) {
    return null;
  }

  return dataLines.join("\n").trim();
}

export function parseSseBlock(block: string): SseEnvelope | null {
  const raw = extractDataLine(block);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as SseEnvelope;
    if (
      typeof parsed.type === "string" &&
      parsed.data !== null &&
      typeof parsed.data === "object" &&
      !Array.isArray(parsed.data)
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
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() || "";

    for (const block of parts) {
      if (!block.trim()) {
        continue;
      }
      const event = parseSseBlock(block);
      if (event) {
        onEvent(event);
      }
    }
  }

  const trailing = buffer.trim();
  if (!trailing) {
    return;
  }

  const event = parseSseBlock(trailing);
  if (event) {
    onEvent(event);
  }
}
