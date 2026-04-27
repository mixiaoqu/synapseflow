"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getAccessToken } from "@/lib/auth/session";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getAccessToken() ? "/admin" : "/login");
  }, [router]);

  return null;
}
