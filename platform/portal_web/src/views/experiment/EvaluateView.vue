<template>
  <div class="bg-white rounded-xl border border-slate-200 p-6">
    <div class="text-center py-16">
      <svg class="w-16 h-16 mx-auto text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625z" />
      </svg>
      <h2 class="text-lg font-semibold text-dp-title mb-2">{{ $t('experiment.evaluate_title') }}</h2>
      <p class="text-sm text-dp-muted">{{ $t('experiment.evaluate_desc') }}</p>
    </div>
  </div>
</template>
