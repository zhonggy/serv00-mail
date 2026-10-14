<template>
  <div class="page">
    <div class="card">
      <div class="toolbar">
        <h3 style="margin:0">草稿箱</h3>
        <span class="spacer" />
        <el-button @click="load">刷新</el-button>
      </div>
      <el-table :data="list" v-loading="loading" style="width:100%">
        <el-table-column prop="to_addrs" label="收件人" min-width="200" show-overflow-tooltip />
        <el-table-column prop="subject" label="主题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="180" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/compose?draft=${row.id}`)">继续编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !list.length" description="草稿箱是空的" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { errMsg } from '../api'

const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try { list.value = (await api.get('/drafts')).data }
  catch (e) { ElMessage.error(errMsg(e, '加载失败')) }
  finally { loading.value = false }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm('删除这封草稿？', '确认删除', { type: 'warning' })
    await api.delete(`/drafts/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(errMsg(e, '删除失败')) }
}

onMounted(load)
</script>
