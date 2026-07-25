<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useNotificationStore } from './stores/notifications'

const auth = useAuthStore()
const notifications = useNotificationStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="topnav" v-if="auth.isAuthenticated">
    <div class="topnav-inner">
      <router-link class="brand" :to="{ name: 'browser' }">DocManage</router-link>
      <nav>
        <router-link :to="{ name: 'browser' }">Browse</router-link>
        <router-link :to="{ name: 'reviews' }">My Reviews</router-link>
        <router-link v-if="auth.isAdmin" :to="{ name: 'admin-dashboard' }">Dashboard</router-link>
        <router-link v-if="auth.isAdmin" :to="{ name: 'admin-audit' }">Audit Log</router-link>
        <router-link v-if="auth.isAdmin" :to="{ name: 'admin-users' }">Users</router-link>
        <router-link v-if="auth.isAdmin" :to="{ name: 'admin-backup' }">Backup</router-link>
      </nav>
      <div class="user-info">
        <span>{{ auth.user.username }} ({{ auth.user.role }})</span>
        <button class="btn btn-sm" @click="logout">Log out</button>
      </div>
    </div>
  </div>

  <router-view />

  <div class="toast-stack">
    <div
      v-for="n in notifications.items"
      :key="n.id"
      class="toast"
      :class="{ 'toast-error': n.type === 'error' }"
      @click="notifications.dismiss(n.id)"
    >
      {{ n.message }}
    </div>
  </div>
</template>
