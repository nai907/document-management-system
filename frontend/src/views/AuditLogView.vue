<script setup>
import { onMounted, ref, watch } from 'vue'
import { listAuditLog } from '../api/audit'
import { useNotificationStore } from '../stores/notifications'
import { extractErrorMessage } from '../utils/errors'

const entries = ref([])
const actionFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const notifications = useNotificationStore()

const ACTIONS = [
  '', 'upload', 'view', 'download', 'edit_metadata', 'new_version',
  'submit_for_review', 'approve', 'reject', 'permission_grant',
  'permission_revoke', 'move', 'delete',
]

async function load() {
  try {
    const params = {}
    if (actionFilter.value) params.action = actionFilter.value
    if (dateFrom.value) params.date_from = dateFrom.value
    if (dateTo.value) params.date_to = dateTo.value
    const data = await listAuditLog(params)
    entries.value = data.results ?? data
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

watch([actionFilter, dateFrom, dateTo], load)
onMounted(load)
</script>

<template>
  <div class="container">
    <h1>Global audit log</h1>
    <div class="card flex-row">
      <select v-model="actionFilter">
        <option v-for="a in ACTIONS" :key="a" :value="a">{{ a || 'All actions' }}</option>
      </select>
      <input v-model="dateFrom" type="date" />
      <input v-model="dateTo" type="date" />
    </div>
    <div class="card">
      <table>
        <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Document</th><th>Details</th></tr></thead>
        <tbody>
          <tr v-for="e in entries" :key="e.id">
            <td class="muted">{{ new Date(e.timestamp).toLocaleString() }}</td>
            <td>{{ e.actor_username || 'system' }}</td>
            <td>{{ e.action }}</td>
            <td class="muted">{{ e.document_code || e.target_repr || '—' }}</td>
            <td class="muted" style="font-size: 0.8rem">{{ JSON.stringify(e.metadata) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
