"use client";

import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  Eye,
  EyeOff,
  Loader2,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authApi } from "@/lib/api/endpoints/auth";
import { getAccessToken, setAuthSession } from "@/lib/auth/session";

const features = [
  {
    icon: BookOpen,
    title: "统一知识管理",
    desc: "文档入库、审核发布、问答检索，全链路闭环",
  },
  {
    icon: ShieldCheck,
    title: "细粒度权限控制",
    desc: "团队隔离、角色分级，操作记录可审计",
  },
  {
    icon: Sparkles,
    title: "智能问答检索",
    desc: "语义理解答案，敏感词兜底，内容质量可控",
  },
];

function LoginForm({
  nextPath,
}: {
  nextPath: string;
}) {
  const router = useRouter();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!identity.trim() || !password.trim() || loading) return;

    setLoading(true);
    try {
      const response = await authApi.login({
        username_or_email: identity.trim(),
        password,
      });
      setAuthSession(response.access_token, response.user);
      toast.success(`欢迎回来，${response.user.username}`);
      router.replace(nextPath);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-2.5">
        <label htmlFor="login-identity" className="text-sm font-medium text-zinc-300">
          用户名或邮箱
        </label>
        <div className="group relative">
          <UserRound
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 transition-colors group-hover:text-zinc-300 group-focus-within:text-blue-400"
            aria-hidden
          />
          <Input
            id="login-identity"
            value={identity}
            onChange={(event) => setIdentity(event.target.value)}
            placeholder="输入用户名或邮箱"
            autoComplete="username"
            disabled={loading}
            className="h-11 rounded-xl border-white/10 bg-white/[0.05] pl-10 text-zinc-100 placeholder:text-zinc-500 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition-all hover:border-white/15 hover:bg-white/[0.07] focus-visible:border-blue-400/40 focus-visible:bg-white/[0.08] focus-visible:ring-4 focus-visible:ring-blue-500/10"
          />
        </div>
      </div>

      <div className="space-y-2.5">
        <label htmlFor="login-password" className="text-sm font-medium text-zinc-300">
          密码
        </label>
        <div className="group relative">
          <LockKeyhole
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 transition-colors group-hover:text-zinc-300 group-focus-within:text-blue-400"
            aria-hidden
          />
          <Input
            id="login-password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="输入密码"
            autoComplete="current-password"
            disabled={loading}
            className="h-11 rounded-xl border-white/10 bg-white/[0.05] pl-10 pr-12 text-zinc-100 placeholder:text-zinc-500 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition-all hover:border-white/15 hover:bg-white/[0.07] focus-visible:border-blue-400/40 focus-visible:bg-white/[0.08] focus-visible:ring-4 focus-visible:ring-blue-500/10"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-white/[0.08] hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/30"
            aria-label={showPassword ? "隐藏密码" : "显示密码"}
          >
            {showPassword ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      <Button
        type="submit"
        disabled={loading || !identity.trim() || !password.trim()}
        aria-busy={loading}
        className="h-11 w-full rounded-xl bg-blue-500 font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:bg-blue-400 hover:-translate-y-px hover:shadow-blue-500/30 active:translate-y-0 disabled:opacity-50 disabled:shadow-none"
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            登录中...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            进入工作台
            <ArrowRight className="h-4 w-4" />
          </span>
        )}
      </Button>

      <p className="text-center text-xs text-zinc-500">
        继续操作即表示你将以已认证用户身份访问知识问答与后台管理能力
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-[#080c14] text-zinc-100">
          <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
        </main>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const searchParams = useSearchParams();
  const nextPath = useMemo(() => searchParams.get("next") || "/admin", [searchParams]);

  useEffect(() => {
    if (getAccessToken()) {
      window.location.replace(nextPath);
    }
  }, [nextPath]);

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#080c14] text-zinc-100">
      <Toaster position="top-center" richColors theme="dark" />

      {/* Subtle background gradient */}
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(59,130,246,0.15),transparent)]" />
        <div className="absolute left-0 top-0 h-[500px] w-[500px] rounded-full bg-blue-500/[0.03] blur-[120px]" />
        <div className="absolute bottom-0 right-0 h-[400px] w-[400px] rounded-full bg-indigo-500/[0.03] blur-[120px]" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col lg:flex-row">
        {/* Left: branding & features */}
        <aside className="order-2 flex flex-col justify-center px-8 py-14 lg:order-1 lg:w-1/2 lg:px-12 lg:py-20">
          <div className="max-w-md">
            {/* Brand */}
            <div className="mb-12">
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-300">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-60 animate-ping" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
                </span>
                企业知识库系统
              </div>
            </div>

            <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              欢迎回来
            </h1>
            <p className="hidden">
              同一账户体系，终端问答与后台管理一体化。登录后自动根据权限进入对应工作台。
            </p>
            <p className="mt-4 text-base leading-7 text-zinc-400">
              使用你的账号登录，继续访问知识库与管理功能。
            </p>

            {/* Features */}
            <ul className="mt-10 space-y-4">
              {features.map(({ icon: Icon, title, desc }) => (
                <li key={title} className="flex items-start gap-4">
                  <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-white/[0.04] text-blue-400">
                    <Icon className="h-4 w-4" aria-hidden />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-200">{title}</p>
                    <p className="mt-0.5 text-xs text-zinc-500 leading-relaxed">{desc}</p>
                  </div>
                </li>
              ))}
            </ul>

            <p className="mt-12 text-xs text-zinc-600">
              LangChain RAG 知识库 · Enterprise Knowledge Base · 2026
            </p>
          </div>
        </aside>

        {/* Right: login form */}
        <section className="order-1 flex flex-1 items-center justify-center px-6 py-12 lg:order-2 lg:px-12 lg:py-20">
          <div className="w-full max-w-[400px]">
            {/* Card */}
            <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03] p-8 shadow-2xl shadow-black/30 ring-1 ring-white/5 backdrop-blur-md">
              {/* Top accent line */}
              <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent" />

              <div className="relative">
                <h2 className="text-2xl font-semibold text-white">登录</h2>
                <p className="mt-1.5 text-sm text-zinc-400">
                  输入账号密码后进入工作台
                </p>

                <div className="mt-8">
                  <LoginForm nextPath={nextPath} />
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
