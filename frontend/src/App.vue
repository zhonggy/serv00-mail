<template>
  <router-view v-if="state.ready" />
  <div v-else class="boot">加载中…</div>
</template>

<script setup>
import { state } from './store'
</script>

<style>
html, body, #app { height: 100%; margin: 0; }
body { font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f5f7fa; }
.boot { display: flex; height: 100%; align-items: center; justify-content: center; color: #909399; }
.page { padding: 20px; }
.card { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.toolbar .spacer { flex: 1; }
.hint-inline { color: #909399; font-size: 13px; }
</style>
