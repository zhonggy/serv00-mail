<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">📮 serv00-mail</div>
      <el-menu :default-active="$route.path" router class="menu" active-text-color="#fff">
        <el-menu-item index="/mailboxes"><el-icon><Message /></el-icon><span>收件箱</span></el-menu-item>
        <el-menu-item index="/compose"><el-icon><EditPen /></el-icon><span>写信</span></el-menu-item>
        <el-menu-item index="/sent"><el-icon><Promotion /></el-icon><span>已发送</span></el-menu-item>
        <el-menu-item index="/drafts"><el-icon><Document /></el-icon><span>草稿箱</span></el-menu-item>
        <el-menu-item index="/stars"><el-icon><Star /></el-icon><span>星标邮件</span></el-menu-item>
        <el-menu-item index="/profile"><el-icon><User /></el-icon><span>个人设置</span></el-menu-item>
        <div v-if="state.user?.is_admin" class="group-label">管理</div>
        <el-menu-item v-if="state.user?.is_admin" index="/admin"><el-icon><Setting /></el-icon><span>管理后台</span></el-menu-item>
      </el-menu>
      <div class="aside-foot">
        <div class="foot-id">
          <el-tag v-if="state.user?.is_admin" type="danger" size="small">管理员</el-tag>
          <span class="uname">{{ displayName }}</span>
        </div>
        <el-button class="logout-btn" @click="logout">退出</el-button>
      </div>
    </el-aside>
    <el-container>
      <el-main class="main"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { Message, EditPen, Setting, Promotion, Document, Star, User } from '@element-plus/icons-vue'
import { state, logout } from '../store'

// 邮箱登录显示登录的邮箱地址，项目账号登录显示用户名
const displayName = computed(() => {
  if (state.user?.login_mailbox_id) {
    return state.user.login_mailbox_email || state.user.username || ''
  }
  return state.user?.username || ''
})
</script>

<style scoped>
.layout { height: 100%; }
.aside {
  background: #1b2340;
  color: #c6cde4;
  display: flex;
  flex-direction: column;
  border-right: none;
}
.brand {
  padding: 20px 18px 16px;
  font-weight: 700;
  font-size: 17px;
  color: #fff;
  letter-spacing: 1px;
}
.menu {
  flex: 1;
  background: transparent;
  border-right: none;
}
.menu :deep(.el-menu-item) {
  color: #aab3d4;
  height: 46px;
  line-height: 46px;
  margin: 2px 10px;
  border-radius: 8px;
}
.menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}
.menu :deep(.el-menu-item.is-active) {
  background: #3b5bdb;
  color: #fff;
}
.menu :deep(.el-menu-item .el-icon) {
  font-size: 17px;
}
.group-label {
  padding: 14px 22px 4px;
  font-size: 12px;
  color: #6b76a0;
  letter-spacing: 2px;
}
.aside-foot {
  padding: 10px 0 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.foot-id {
  padding: 2px 22px;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
}
.uname {
  color: #c6cde4;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.logout-btn {
  height: 46px;
  margin: 2px 10px;
  background: rgba(255, 255, 255, 0.06);
  border: none;
  border-radius: 8px;
  color: #aab3d4;
  font-size: 14px;
}
.logout-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}
.main { background: #f2f4fa; padding: 20px 24px; }
</style>
