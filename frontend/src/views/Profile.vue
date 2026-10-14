<template>
  <div class="page">
    <div class="card narrow">
      <h3 style="margin:0 0 16px">个人设置</h3>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="登录方式">
          <el-tag v-if="loginMb" type="info">邮箱登录</el-tag>
          <el-tag v-else type="success">项目账号</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="用户名">{{ loginMb ? loginMbEmail : state.user?.username }}</el-descriptions-item>
        <el-descriptions-item label="身份">
          <el-tag v-if="state.user?.is_admin" type="danger">管理员</el-tag>
          <el-tag v-else type="info">普通用户</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="loginMb" label="登录邮箱">{{ loginMbEmail }}</el-descriptions-item>
        <el-descriptions-item v-else label="我的邮箱">
          <div v-for="m in boxes" :key="m.id" class="mb-line">
            {{ m.email }}
            <el-tag :type="m.type === 'account' ? 'success' : 'info'" size="small" style="margin-left:6px">
              {{ m.type === 'account' ? '独立邮箱' : '别名' }}
            </el-tag>
          </div>
          <span v-if="!boxes.length" class="muted">暂无邮箱</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />
      <h4 style="margin:0 0 12px">修改密码</h4>
      <p class="muted" style="margin:0 0 12px">
        {{ loginMb ? '修改的是你登录用邮箱的密码（只用于登录本项目）。' : '修改的是项目登录密码。' }}
      </p>
      <el-form :model="pw" label-width="90px" style="max-width:420px">
        <el-form-item label="原密码">
          <el-input v-model="pw.old" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pw.new1" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pw.new2" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="changePw">修改密码</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import { state } from '../store'

const boxes = ref([])
const loginMb = ref(null)
const loginMbEmail = ref('')
const saving = ref(false)
const pw = reactive({ old: '', new1: '', new2: '' })

onMounted(async () => {
  try {
    boxes.value = (await api.get('/mailboxes')).data
  } catch { /* 忽略 */ }
  const mbId = state.user?.login_mailbox_id
  if (mbId) {
    loginMb.value = mbId
    loginMbEmail.value = boxes.value.find((m) => m.id === mbId)?.email || `#${mbId}`
  }
})

async function changePw() {
  if (!pw.old) return ElMessage.warning('请输入原密码')
  if (!pw.new1 || pw.new1.length < 6) return ElMessage.warning('新密码至少 6 位')
  if (pw.new1 !== pw.new2) return ElMessage.warning('两次输入的新密码不一致')
  saving.value = true
  try {
    await api.post('/auth/change-password', { old_password: pw.old, new_password: pw.new1 })
    ElMessage.success('密码已修改，请重新登录')
    pw.old = ''; pw.new1 = ''; pw.new2 = ''
    setTimeout(() => { localStorage.removeItem('sm_token'); location.hash = '#/login'; location.reload() }, 1200)
  } catch (e) { ElMessage.error(errMsg(e, '修改失败')) }
  finally { saving.value = false }
}
</script>

<style scoped>
.narrow { max-width: 760px; }
.mb-line { padding: 2px 0; }
.muted { color: #909399; font-size: 13px; }
</style>
