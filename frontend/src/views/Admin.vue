<template>
  <div class="page">
    <div class="card">
      <h3 style="margin-top:0">管理后台</h3>
      <el-tabs v-model="tab">
        <el-tab-pane label="全局设置" name="settings">
          <el-table :data="settings" v-loading="sLoading" style="max-width:640px">
            <el-table-column prop="key" label="键" width="200" />
            <el-table-column label="值">
              <template #default="{ row }">
                <el-switch
                  v-if="row.value === 'true' || row.value === 'false'"
                  :model-value="row.value === 'true'"
                  @change="(v) => saveSetting(row, v ? 'true' : 'false')"
                />
                <el-input v-else :model-value="row.value" @change="(v) => saveSetting(row, v)" style="max-width:280px" />
              </template>
            </el-table-column>
            <el-table-column label="说明" width="220">
              <template #default="{ row }">{{ desc(row.key) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="用户管理" name="users">
          <el-table :data="users" v-loading="uLoading" style="max-width:720px">
            <el-table-column prop="username" label="用户名" />
            <el-table-column label="管理员" width="100">
              <template #default="{ row }"><el-tag v-if="row.is_admin" type="danger" size="small">是</el-tag><span v-else>—</span></template>
            </el-table-column>
            <el-table-column label="允许发件" width="140">
              <template #default="{ row }">
                <el-switch :model-value="row.can_send" @change="(v) => saveUser(row, v)" :disabled="row.is_admin && row.id === state.user?.id" />
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="域名管理" name="domains">
          <div class="toolbar">
            <span class="hint-inline">每个域名配一个主邮箱（catch-all 指向它），该域名下别名的收发走主邮箱凭据</span>
            <span class="spacer" />
            <el-button type="primary" @click="openDomainDlg()">＋ 添加域名</el-button>
          </div>
          <el-table :data="domains" v-loading="dLoading">
            <el-table-column prop="domain" label="域名" width="220" />
            <el-table-column prop="master_email" label="主邮箱" min-width="220" />
            <el-table-column label="默认" width="100">
              <template #default="{ row }"><el-tag v-if="row.is_default" type="success" size="small">默认</el-tag><span v-else>—</span></template>
            </el-table-column>
            <el-table-column prop="created_at" label="添加时间" width="200" />
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <el-button v-if="!row.is_default" link type="primary" @click="setDefault(row)">设为默认</el-button>
                <el-button link type="primary" @click="openDomainDlg(row)">编辑</el-button>
                <el-button link type="danger" @click="delDomain(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!dLoading && !domains.length" description="还没有配置域名，先添加一个（域名须在 serv00 开启 catch-all 指向主邮箱）" />
        </el-tab-pane>

        <el-tab-pane label="API Keys" name="keys">
          <div class="toolbar">
            <span class="spacer" />
            <el-button type="primary" @click="kDlg = true">＋ 新建 Key</el-button>
          </div>
          <el-table :data="keys" v-loading="kLoading">
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column prop="key_prefix" label="前缀" width="140" />
            <el-table-column prop="scopes" label="权限范围" min-width="220" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '有效' : '已吊销' }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="200" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button v-if="row.is_active" link type="danger" @click="revoke(row)">吊销</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="kDlg" title="新建 API Key" width="420px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="kForm.name" placeholder="如 notify-service" /></el-form-item>
        <el-form-item label="权限">
          <el-checkbox-group v-model="kForm.scopes">
            <el-checkbox value="mailbox:write">建邮箱/删邮箱</el-checkbox>
            <el-checkbox value="mail:read">读邮件/取验证码</el-checkbox>
            <el-checkbox value="mail:send">发信</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kDlg = false">取消</el-button>
        <el-button type="primary" :loading="kCreating" @click="createKey">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="kShow" title="Key 已创建" width="440px">
      <el-alert type="warning" :closable="false" style="margin-bottom:12px">明文 Key 仅显示一次，请立即保存到调用方配置里。</el-alert>
      <el-input :value="newKey" readonly>
        <template #append><el-button @click="copyKey">复制</el-button></template>
      </el-input>
      <template #footer><el-button type="primary" @click="kShow = false">我已保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="dDlg" :title="dForm.id ? '编辑域名' : '添加域名'" width="440px">
      <el-form label-width="90px">
        <el-form-item label="域名">
          <el-input v-model="dForm.domain" :disabled="!!dForm.id" placeholder="如 ymail.de5.net" />
        </el-form-item>
        <el-form-item label="主邮箱">
          <el-input v-model="dForm.master_email" placeholder="如 admin@ymail.de5.net" />
        </el-form-item>
        <el-form-item label="主邮箱密码">
          <el-input v-model="dForm.master_password" type="password" show-password
                    :placeholder="dForm.id ? '不修改请留空' : '主邮箱的登录密码'" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="dForm.is_default" />
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" style="margin-top:4px">
        该域名须在 serv00 面板开启 catch-all 并指向主邮箱；密码加密存储，仅用于 IMAP/SMTP 登录。
      </el-alert>
      <template #footer>
        <el-button @click="dDlg = false">取消</el-button>
        <el-button type="primary" :loading="dSaving" @click="saveDomain">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { errMsg } from '../api'
import { state } from '../store'

const tab = ref('settings')
const settings = ref([])
const users = ref([])
const keys = ref([])
const sLoading = ref(false)
const uLoading = ref(false)
const kLoading = ref(false)
const kDlg = ref(false)
const kCreating = ref(false)
const kShow = ref(false)
const newKey = ref('')
const kForm = reactive({ name: '', scopes: ['mailbox:write', 'mail:read'] })
const domains = ref([])
const dLoading = ref(false)
const dDlg = ref(false)
const dSaving = ref(false)
const dForm = reactive({ id: 0, domain: '', master_email: '', master_password: '', is_default: false })

const DESCS = {
  allow_register: '是否允许新用户注册',
  allow_send: '全局发信总开关（关掉后所有发信接口返回 403）',
  default_domain: '新建邮箱默认使用的域名',
}
const desc = (k) => DESCS[k] || ''

async function loadSettings() {
  sLoading.value = true
  try { settings.value = (await api.get('/admin/settings')).data }
  catch (e) { ElMessage.error(errMsg(e, '加载设置失败')) }
  finally { sLoading.value = false }
}
async function saveSetting(row, value) {
  try {
    const { data } = await api.put(`/admin/settings/${row.key}`, { value: String(value) })
    row.value = data.value
    ElMessage.success('已保存')
  } catch (e) { ElMessage.error(errMsg(e, '保存失败')); loadSettings() }
}
async function loadUsers() {
  uLoading.value = true
  try { users.value = (await api.get('/admin/users')).data }
  catch (e) { ElMessage.error(errMsg(e, '加载用户失败')) }
  finally { uLoading.value = false }
}
async function saveUser(row, canSend) {
  try {
    const { data } = await api.patch(`/admin/users/${row.id}`, { can_send: canSend })
    row.can_send = data.can_send
    ElMessage.success('已更新')
  } catch (e) { ElMessage.error(errMsg(e, '更新失败')); loadUsers() }
}
async function loadKeys() {
  kLoading.value = true
  try { keys.value = (await api.get('/admin/api-keys')).data }
  catch (e) { ElMessage.error(errMsg(e, '加载 Keys 失败')) }
  finally { kLoading.value = false }
}
async function createKey() {
  if (!kForm.name) return ElMessage.warning('请填写名称')
  kCreating.value = true
  try {
    const { data } = await api.post('/admin/api-keys', { name: kForm.name, scopes: kForm.scopes.join(',') })
    newKey.value = data.key || ''
    kDlg.value = false
    kShow.value = true
    kForm.name = ''
    loadKeys()
  } catch (e) { ElMessage.error(errMsg(e, '创建失败')) }
  finally { kCreating.value = false }
}
async function revoke(row) {
  try {
    await ElMessageBox.confirm(`吊销 Key「${row.name}」？调用方将立即失效。`, '确认吊销', { type: 'warning' })
    await api.delete(`/admin/api-keys/${row.id}`)
    ElMessage.success('已吊销')
    loadKeys()
  } catch (e) { if (e !== 'cancel') ElMessage.error(errMsg(e, '吊销失败')) }
}
function copyKey() {
  navigator.clipboard?.writeText(newKey.value)
  ElMessage.success('已复制')
}

async function loadDomains() {
  dLoading.value = true
  try { domains.value = (await api.get('/admin/domains')).data }
  catch (e) { ElMessage.error(errMsg(e, '加载域名失败')) }
  finally { dLoading.value = false }
}
function openDomainDlg(row) {
  dForm.id = row?.id || 0
  dForm.domain = row?.domain || ''
  dForm.master_email = row?.master_email || ''
  dForm.master_password = ''
  dForm.is_default = row?.is_default || false
  dDlg.value = true
}
async function saveDomain() {
  if (!dForm.domain.trim() || !dForm.master_email.trim()) return ElMessage.warning('请填写域名和主邮箱')
  if (!dForm.id && !dForm.master_password) return ElMessage.warning('请填写主邮箱密码')
  dSaving.value = true
  try {
    const payload = {
      master_email: dForm.master_email.trim(),
      is_default: dForm.is_default,
    }
    if (dForm.master_password) payload.master_password = dForm.master_password
    if (dForm.id) {
      await api.patch(`/admin/domains/${dForm.id}`, payload)
    } else {
      payload.domain = dForm.domain.trim()
      await api.post('/admin/domains', payload)
    }
    ElMessage.success('已保存')
    dDlg.value = false
    loadDomains()
  } catch (e) { ElMessage.error(errMsg(e, '保存失败')) }
  finally { dSaving.value = false }
}
async function setDefault(row) {
  try {
    await api.patch(`/admin/domains/${row.id}`, { is_default: true })
    ElMessage.success(`已将 ${row.domain} 设为默认域名`)
    loadDomains()
  } catch (e) { ElMessage.error(errMsg(e, '设置失败')) }
}
async function delDomain(row) {
  try {
    await ElMessageBox.confirm(`删除域名「${row.domain}」？该域名下不能有邮箱。`, '确认删除', { type: 'warning' })
    await api.delete(`/admin/domains/${row.id}`)
    ElMessage.success('已删除')
    loadDomains()
  } catch (e) { if (e !== 'cancel') ElMessage.error(errMsg(e, '删除失败')) }
}

onMounted(() => { loadSettings(); loadUsers(); loadKeys(); loadDomains() })
</script>
