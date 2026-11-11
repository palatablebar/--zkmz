<template>
  <div class="shell">
    <aside class="rail">
      <div class="rail-brand">FeatPoint · 工艺卡</div>
      <div v-for="step in steps" :key="step.code" class="rail-step">
        <strong>{{ step.code }}</strong>
        <span>{{ step.title }}</span>
      </div>
    </aside>

    <main class="main" style="max-width: 720px">
      <div class="sheet-head">
        <div>
          <div class="op">工序 00 / 领料登记</div>
          <h1>FeatPoint 特征工艺卡</h1>
          <p class="sub">
            岚舟科技 · 风控算法组：把「按天写 SQL 拼特征」改成带点时间口径的工艺卡——
            每个特征一张配方单，每条样本一份校验记录。
          </p>
        </div>
        <div class="seal">
          <div>消费贷特征平台</div>
          <div>车间工艺卡 No. F-2026-01</div>
        </div>
      </div>

      <form class="card" @submit.prevent="submit">
        <div class="card-title">
          <h2>账号</h2>
          <span class="op-index">login</span>
        </div>
        <div class="field">
          <label>邮箱</label>
          <input v-model="email" type="email" autocomplete="username" placeholder="owner@featpoint.demo" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="Demo@2026" />
        </div>
        <ErrorNotice :error="error" />
        <div class="actions">
          <button class="btn btn-annot" type="submit" :disabled="loading">
            {{ loading ? '校验中…' : '领取工艺卡' }}
          </button>
          <span class="small muted">三个演示账号：owner / analyst / viewer @featpoint.demo</span>
        </div>
        <div class="tear" />
        <p class="small muted">
          角色差异：owner 可改特征定义与发起回填；analyst 建样本任务但改定义会被 403 拒绝；
          viewer 只读校验报告。
        </p>
      </form>
    </main>

    <aside class="margin-col">
      <div class="margin-note">
        <span class="stamp">批注 · 001</span>
        <p>
          离线 AUC 0.89 / 线上 0.71：训练时用 join 取「当天最新值」，把标签时刻之后的事件带进了特征。
          工艺卡的第一条规矩——窗口右端必须排除标签时刻。
        </p>
      </div>
      <div class="margin-note" style="color: var(--ink-soft); border-left-color: var(--ink-line-strong)">
        <span class="stamp" style="color: var(--ink-soft); border-color: var(--ink-line-strong)">工位</span>
        <p>事件源：申请 / 还款 / 登录 三类账户事件；标签集：2026Q1 申请样本 A/B 各 400。</p>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import { OPERATION_STEPS } from '../constants/recipe'
import { useApi } from '../hooks/useApi'
import { useAuthStore } from '../stores/auth'

const steps = OPERATION_STEPS
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { loading, error, run } = useApi()

const email = ref('owner@featpoint.demo')
const password = ref('Demo@2026')

async function submit() {
  const ok = await run(() => auth.login(email.value.trim(), password.value))
  if (ok) {
    const next = typeof route.query.next === 'string' ? route.query.next : '/features'
    router.replace(next)
  }
}
</script>
