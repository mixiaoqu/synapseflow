<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
  }>(),
  {
    title: "",
    description: "",
  },
);
</script>

<template>
  <section
    class="flex flex-col gap-4 rounded-[18px] border border-gray-200 bg-white px-5 py-[18px] shadow-sm"
  >
    <div v-if="title || description">
      <h3
        v-if="title"
        class="m-0 text-base font-semibold text-slate-900"
      >
        {{ title }}
      </h3>
      <p
        v-if="description"
        class="mt-2 text-[13px] leading-7 text-slate-600"
      >
        {{ description }}
      </p>
    </div>

    <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div class="flex flex-wrap items-center gap-3">
        <slot />
      </div>

      <div
        v-if="$slots.actions"
        class="flex flex-wrap items-center gap-3"
      >
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>
