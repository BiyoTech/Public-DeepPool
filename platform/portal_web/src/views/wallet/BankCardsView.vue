<template>
  <div class="min-h-screen bg-slate-50">
    <div class="max-w-2xl mx-auto px-6 py-8">
      <h1 class="text-2xl font-bold text-dp-title mb-6">银行卡管理</h1>

      <!-- 银行卡列表 -->
      <div class="space-y-3 mb-6">
        <div v-if="cards.length === 0 && !loading" class="bg-white rounded-2xl border border-slate-100 shadow-sm p-8 text-center text-dp-muted text-sm">
          暂无绑定银行卡
        </div>
        <div
          v-for="card in cards"
          :key="card.id"
          class="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center justify-between"
        >
          <div>
            <div class="text-sm font-medium text-dp-title">{{ card.bank_name }}</div>
            <div class="text-xs text-dp-muted font-mono mt-0.5">**** **** **** {{ card.card_number }}</div>
            <div class="text-xs text-dp-placeholder mt-0.5">{{ card.card_holder }}</div>
          </div>
          <button
            class="text-xs text-red-400 hover:text-red-600 transition-colors"
            @click="handleDelete(card.id)"
          >
            解绑
          </button>
        </div>
      </div>

      <!-- 添加银行卡表单 -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
        <h2 class="text-base font-bold text-dp-title mb-4">绑定新银行卡</h2>
        <form @submit.prevent="handleCreate" class="space-y-4">
          <div>
            <label class="text-sm font-medium text-dp-body mb-1.5 block">银行名称</label>
            <input
              v-model="form.bank_name"
              type="text"
              placeholder="例如：中国银行"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              required
            />
          </div>
          <div>
            <label class="text-sm font-medium text-dp-body mb-1.5 block">银行卡号</label>
            <input
              v-model="form.card_number"
              type="text"
              placeholder="输入银行卡号"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              required
            />
          </div>
          <div>
            <label class="text-sm font-medium text-dp-body mb-1.5 block">持卡人姓名</label>
            <input
              v-model="form.card_holder"
              type="text"
              placeholder="输入持卡人姓名"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              required
            />
          </div>
          <button
            type="submit"
            :disabled="creating"
            class="w-full py-3 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium
                   shadow-sm hover:shadow-md transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {{ creating ? '...' : '绑定银行卡' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listBankCards, createBankCard, deleteBankCard } from '@/api/bankcard'

const cards = ref<any[]>([])
const loading = ref(false)
const creating = ref(false)
const form = ref({ bank_name: '', card_number: '', card_holder: '' })

async function fetchCards() {
  loading.value = true
  try {
    const res = await listBankCards()
    cards.value = res.data?.data || []
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.bank_name || !form.value.card_number || !form.value.card_holder) return
  creating.value = true
  try {
    await createBankCard(form.value)
    form.value = { bank_name: '', card_number: '', card_holder: '' }
    await fetchCards()
  } catch { /* ignore */ }
  finally { creating.value = false }
}

async function handleDelete(id: number) {
  if (!confirm('确定解绑此银行卡？')) return
  try {
    await deleteBankCard(id)
    await fetchCards()
  } catch { /* ignore */ }
}

onMounted(fetchCards)
</script>
