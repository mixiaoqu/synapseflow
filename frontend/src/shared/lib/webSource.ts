/** 只将网页来源的绝对 HTTP(S) URL 渲染为链接。 */
export function getWebSource(doc: Record<string, unknown>) {
  const metadata = doc.metadata;
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) return null;
  const source = metadata as Record<string, unknown>;
  if (source.source_type !== "web" || typeof source.url !== "string") return null;
  if (/[\s\\]/.test(source.url)) return null;
  try {
    const url = new URL(source.url);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    return {
      url: url.href,
      title: typeof source.title === "string" && source.title.trim() ? source.title.trim() : url.hostname,
      fetchedAt: typeof source.fetched_at === "string" ? source.fetched_at : "",
    };
  } catch {
    return null;
  }
}
