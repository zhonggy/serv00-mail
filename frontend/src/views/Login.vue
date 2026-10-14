<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>📮 serv00-mail</h2>
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form :model="f" label-width="70px" @submit.prevent="doLogin">
            <el-form-item label="用户名">
              <el-input v-model="f.username" autocomplete="username" placeholder="用户名，或邮箱地址（独立邮箱）" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="f.password" type="password" show-password autocomplete="current-password" @keyup.enter="doLogin" />
            </el-form-item>
            <el-button type="primary" :loading="loading" @click="doLogin" style="width:100%">登录</el-button>
            <p class="hint">也可用独立邮箱 / 域名主邮箱的地址 + 密码登录；别名需先设置登录密码</p>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form :model="f" label-width="70px" @submit.prevent="doRegister">
            <el-form-item label="用户名"><el-input v-model="f.username" autocomplete="username" /></el-form-item>
            <el-form-item label="密码">
              <el-input v-model="f.password" type="password" show-password autocomplete="new-password" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="f.confirm" type="password" show-password autocomplete="new-password" @keyup.enter="doRegister" />
            </el-form-item>
            <el-button type="success" :loading="loading" @click="doRegister" style="width:100%">注册</el-button>
            <p class="hint">第一个注册的用户自动成为管理员</p>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import { state } from '../store'

const router = useRouter()
const tab = ref('login')
const loading = ref(false)
const f = reactive({ username: '', password: '', confirm: '' })

async function afterAuth(token) {
  localStorage.setItem('sm_token', token)
  const { data } = await api.get('/auth/me')
  state.user = data
  router.replace('/mailboxes')
}

async function doLogin() {
  if (!f.username || !f.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    const { data } = await api.post('/auth/login', { username: f.username, password: f.password })
    await afterAuth(data.access_token)
  } catch (e) { ElMessage.error(errMsg(e, '登录失败')) }
  finally { loading.value = false }
}

async function doRegister() {
  if (!f.username || f.username.length < 3) return ElMessage.warning('用户名至少 3 个字符')
  if (!f.password) return ElMessage.warning('请输入密码')
  if (f.password !== f.confirm) return ElMessage.warning('两次输入的密码不一致')
  loading.value = true
  try {
    await api.post('/auth/register', { username: f.username, password: f.password })
    ElMessage.success('注册成功，已自动登录')
    const { data } = await api.post('/auth/login', { username: f.username, password: f.password })
    await afterAuth(data.access_token)
  } catch (e) { ElMessage.error(errMsg(e, '注册失败')) }
  finally { loading.value = false }
}
</script>

<style scoped>
.login-wrap { display: flex; height: 100%; align-items: center; justify-content: center; }
.login-card { width: 380px; }
.login-card h2 { text-align: center; margin: 0 0 12px; }
.hint { color: #909399; font-size: 12px; text-align: center; margin-top: 12px; }
</style>
