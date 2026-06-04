<template>
  <div class="relative min-h-screen overflow-hidden bg-gradient-to-br from-teal-50 via-slate-50 to-indigo-50">
    <div
      class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_20%,rgba(15,118,110,0.18),transparent_22%),radial-gradient(circle_at_82%_18%,rgba(30,64,175,0.14),transparent_18%),radial-gradient(circle_at_70%_72%,rgba(14,116,144,0.12),transparent_20%)]"
    />
    <div class="relative z-10 min-h-screen">
      <router-view />
    </div>
  </div>
</template>
