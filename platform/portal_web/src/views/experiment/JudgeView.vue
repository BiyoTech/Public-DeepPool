<template>
  <div class="bg-white rounded-xl border border-slate-200 p-6">
    <div class="text-center py-16">
      <svg class="w-16 h-16 mx-auto text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.97z" />
      </svg>
      <h2 class="text-lg font-semibold text-dp-title mb-2">{{ $t('experiment.judge_title') }}</h2>
      <p class="text-sm text-dp-muted">{{ $t('experiment.judge_desc') }}</p>
    </div>
  </div>
</template>
