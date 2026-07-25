<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { extractErrorMessage } from '../utils/errors'

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push(route.query.redirect || { name: 'browser' })
  } catch (e) {
    error.value = e?.response?.status === 401 ? 'Invalid username or password.' : extractErrorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="container" style="max-width: 380px; margin-top: 10vh">
    <h1>Document Management</h1>
    <form class="card" @submit.prevent="submit">
      <div class="field">
        <label for="username">Username</label>
        <input id="username" v-model="username" autocomplete="username" required style="width: 100%" />
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          style="width: 100%"
        />
      </div>
      <button class="btn btn-primary" type="submit" :disabled="loading" style="width: 100%">
        {{ loading ? 'Signing in…' : 'Sign in' }}
      </button>
      <p v-if="error" class="error-text">{{ error }}</p>
    </form>
  </div>
</template>
