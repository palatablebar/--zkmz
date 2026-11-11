<template>
  <section class="card">
    <div class="card-title">
      <h2>边界用例探针</h2>
      <span class="op-index">off-by-one</span>
    </div>
    <p class="small muted" style="margin-bottom: 10px">
      对首个样本特征合成 −1ms / 0ms / +1ms 三个事件，用同一判定函数输出 strict 与 inclusive
      的取值表：<em>恰好等于标签时刻</em>的事件只有 inclusive 会纳入 → 越界 0ms。
    </p>
    <table>
      <thead>
        <tr>
          <th>用例</th>
          <th>偏移</th>
          <th>strict 纳入</th>
          <th>inclusive 纳入</th>
          <th>判定</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="probe in probes" :key="probe.case">
          <td>{{ probe.case }}</td>
          <td>{{ probe.offset_ms }} ms</td>
          <td>{{ probe.included_strict ? '是' : '否' }}</td>
          <td>{{ probe.included_inclusive ? '是' : '否' }}</td>
          <td :style="{ color: probe.leak_under_inclusive ? 'var(--annot)' : 'inherit' }">
            {{ probe.verdict }}
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import type { BoundaryProbe } from '../../types/sample'

defineProps<{ probes: BoundaryProbe[] }>()
</script>
