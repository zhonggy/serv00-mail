<template>
  <div class="compose">
    <div class="card">
      <h3 class="title">写信</h3>
      <el-form :model="f" label-width="80px" class="form">
        <el-form-item label="发件邮箱">
          <el-select v-if="!isMailboxLogin" v-model="f.mailbox_id" placeholder="选择发件邮箱" style="width:100%">
            <el-option v-for="m in boxes" :key="m.id" :label="m.email" :value="m.id" />
          </el-select>
          <el-input v-else :value="loginMbEmail" readonly style="width:100%" />
        </el-form-item>
        <el-form-item label="收件人">
          <el-input v-model="f.to" placeholder="someone@example.com，多个用逗号分隔" />
        </el-form-item>
        <el-form-item label="主题"><el-input v-model="f.subject" /></el-form-item>
        <el-form-item label="正文" class="body-item">
          <div class="editor-wrap">
            <QuillEditor
              v-model:content="f.body"
              contentType="html"
              :options="editorOptions"
            />
          </div>
        </el-form-item>
        <el-form-item class="btn-row">
          <el-button type="primary" :loading="sending" @click="send">发送</el-button>
          <el-button :loading="saving" @click="saveDraft">存草稿</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { QuillEditor } from '@vueup/vue-quill'
import '@vueup/vue-quill/dist/vue-quill.snow.css'
import api, { errMsg } from '../api'
import { state } from '../store'

const route = useRoute()
const router = useRouter()
const boxes = ref([])
const sending = ref(false)
const saving = ref(false)
const draftId = ref(null)
const f = reactive({ mailbox_id: null, to: '', subject: '', body: '' })

// 邮箱登录：发件邮箱锁定为登录的邮箱，不可切换
const isMailboxLogin = computed(() => !!state.user?.login_mailbox_id)
const loginMbEmail = computed(() => {
  const id = state.user?.login_mailbox_id
  return boxes.value.find((m) => m.id === id)?.email || ''
})

const editorOptions = {
  theme: 'snow',
  placeholder: '在此输入正文…',
  modules: {
    toolbar: [
      ['bold', 'italic', 'underline', 'strike'],
      [{ color: [] }, { background: [] }],
      [{ header: [1, 2, 3, false] }],
      [{ list: 'ordered' }, { list: 'bullet' }],
      [{ align: [] }],
      ['link', 'clean'],
    ],
  },
}

onMounted(async () => {
  try {
    boxes.value = (await api.get('/mailboxes')).data
    const loginMb = state.user?.login_mailbox_id
    if (loginMb && boxes.value.some((m) => m.id === loginMb)) {
      f.mailbox_id = loginMb
    } else if (boxes.value.length) {
      f.mailbox_id = boxes.value[0].id
    }
  } catch (e) { ElMessage.error(errMsg(e, '加载邮箱列表失败')) }
  // 从草稿箱进来：?draft=ID
  if (route.query.draft) {
    try {
      const { data } = await api.get(`/drafts/${route.query.draft}`)
      draftId.value = data.id
      f.to = data.to_addrs
      f.subject = data.subject
      f.body = data.body_html || ''
      if (data.mailbox_id && boxes.value.some((m) => m.id === data.mailbox_id)) {
        f.mailbox_id = data.mailbox_id
      }
    } catch (e) { ElMessage.error(errMsg(e, '加载草稿失败')) }
  }
})

async function send() {
  if (!f.mailbox_id) return ElMessage.warning('请选择发件邮箱')
  if (!f.to) return ElMessage.warning('请填写收件人')
  sending.value = true
  try {
    await api.post(`/mailboxes/${f.mailbox_id}/send`, {
      to: f.to, subject: f.subject, body: f.body || '', html: true,
    })
    ElMessage.success('已发送')
    if (draftId.value) {
      try { await api.delete(`/drafts/${draftId.value}`) } catch { /* 忽略 */ }
      draftId.value = null
    }
    f.to = ''; f.subject = ''; f.body = ''
  } catch (e) {
    ElMessage.error(e.response?.status === 403 ? '发送被管理员关闭（全局开关或你的发件权限）' : errMsg(e, '发送失败'))
  } finally { sending.value = false }
}

async function saveDraft() {
  saving.value = true
  try {
    const payload = {
      mailbox_id: f.mailbox_id, to_addrs: f.to,
      subject: f.subject, body_html: f.body || '',
    }
    if (draftId.value) {
      await api.put(`/drafts/${draftId.value}`, payload)
    } else {
      const { data } = await api.post('/drafts', payload)
      draftId.value = data.id
    }
    ElMessage.success('草稿已保存')
  } catch (e) { ElMessage.error(errMsg(e, '保存草稿失败')) }
  finally { saving.value = false }
}
</script>

<style scoped>
.compose { height: 100%; }
.card {
  background: #fff;
  border-radius: 10px;
  padding: 22px 26px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  min-height: calc(100vh - 110px);
  display: flex;
  flex-direction: column;
}
.title { margin: 0 0 18px; font-size: 17px; }
.form { max-width: 1100px; flex: 1; display: flex; flex-direction: column; }
.body-item { flex: 1; margin-bottom: 0; }
.btn-row { flex-shrink: 0; margin-top: 16px; margin-bottom: 0; }
.body-item { flex: 1; margin-bottom: 0; }
.body-item :deep(.el-form-item__content) { display: flex; flex-direction: column; align-items: stretch; }
.editor-wrap { flex: 1; display: flex; flex-direction: column; min-height: 420px; }
.editor-wrap :deep(.ql-toolbar.ql-snow) { flex-shrink: 0; border-radius: 6px 6px 0 0; border-color: #dcdfe6; }
.editor-wrap :deep(.ql-container.ql-snow) { flex: 1; display: flex; flex-direction: column; min-height: 0; border-radius: 0 0 6px 6px; border-color: #dcdfe6; font-size: 14px; }
.editor-wrap :deep(.ql-editor) { flex: 1; overflow-y: auto; min-height: 0; }
</style>
