"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  Brain,
  Eye,
  EyeOff,
  Layers,
  Loader2,
  LockKeyhole,
  Shield,
  UserRound,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authApi } from "@/lib/api/endpoints/auth";
import { getAccessToken, setAuthSession } from "@/lib/auth/session";

const highlights = [
  {
    icon: Layers,
    text: "文档与知识库按账号归属，数据边界清晰。",
  },
  {
    icon: Brain,
    text: "问答与治理在已认证身份下执行，检索更可信。",
  },
  {
    icon: Shield,
    text: "采用 Bearer Token 会话，替代共享式开发态。",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const nextPath = useMemo(
    () => searchParams.get("next") || "/kb-chat",
    [searchParams],
  );

  useEffect(() => {
    if (getAccessToken()) {
      router.replace(nextPath);
    }
  }, [nextPath, router]);

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
    <main
      className="relative min-h-screen overflow-x-hidden bg-[#050816] text-zinc-100 selection:bg-emerald-500/30"
      aria-label="登录"
    >
      <Toaster position="top-center" richColors theme="dark" />

      <div
        className="pointer-events-none absolute inset-0 overflow-hidden"
        aria-hidden
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.12),transparent_32%),radial-gradient(circle_at_85%_18%,rgba(45,212,191,0.08),transparent_24%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_28%,rgba(255,255,255,0.01))]" />
        <div className="absolute -left-[12%] top-[-18%] h-[38rem] w-[38rem] rounded-full bg-emerald-400/10 blur-[170px]" />
        <div className="absolute bottom-[-24%] right-[-10%] h-[34rem] w-[34rem] rounded-full bg-cyan-400/10 blur-[180px]" />
        <div className="absolute left-[48%] top-[18%] h-[24rem] w-[24rem] -translate-x-1/2 rounded-full bg-amber-300/[0.05] blur-[140px]" />
        <div
          className="absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgba(255,255,255,0.75) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.75) 1px, transparent 1px)",
            backgroundSize: "72px 72px",
            maskImage:
              "radial-gradient(ellipse 92% 74% at 50% 44%, black 12%, rgba(0,0,0,0.85) 38%, transparent 78%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 92% 74% at 50% 44%, black 12%, rgba(0,0,0,0.85) 38%, transparent 78%)",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col lg:flex-row">
        <aside className="order-2 flex flex-col justify-between px-6 py-10 lg:order-1 lg:w-1/2 lg:px-12 lg:py-20 xl:px-20 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-8 motion-safe:duration-700">
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/15 bg-white/[0.04] px-3.5 py-1.5 text-xs font-medium text-emerald-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-md">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-70" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
              SynapseFlow Platform
            </div>

            <h1 className="mt-8 text-5xl font-semibold tracking-[-0.04em] text-white sm:text-6xl lg:text-[4.5rem] lg:leading-[0.95]">
              知识工作台
            </h1>
            <p className="mt-6 max-w-lg text-base leading-8 text-zinc-400 sm:text-[1.05rem]">
              使用个人身份登录后，文档、知识库与智能问答均在当前用户范围内进行，与默认共享账号彻底分离，保障数据安全与隐私边界。
            </p>

            <ul className="mt-12 space-y-4">
              {highlights.map(({ icon: Icon, text }, index) => (
                <li
                  key={text}
                  className="group flex items-start gap-4 rounded-[1.75rem] border border-white/[0.06] bg-white/[0.035] px-4 py-4 shadow-[0_20px_50px_-40px_rgba(0,0,0,0.75)] backdrop-blur-sm transition-all duration-300 hover:border-white/[0.1] hover:bg-white/[0.05] hover:shadow-[0_30px_80px_-45px_rgba(16,185,129,0.6)] motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-4 motion-safe:duration-700"
                  style={{ animationDelay: `${160 + index * 120}ms` }}
                >
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br from-emerald-400/15 via-emerald-400/[0.08] to-white/[0.03] text-emerald-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition-all duration-300 group-hover:scale-105 group-hover:border-emerald-300/20 group-hover:text-emerald-200">
                    <Icon className="h-5 w-5" aria-hidden />
                  </div>
                  <div className="pt-1">
                    <p className="text-sm font-medium leading-7 text-zinc-300 transition-colors duration-300 group-hover:text-zinc-100">
                      {text}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-16 flex items-center gap-4 text-xs font-medium text-zinc-500 lg:mt-auto">
            <span>v0.1.0 Beta</span>
            <span className="h-1 w-1 rounded-full bg-zinc-700" />
            <span>2026</span>
          </div>
        </aside>

        <section className="order-1 flex flex-1 items-center justify-center px-4 py-12 sm:px-8 lg:py-20 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-8 motion-safe:duration-700 motion-safe:delay-150">
          <div className="w-full max-w-[440px]">
            <div className="mb-8 lg:hidden motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-4 motion-safe:duration-700 motion-safe:delay-100">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/15 bg-white/[0.04] px-3.5 py-1.5 text-xs font-medium text-emerald-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-md">
                SynapseFlow
              </div>
              <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white">
                登录以继续
              </h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">
                进入你的工作空间，继续处理文档与知识任务。
              </p>
            </div>

            <div className="relative overflow-hidden rounded-[2rem] border border-white/[0.08] bg-white/[0.045] p-8 shadow-2xl shadow-black/50 backdrop-blur-xl ring-1 ring-white/5 sm:p-10">
              <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),transparent_24%,transparent_70%,rgba(255,255,255,0.03))]" />
              <div className="absolute inset-[1px] rounded-[calc(2rem-1px)] bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.08),transparent_34%)]" />
              <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-emerald-300/30 to-transparent" />

              <div className="relative">
                <div className="mb-8 hidden lg:block">
                  <p className="text-sm font-medium uppercase tracking-[0.24em] text-zinc-500">
                    Welcome Back
                  </p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">
                    登录
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-400">
                    输入您的凭据以访问工作台。
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="space-y-2.5">
                    <label
                      htmlFor="login-identity"
                      className="text-sm font-medium text-zinc-300"
                    >
                      账号
                    </label>
                    <div className="group relative">
                      <UserRound
                        className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 transition-colors duration-300 group-hover:text-zinc-300 group-focus-within:text-emerald-300"
                        aria-hidden
                      />
                      <Input
                        id="login-identity"
                        value={identity}
                        onChange={(e) => setIdentity(e.target.value)}
                        placeholder="用户名或邮箱"
                        autoComplete="username"
                        disabled={loading}
                        className="h-12 rounded-2xl border-white/10 bg-white/[0.04] pl-10 text-zinc-100 placeholder:text-zinc-500 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300 hover:border-white/15 hover:bg-white/[0.06] focus-visible:border-emerald-400/35 focus-visible:bg-white/[0.07] focus-visible:ring-4 focus-visible:ring-emerald-500/10"
                      />
                    </div>
                  </div>

                  <div className="space-y-2.5">
                    <label
                      htmlFor="login-password"
                      className="text-sm font-medium text-zinc-300"
                    >
                      密码
                    </label>
                    <div className="group relative">
                      <LockKeyhole
                        className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 transition-colors duration-300 group-hover:text-zinc-300 group-focus-within:text-emerald-300"
                        aria-hidden
                      />
                      <Input
                        id="login-password"
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        autoComplete="current-password"
                        disabled={loading}
                        className="h-12 rounded-2xl border-white/10 bg-white/[0.04] pl-10 pr-14 text-zinc-100 placeholder:text-zinc-500 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300 hover:border-white/15 hover:bg-white/[0.06] focus-visible:border-emerald-400/35 focus-visible:bg-white/[0.07] focus-visible:ring-4 focus-visible:ring-emerald-500/10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((value) => !value)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-2.5 text-zinc-500 transition-all duration-300 hover:bg-white/[0.08] hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/30 active:scale-95"
                        aria-label={showPassword ? "隐藏密码" : "显示密码"}
                        aria-pressed={showPassword}
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
                    className="group relative h-12 w-full overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-500 via-emerald-500 to-teal-500 text-sm font-semibold text-white shadow-[0_16px_40px_-18px_rgba(16,185,129,0.95)] transition-all duration-300 hover:-translate-y-0.5 hover:brightness-110 hover:shadow-[0_22px_60px_-20px_rgba(16,185,129,1)] focus-visible:ring-emerald-300/30 disabled:shadow-none motion-safe:active:scale-[0.985]"
                  >
                    <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.18),transparent_40%)]" />
                    <div className="absolute inset-0 flex h-full w-full justify-center [transform:skew(-16deg)_translateX(-170%)] transition-transform duration-1000 group-hover:[transform:skew(-16deg)_translateX(170%)]">
                      <div className="relative h-full w-10 bg-white/25 blur-[2px]" />
                    </div>
                    <span className="relative flex items-center gap-2">
                      {loading ? (
                        <>
                          <Loader2
                            className="h-4 w-4 animate-spin"
                            aria-hidden
                          />
                          正在登录...
                        </>
                      ) : (
                        <>
                          进入工作台
                          <ArrowRight
                            className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1"
                            aria-hidden
                          />
                        </>
                      )}
                    </span>
                  </Button>
                </form>

                <div className="mt-8 rounded-2xl border border-white/[0.08] bg-black/20 p-1 ring-1 ring-white/5 backdrop-blur-sm">
                  <details className="group rounded-[calc(1rem-1px)] bg-white/[0.02] p-4 transition-colors duration-300 open:bg-white/[0.03]">
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium text-zinc-300 transition-colors duration-300 hover:text-white marker:content-none [&::-webkit-details-marker]:hidden">
                      <span className="flex items-center gap-3">
                        <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-amber-400/15 bg-amber-300/[0.08] text-amber-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
                          <Shield className="h-4 w-4" />
                        </span>
                        <span>
                          默认管理员账号
                          <span className="block text-xs font-normal text-zinc-500">
                            仅用于首次部署后的初始化登录
                          </span>
                        </span>
                      </span>
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/[0.05] text-zinc-400 transition-all duration-300 group-open:rotate-180 group-open:bg-white/[0.08] group-open:text-zinc-200">
                        <ArrowRight className="h-4 w-4 rotate-90" />
                      </span>
                    </summary>
                    <div className="mt-4 grid gap-3 border-t border-white/[0.06] pt-4 text-xs">
                      <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-3 font-mono text-amber-100/85">
                        <span className="text-zinc-500">User</span>
                        <span className="select-all">admin</span>
                      </div>
                      <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-3 font-mono text-amber-100/85">
                        <span className="text-zinc-500">Pass</span>
                        <span className="select-all">ChangeMe123!</span>
                      </div>
                      <p className="mt-1 leading-6 text-zinc-500">
                        登录后请尽快修改默认密码，避免初始化口令继续暴露在环境中。
                      </p>
                    </div>
                  </details>
                </div>
              </div>
            </div>

            <p className="mt-8 text-center text-[11px] font-medium leading-6 text-zinc-500 lg:text-left">
              继续即表示您已理解并同意当前环境以已认证用户为数据边界。
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
