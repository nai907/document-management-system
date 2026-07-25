<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listMyReviews } from '../api/reviews'
import { useNotificationStore } from '../stores/notifications'
import { extractErrorMessage } from '../utils/errors'

const reviews = ref([])
const router = useRouter()
const notifications = useNotificationStore()

async function load() {
  try {
    const data = await listMyReviews()
    reviews.value = data.results ?? data
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

function open(review) {
  router.push({ name: 'document-detail', params: { id: review.document } })
}

function daysAgo(dateStr) {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000)
}

onMounted(load)
</script>

<template>
  <div class="container">
    <h1>My pending reviews</h1>
    <div class="card">
      <table v-if="reviews.length">
        <thead><tr><th>Document</th><th>Assigned</th><th>Waiting</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in reviews" :key="r.id">
            <td>{{ r.document_code }} — {{ r.document_title }}</td>
            <td class="muted">{{ new Date(r.assigned_at).toLocaleDateString() }}</td>
            <td>
              <span class="badge" :class="daysAgo(r.assigned_at) >= 5 ? 'badge-rejected' : 'badge-in_review'">
                {{ daysAgo(r.assigned_at) }} day(s)
              </span>
            </td>
            <td><button class="btn btn-sm" @click="open(r)">Open</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Nothing waiting on you right now.</p>
    </div>
  </div>
</template>
