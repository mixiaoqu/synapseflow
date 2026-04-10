import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "企业知识库系统",
  description: "企业知识管理与智能问答工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full overflow-hidden">
      <body className={`${inter.className} h-full overflow-hidden`}>{children}</body>
    </html>
  );
}
