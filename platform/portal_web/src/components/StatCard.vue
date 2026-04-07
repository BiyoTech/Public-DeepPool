<template>
  <div class="text-center py-2">
    <div class="inline-flex flex-col items-center">
      <span class="text-3xl md:text-4xl font-bold bg-gradient-to-r from-dp-blue to-dp-blue-dark bg-clip-text text-transparent tabular-nums">
        {{ displayValue }}
      </span>
      <span class="text-sm text-dp-muted mt-1">{{ label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = defineProps<{
  value: number
  label: string
}>()

const displayValue = ref('0')

/** 数字计数动画（easeOutExpo 缓动） */
function animate(target: number) {
  const duration = 1500
  const start = performance.now()
  function step(now: number) {
    const progress = Math.min((now - start) / duration, 1)
    const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
    displayValue.value = Math.floor(eased * target).toLocaleString()
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

onMounted(() => animate(props.value))
watch(() => props.value, (val) => animate(val))
</script>
