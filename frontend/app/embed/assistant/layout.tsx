export default function EmbedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="w-full h-[100dvh] overflow-hidden bg-background">
      {children}
    </div>
  );
}
