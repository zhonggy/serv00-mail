<template>
  <div class="page">
    <div class="card">
      <div class="toolbar">
        <h3 style="margin:0">星标邮件</h3>
        <span class="spacer" />
        <el-button @click="load">刷新</el-button>
      </div>
      <el-table :data="list" v-loading="loading" style="width:100%" @row-click="openMail" row-style="cursor:pointer">
        <el-table-column prop="mailbox_email" label="所在邮箱" min-width="200" show-overflow-tooltip />
        <el-table-column prop="from_addr" label="发件人" min-width="180" show-overflow-tooltip />
        <el-table-column prop="subject" label="主题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="date_str" label="时间" width="170" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="danger" @click.stop="unstar(row)">取消星标</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !list.length" description="还没有星标邮件，在收件箱点 ☆ 即可收藏" />
    </div>
    <el-drawer v-model="drawer" :title="detail.subject || '邮件详情'" size="55%" class="msg-drawer">
      <div class="drawer-body">
        <p><b>发件人：</b>{{ detail.from }}</p>
        <p><b>收件人：</b>{{ detail.to }}</p>
        <p><b>时间：</b>{{ detail.date }}</p>
        <el-divider />
        <iframe
          v-if="detail.body_html"
          :key="detail.uid || detail.id"
          ref="frameRef"
          :srcdoc="frameDoc(detail.body_html)"
          class="html-frame"
          sandbox="allow-scripts"
          @load="onFrameLoad"
        />
        <pre v-else class="text-body">{{ detail.body_text }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import { frameDoc, fitFrame } from '../frameDoc'

const list = ref([])
const loading = ref(false)
const detail = ref({})
const drawer = ref(false)
const frameRef = ref(null)

function onFrameLoad() {
  if (frameRef.value) frameRef.value.style.height = '420px'
}

function onFrameMsg(e) {
  fitFrame(frameRef, e.data)
}

async function load() {
  loading.value = true
  try { list.value = (await api.get('/stars')).data }
  catch (e) { ElMessage.error(errMsg(e, '加载失败')) }
  finally { loading.value = false }
}

async function openMail(row) {
  try {
    detail.value = (await api.get(`/mailboxes/${row.mailbox_id}/messages/${row.imap_uid}`)).data
    drawer.value = true
  } catch (e) { ElMessage.error(errMsg(e, '读取邮件失败（可能已被删除）')) }
}

async function unstar(row) {
  try {
    await api.delete(`/stars/${row.id}`)
    ElMessage.success('已取消星标')
    load()
  } catch (e) { ElMessage.error(errMsg(e, '操作失败')) }
}

onMounted(() => {
  load()
  window.addEventListener('message', onFrameMsg)
})

onUnmounted(() => window.removeEventListener('message', onFrameMsg))
</script>

<style scoped>
.html-frame { width: 100%; border: 1px solid #ebeef5; border-radius: 4px; flex-shrink: 0; }
.text-body { white-space: pre-wrap; word-break: break-word; font-size: 14px; margin: 0; }
.msg-drawer :deep(.el-drawer__body) { display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
.drawer-body { display: flex; flex-direction: column; }
.drawer-body p { margin: 3px 0; flex-shrink: 0; }
.drawer-body .el-divider { flex-shrink: 0; }
</style>
