<template>
  <div class="relative min-h-screen overflow-hidden bg-[var(--admin-bg)]">
    <div class="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-blue-50 to-transparent" />
    <div class="relative z-10 min-h-screen">
      <router-view />
    </div>
  </div>
</template>
