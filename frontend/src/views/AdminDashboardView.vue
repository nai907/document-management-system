<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { dashboardSummary } from '../api/audit'
import { useNotificationStore } from '../stores/notifications'
import { extractErrorMessage } from '../utils/errors'

const summary = ref(null)
const router = useRouter()
const notifications = useNotificationStore()

async function load() {
  try {
    summary.value = await dashboardSummary()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

function openDoc(id) {
  router.push({ name: 'document-detail', params: { id } })
}

onMounted(load)
</script>

<template>
  <div class="container" v-if="summary">
    <h1>Admin dashboard</h1>

    <div class="stat-grid">
      <div class="stat-tile">
        <div class="value">{{ summary.total_documents }}</div>
        <div class="label">Total documents</div>
      </div>
      <div class="stat-tile" v-for="(count, status) in summary.counts_by_status" :key="status">
        <div class="value">{{ count }}</div>
        <div class="label">{{ status.replace('_', ' ') }}</div>
      </div>
    </div>

    <div class="card">
      <h3>Documents currently in review</h3>
      <table v-if="summary.pending_reviews.length">
        <thead><tr><th>Document</th><th>Owner</th><th>Waiting on</th><th></th></tr></thead>
        <tbody>
          <tr v-for="d in summary.pending_reviews" :key="d.id">
            <td>{{ d.code }} — {{ d.title }}</td>
            <td class="muted">{{ d.owner }}</td>
            <td>{{ d.pending_reviewers.join(', ') }}</td>
            <td><button class="btn btn-sm" @click="openDoc(d.id)">Open</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Nothing is currently in review.</p>
    </div>

    <div class="card">
      <h3>Overdue reviews (pending &gt; 5 days)</h3>
      <table v-if="summary.overdue_reviews.length">
        <thead><tr><th>Document</th><th>Reviewer</th><th>Assigned</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in summary.overdue_reviews" :key="r.id">
            <td>{{ r.document_code }} — {{ r.document_title }}</td>
            <td>{{ r.reviewer }}</td>
            <td class="muted">{{ new Date(r.assigned_at).toLocaleDateString() }}</td>
            <td><button class="btn btn-sm" @click="openDoc(r.document_id)">Open</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">No overdue reviews.</p>
    </div>

    <div class="card">
      <h3>Permissions expiring within 7 days</h3>
      <table v-if="summary.expiring_permissions.length">
        <thead><tr><th>Document</th><th>Grantee</th><th>Expires</th><th></th></tr></thead>
        <tbody>
          <tr v-for="p in summary.expiring_permissions" :key="p.id">
            <td>{{ p.document_code }}</td>
            <td>{{ p.grantee }}</td>
            <td class="muted">{{ new Date(p.expires_at).toLocaleString() }}</td>
            <td><button class="btn btn-sm" @click="openDoc(p.document_id)">Open</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Nothing expiring soon.</p>
    </div>

    <div class="card">
      <h3>Recent activity</h3>
      <table>
        <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Document</th></tr></thead>
        <tbody>
          <tr v-for="e in summary.recent_activity" :key="e.id">
            <td class="muted">{{ new Date(e.timestamp).toLocaleString() }}</td>
            <td>{{ e.actor_username || 'system' }}</td>
            <td>{{ e.action }}</td>
            <td class="muted">{{ e.document_code || e.target_repr }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
