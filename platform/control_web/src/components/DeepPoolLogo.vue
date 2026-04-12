<!-- DeepPool brand logo — circuit board + server rack motif.
     Accepts `size` prop for width/height (default 32px). -->
<template>
  <svg :width="size" :height="size" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="dp-logo-grad" x1="10" y1="8" x2="54" y2="58" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#38BDF8" />
        <stop offset="50%" stop-color="#3B82F6" />
        <stop offset="100%" stop-color="#8B5CF6" />
      </linearGradient>
    </defs>
    <!-- Server rack body -->
    <rect x="36" y="10" width="18" height="44" rx="3" stroke="url(#dp-logo-grad)" stroke-width="2.5" fill="none" />
    <!-- Server slots -->
    <rect x="40" y="16" width="10" height="4" rx="1" fill="url(#dp-logo-grad)" opacity="0.7" />
    <rect x="40" y="24" width="10" height="4" rx="1" fill="url(#dp-logo-grad)" opacity="0.7" />
    <rect x="40" y="32" width="10" height="4" rx="1" fill="url(#dp-logo-grad)" opacity="0.7" />
    <rect x="40" y="40" width="10" height="4" rx="1" fill="url(#dp-logo-grad)" opacity="0.7" />
    <!-- LED indicators -->
    <circle cx="42" cy="18" r="1" fill="url(#dp-logo-grad)" />
    <circle cx="42" cy="26" r="1" fill="url(#dp-logo-grad)" />
    <circle cx="42" cy="34" r="1" fill="url(#dp-logo-grad)" />
    <circle cx="42" cy="42" r="1" fill="url(#dp-logo-grad)" />
    <!-- Circuit traces flowing from left into server -->
    <path d="M8 18 Q18 18 24 14 L36 14" stroke="url(#dp-logo-grad)" stroke-width="2" stroke-linecap="round" fill="none" />
    <path d="M8 30 Q16 30 22 24 L36 24" stroke="url(#dp-logo-grad)" stroke-width="2" stroke-linecap="round" fill="none" />
    <path d="M8 42 Q16 42 22 36 L36 36" stroke="url(#dp-logo-grad)" stroke-width="2" stroke-linecap="round" fill="none" />
    <path d="M12 52 Q18 52 24 46 L36 46" stroke="url(#dp-logo-grad)" stroke-width="2" stroke-linecap="round" fill="none" />
    <!-- Circuit junction nodes -->
    <circle cx="8" cy="18" r="2.5" fill="url(#dp-logo-grad)" />
    <circle cx="8" cy="30" r="2.5" fill="url(#dp-logo-grad)" />
    <circle cx="8" cy="42" r="2.5" fill="url(#dp-logo-grad)" />
    <circle cx="12" cy="52" r="2.5" fill="url(#dp-logo-grad)" />
    <!-- Mid-trace junction dots -->
    <circle cx="24" cy="14" r="1.5" fill="url(#dp-logo-grad)" />
    <circle cx="22" cy="24" r="1.5" fill="url(#dp-logo-grad)" />
    <circle cx="22" cy="36" r="1.5" fill="url(#dp-logo-grad)" />
    <circle cx="24" cy="46" r="1.5" fill="url(#dp-logo-grad)" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number | string }>(), { size: 32 })
</script>
