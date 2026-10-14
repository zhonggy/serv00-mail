<template>
  <div class="inbox">
    <!-- 左：邮箱卡片列 -->
    <div class="mb-col">
      <div class="mb-head">
        <span class="mb-title">收件箱</span>
        <el-button v-if="!state.user?.login_mailbox_id" type="primary" size="small" @click="dlg = true">＋ 新建</el-button>
      </div>
      <div class="mb-list">
        <div
          v-for="m in list" :key="m.id"
          class="mb-card" :class="{ active: m.id === curId }"
          @click="select(m.id)"
        >
          <div class="mb-email">{{ m.email }}</div>
          <div class="mb-meta">
            <span class="mb-actions" @click.stop>
              <el-button v-if="m.type === 'alias'" link type="primary" size="small" @click="openPw(m)">设密码</el-button>
              <el-button link type="primary" size="small" @click="copyEmail(m.email)">复制</el-button>
            </span>
          </div>
        </div>
        <el-empty v-if="!loading && !list.length" description="还没有邮箱，先建一个吧" />
      </div>
    </div>

    <!-- 右：选中邮箱的邮件列表 -->
    <div class="msg-col">
      <div class="card">
        <div class="toolbar">
          <h3 style="margin:0">{{ curEmail || '选择邮箱查看邮件' }}</h3>
          <span class="spacer" />
          <el-select v-model="limit" style="width:110px" @change="loadMsgs" :disabled="!curId">
            <el-option :value="20" label="最新 20 封" />
            <el-option :value="50" label="最新 50 封" />
            <el-option :value="100" label="最新 100 封" />
          </el-select>
          <el-button @click="loadMsgs" :disabled="!curId">刷新</el-button>
        </div>
        <el-table :data="msgs" v-loading="loading" style="width:100%" @row-click="openMsg" row-style="cursor:pointer">
          <el-table-column width="50">
            <template #default="{ row }">
              <span @click.stop="toggleStar(row)" class="star" :class="{ on: starred[row.uid] }">
                {{ starred[row.uid] ? '★' : '☆' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="from" label="发件人" min-width="180" show-overflow-tooltip />
          <el-table-column prop="subject" label="主题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="snippet" label="摘要" min-width="240" show-overflow-tooltip />
          <el-table-column prop="date" label="时间" width="170" />
        </el-table>
        <el-empty v-if="!loading && curId && !msgs.length" description="暂无邮件" />
        <el-empty v-if="!loading && !curId" description="从左侧选择一个邮箱" />
      </div>
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

    <!-- 新建邮箱 -->
    <el-dialog v-model="dlg" title="新建邮箱" width="420px">
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="account">独立邮箱（真实账号）</el-radio>
            <el-radio value="alias">别名（秒开、无限）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="域名">
          <el-select v-model="form.domain" placeholder="选择域名" style="width:100%" :disabled="!domains.length">
            <el-option
              v-for="d in domains"
              :key="d.domain"
              :value="d.domain"
              :label="d.domain + (d.is_default ? '（默认）' : '')"
            />
          </el-select>
          <div v-if="!domains.length" class="hint-inline" style="margin-top:4px">还没有配置域名，请先在管理后台 → 域名管理添加</div>
        </el-form-item>
        <el-form-item label="前缀">
          <el-input v-model="form.prefix" placeholder="留空则随机生成，如 notify01" />
        </el-form-item>
        <el-form-item v-if="form.type === 'alias'" label="登录密码">
          <el-input v-model="form.password" type="password" show-password placeholder="可选，设置后可用该邮箱+密码登录本项目" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pwdDlg" title="创建成功" width="440px">
      <el-alert type="warning" :closable="false" style="margin-bottom:12px">
        独立邮箱的密码仅显示一次，请立即保存。之后查邮件不需要密码，后端会用存档凭据自动登录。
      </el-alert>
      <el-input :value="createdInfo.email" readonly style="margin-bottom:8px" />
      <el-input :value="createdInfo.password" readonly>
        <template #append><el-button @click="copyPwd">复制密码</el-button></template>
      </el-input>
      <template #footer><el-button type="primary" @click="pwdDlg = false">我已保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="pwDlg" title="设置别名登录密码" width="400px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        {{ pwRow.email }}：该密码只用于登录本项目，不能登录网页邮箱/邮件客户端。
      </el-alert>
      <el-form label-width="80px">
        <el-form-item label="新密码"><el-input v-model="pwForm.password" type="password" show-password placeholder="至少 6 位" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwDlg = false">取消</el-button>
        <el-button type="primary" :loading="pwSaving" @click="savePw">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { errMsg } from '../api'
import { state } from '../store'
import { frameDoc, fitFrame } from '../frameDoc'

const list = ref([])
const loading = ref(false)
const curId = ref(null)
const curEmail = ref('')
const msgs = ref([])
const starred = ref({})
const detail = ref({})
const drawer = ref(false)
const limit = ref(20)

const dlg = ref(false)
const creating = ref(false)
const pwdDlg = ref(false)
const createdInfo = reactive({ email: '', password: '' })
const form = reactive({ type: 'alias', prefix: '', domain: '', password: '' })
const domains = ref([])
const pwDlg = ref(false)
const pwSaving = ref(false)
const pwRow = reactive({ id: 0, email: '' })
const pwForm = reactive({ password: '' })
const frameRef = ref(null)

function onFrameLoad() {
  if (frameRef.value) frameRef.value.style.height = '420px'
}

function onFrameMsg(e) {
  fitFrame(frameRef, e.data)
}

async function loadDomains() {
  try {
    domains.value = (await api.get('/domains')).data
    const def = domains.value.find((d) => d.is_default)
    if (def) form.domain = def.domain
  } catch (e) { /* 未配置域名时建邮箱会提示 */ }
}

async function load() {
  loading.value = true
  try {
    list.value = (await api.get('/mailboxes')).data
    if (list.value.length && !curId.value) select(list.value[0].id)
  } catch (e) { ElMessage.error(errMsg(e, '加载失败')) }
  finally { loading.value = false }
}

function select(id) {
  curId.value = id
  curEmail.value = list.value.find((m) => m.id === id)?.email || ''
  loadMsgs()
  loadStars()
}

async function loadMsgs() {
  if (!curId.value) return
  loading.value = true
  try {
    msgs.value = (await api.get(`/mailboxes/${curId.value}/messages`, { params: { limit: limit.value } })).data
  } catch (e) { ElMessage.error(errMsg(e, '加载邮件失败')) }
  finally { loading.value = false }
}

async function loadStars() {
  try {
    const { data } = await api.get('/stars')
    const map = {}
    for (const s of data) {
      if (s.mailbox_id === curId.value) map[s.imap_uid] = s.id
    }
    starred.value = map
  } catch { /* 忽略 */ }
}

async function toggleStar(row) {
  try {
    if (starred.value[row.uid]) {
      await api.delete(`/stars/${starred.value[row.uid]}`)
      ElMessage.success('已取消星标')
    } else {
      const { data } = await api.post('/stars', {
        mailbox_id: curId.value, imap_uid: String(row.uid),
        from_addr: row.from || '', subject: row.subject || '',
        snippet: row.snippet || '', date_str: row.date || '',
      })
      ElMessage.success('已加星标')
      starred.value[row.uid] = data.id
      return
    }
    loadStars()
  } catch (e) { ElMessage.error(errMsg(e, '操作失败')) }
}

async function openMsg(row) {
  try {
    detail.value = (await api.get(`/mailboxes/${curId.value}/messages/${row.uid}`)).data
    drawer.value = true
  } catch (e) { ElMessage.error(errMsg(e, '读取邮件失败')) }
}

async function create() {
  creating.value = true
  try {
    const { data } = await api.post('/mailboxes', {
      type: form.type,
      prefix: form.prefix || undefined,
      domain: form.domain || undefined,
      password: (form.type === 'alias' && form.password) ? form.password : undefined,
    })
    ElMessage.success(`已创建 ${data.email}`)
    dlg.value = false
    form.prefix = ''
    form.password = ''
    if (data.type === 'account' && data.password) {
      createdInfo.email = data.email
      createdInfo.password = data.password
      pwdDlg.value = true
    }
    await load()
    select(data.id)
  } catch (e) { ElMessage.error(errMsg(e, '创建失败')) }
  finally { creating.value = false }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除 ${row.email}？${row.type === 'account' ? 'serv00 上的真实邮箱也会一并删除。' : ''}`, '确认删除', { type: 'warning' })
    await api.delete(`/mailboxes/${row.id}`)
    ElMessage.success('已删除')
    if (curId.value === row.id) { curId.value = null; msgs.value = [] }
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(errMsg(e, '删除失败')) }
}

function copyEmail(email) {
  navigator.clipboard?.writeText(email)
  ElMessage.success('邮箱已复制')
}

function copyPwd() {
  navigator.clipboard?.writeText(createdInfo.password)
  ElMessage.success('密码已复制')
}

function openPw(row) {
  pwRow.id = row.id
  pwRow.email = row.email
  pwForm.password = ''
  pwDlg.value = true
}

async function savePw() {
  if (!pwForm.password || pwForm.password.length < 6) return ElMessage.warning('密码至少 6 位')
  pwSaving.value = true
  try {
    await api.patch(`/mailboxes/${pwRow.id}/password`, { password: pwForm.password })
    ElMessage.success('登录密码已设置')
    pwDlg.value = false
    load()
  } catch (e) { ElMessage.error(errMsg(e, '保存失败')) }
  finally { pwSaving.value = false }
}

onMounted(() => {
  load(); loadDomains()
  window.addEventListener('message', onFrameMsg)
})

onUnmounted(() => window.removeEventListener('message', onFrameMsg))
</script>

<style scoped>
.inbox { display: flex; gap: 16px; height: calc(100vh - 90px); min-height: 480px; }
.mb-col {
  width: 300px; flex-shrink: 0;
  background: #fff; border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  display: flex; flex-direction: column; overflow: hidden;
}
.mb-head {
  padding: 14px 16px; display: flex; align-items: center;
  justify-content: space-between; border-bottom: 1px solid #f0f2f7;
}
.mb-title { font-weight: 700; font-size: 15px; }
.mb-list { flex: 1; overflow-y: auto; padding: 10px; }
.mb-card {
  border: 1px solid #ebeef5; border-radius: 8px;
  padding: 16px; margin-bottom: 10px; cursor: pointer;
  transition: all 0.15s;
}
.mb-card:hover { border-color: #c6d8ff; }
.mb-card.active { border-color: #3b5bdb; background: #f0f4ff; }
.mb-email { font-size: 17px; font-weight: 600; word-break: break-all; margin-bottom: 8px; }
.mb-meta { display: flex; align-items: center; justify-content: flex-end; }
.mb-actions { display: flex; gap: 2px; }
.msg-col { flex: 1; min-width: 0; display: flex; }
.msg-col .card { flex: 1; display: flex; flex-direction: column; }
.card {
  background: #fff; border-radius: 10px; padding: 18px 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); width: 100%;
}
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.toolbar .spacer { flex: 1; }
.star { cursor: pointer; font-size: 18px; color: #c0c4cc; user-select: none; }
.star.on { color: #f5a623; }
.html-frame { width: 100%; border: 1px solid #ebeef5; border-radius: 4px; flex-shrink: 0; }
.text-body { flex: 1; min-height: 0; overflow: auto; white-space: pre-wrap; word-break: break-word; font-size: 14px; margin: 0; }
.msg-drawer :deep(.el-drawer__body) { display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
.drawer-body { display: flex; flex-direction: column; }
.drawer-body p { margin: 3px 0; flex-shrink: 0; }
.drawer-body .el-divider { flex-shrink: 0; }
</style>
