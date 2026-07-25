<script setup>
import { onMounted, ref } from 'vue'
import { createUser, listUsers, updateUser } from '../api/auth'
import { useNotificationStore } from '../stores/notifications'
import { extractErrorMessage } from '../utils/errors'

const users = ref([])
const notifications = useNotificationStore()

const newUsername = ref('')
const newPassword = ref('')
const newRole = ref('employee')
const newDepartment = ref('')
const creating = ref(false)
const error = ref('')

async function load() {
  const data = await listUsers()
  users.value = data.results ?? data
}

async function createNewUser() {
  error.value = ''
  creating.value = true
  try {
    await createUser({
      username: newUsername.value,
      password: newPassword.value,
      role: newRole.value,
      department: newDepartment.value,
    })
    newUsername.value = ''
    newPassword.value = ''
    newDepartment.value = ''
    notifications.push('User created.')
    await load()
  } catch (e) {
    error.value = extractErrorMessage(e)
  } finally {
    creating.value = false
  }
}

async function changeRole(user, role) {
  try {
    await updateUser(user.id, { role })
    notifications.push(`${user.username} is now ${role}.`)
    await load()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function toggleActive(user) {
  try {
    await updateUser(user.id, { is_active: !user.is_active })
    await load()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

onMounted(load)
</script>

<template>
  <div class="container">
    <h1>Users</h1>

    <div class="card">
      <h3>Create user</h3>
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px">
        <input v-model="newUsername" placeholder="Username" />
        <input v-model="newPassword" type="password" placeholder="Password" />
        <select v-model="newRole">
          <option value="employee">Employee</option>
          <option value="admin">Admin</option>
        </select>
        <input v-model="newDepartment" placeholder="Department (optional)" />
      </div>
      <button class="btn btn-primary btn-sm" style="margin-top: 10px" :disabled="creating" @click="createNewUser">
        Create
      </button>
      <p v-if="error" class="error-text">{{ error }}</p>
    </div>

    <div class="card">
      <table>
        <thead><tr><th>Username</th><th>Department</th><th>Role</th><th>Active</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td class="muted">{{ u.department || '—' }}</td>
            <td>
              <select :value="u.role" @change="changeRole(u, $event.target.value)">
                <option value="employee">Employee</option>
                <option value="admin">Admin</option>
              </select>
            </td>
            <td>{{ u.is_active ? 'Yes' : 'No' }}</td>
            <td><button class="btn btn-sm" @click="toggleActive(u)">{{ u.is_active ? 'Deactivate' : 'Activate' }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
