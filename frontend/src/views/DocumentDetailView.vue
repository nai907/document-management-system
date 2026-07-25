<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listUsers } from '../api/auth'
import {
  deleteDocument,
  downloadFile,
  getDocument,
  getDocumentAudit,
  grantPermission,
  listFolders,
  revokePermission,
  reviewDecision,
  submitForReview,
  updateDocument,
  uploadVersion,
} from '../api/documents'
import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notifications'
import { extractErrorMessage } from '../utils/errors'

const props = defineProps({ id: { type: [String, Number], required: true } })
const auth = useAuthStore()
const notifications = useNotificationStore()
const router = useRouter()

const doc = ref(null)
const auditEntries = ref([])
const users = ref([])
const folders = ref([])
const tab = ref('overview')

const newVersionFile = ref(null)
const changeNote = ref('')
const uploadingVersion = ref(false)

const grantUserId = ref('')
const grantCanView = ref(true)
const grantCanEdit = ref(false)
const grantCanApprove = ref(false)
const grantCanDownload = ref(true)
const grantExpiresAt = ref('')

const reviewerIds = ref([])
const decisionComment = ref('')

const isOwnerOrAdmin = computed(
  () => doc.value && auth.user && (auth.isAdmin || doc.value.owner === auth.user.id)
)

const pendingReviewers = computed(() =>
  (doc.value?.review_assignments || [])
    .filter((a) => a.status === 'pending')
    .map((a) => a.reviewer_username)
)

async function loadAll() {
  try {
    doc.value = await getDocument(props.id)
    auditEntries.value = await getDocumentAudit(props.id)
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function loadUsersAndFolders() {
  try {
    const data = await listUsers()
    users.value = data.results ?? data
    const folderData = await listFolders()
    folders.value = folderData.results ?? folderData
  } catch {
    // non-owners without list access simply won't see reviewer/grantee pickers
  }
}

function userLabel(userId) {
  const u = users.value.find((x) => x.id === userId)
  return u ? u.username : `#${userId}`
}

function onVersionFileChange(e) {
  newVersionFile.value = e.target.files[0] || null
}

async function submitNewVersion() {
  if (!newVersionFile.value) return
  uploadingVersion.value = true
  try {
    await uploadVersion(props.id, newVersionFile.value, changeNote.value)
    changeNote.value = ''
    newVersionFile.value = null
    notifications.push('New version uploaded.')
    await loadAll()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  } finally {
    uploadingVersion.value = false
  }
}

async function doDownload(versionNumber) {
  try {
    await downloadFile(props.id, versionNumber, `${doc.value.code}_v${versionNumber}`)
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function doGrant() {
  try {
    await grantPermission(props.id, {
      user: grantUserId.value,
      can_view: grantCanView.value,
      can_edit: grantCanEdit.value,
      can_approve: grantCanApprove.value,
      can_download: grantCanDownload.value,
      expires_at: grantExpiresAt.value || null,
    })
    grantUserId.value = ''
    grantExpiresAt.value = ''
    notifications.push('Permission granted.')
    await loadAll()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function doRevoke(permId) {
  try {
    await revokePermission(props.id, permId)
    notifications.push('Permission revoked.')
    await loadAll()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function doSubmitForReview() {
  if (!reviewerIds.value.length) return
  try {
    await submitForReview(props.id, reviewerIds.value)
    notifications.push('Submitted for review.')
    reviewerIds.value = []
    await loadAll()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function doDecision(decision) {
  try {
    await reviewDecision(props.id, decision, decisionComment.value)
    decisionComment.value = ''
    notifications.push(`Review ${decision}d.`)
    await loadAll()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function doRename() {
  const title = window.prompt('New title', doc.value.title)
  if (!title || title === doc.value.title) return
  try {
    await updateDocument(props.id, { title })
    await loadAll()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

async function doDelete() {
  if (!window.confirm('Delete this document permanently?')) return
  try {
    await deleteDocument(props.id)
    notifications.push('Document deleted.')
    router.push({ name: 'browser' })
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

onMounted(() => {
  loadAll()
  loadUsersAndFolders()
})
</script>

<template>
  <div class="container" v-if="doc">
    <div class="flex-between">
      <div>
        <p class="muted" style="margin-bottom: 2px">{{ doc.code }}</p>
        <h1 style="margin-bottom: 4px">{{ doc.title }}</h1>
        <span class="badge" :class="`badge-${doc.status}`">{{ doc.status }}</span>
      </div>
      <div class="flex-row" v-if="isOwnerOrAdmin">
        <button class="btn btn-sm" @click="doRename">Rename</button>
        <button class="btn btn-sm btn-danger" @click="doDelete">Delete</button>
      </div>
    </div>
    <p class="muted">{{ doc.description }}</p>

    <div class="flex-row" style="margin: 16px 0; border-bottom: 1px solid var(--border)">
      <button
        v-for="t in ['overview', 'versions', 'permissions', 'review', 'history']"
        :key="t"
        class="btn btn-sm"
        :style="tab === t ? 'border-color:var(--accent);color:var(--accent)' : 'border:none'"
        @click="tab = t"
      >
        {{ t }}
      </button>
    </div>

    <!-- Overview -->
    <div v-if="tab === 'overview'" class="card">
      <p><strong>Owner:</strong> {{ doc.owner_username }}</p>
      <p><strong>Folder:</strong> {{ doc.folder_name || '—' }}</p>
      <p><strong>Tags:</strong> {{ doc.tags.map((t) => t.name).join(', ') || '—' }}</p>
      <p><strong>Latest version:</strong> v{{ doc.latest_version_number || '—' }}
        <button v-if="doc.latest_version_number" class="btn btn-sm" @click="doDownload()">Download latest</button>
      </p>
    </div>

    <!-- Versions -->
    <div v-if="tab === 'versions'" class="card">
      <h3>Version history</h3>
      <table>
        <thead>
          <tr><th>Version</th><th>Uploaded by</th><th>Date</th><th>Note</th><th>Checksum</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="v in doc.versions" :key="v.id">
            <td>v{{ v.version_number }}</td>
            <td class="muted">{{ v.uploaded_by_username }}</td>
            <td class="muted">{{ new Date(v.uploaded_at).toLocaleString() }}</td>
            <td class="muted">{{ v.change_note || '—' }}</td>
            <td class="muted" style="font-family: monospace; font-size: 0.75rem">{{ v.checksum.slice(0, 10) }}</td>
            <td><button class="btn btn-sm" @click="doDownload(v.version_number)">Download</button></td>
          </tr>
        </tbody>
      </table>

      <div v-if="isOwnerOrAdmin" style="margin-top: 16px">
        <h3>Upload new version</h3>
        <div class="field">
          <input type="file" accept=".pdf,.txt,.xlsx,.xls" @change="onVersionFileChange" />
          <p class="muted" style="font-size: 0.78rem; margin-top: 4px">Allowed types: PDF, .txt, .xlsx, .xls</p>
        </div>
        <div class="field"><input v-model="changeNote" placeholder="Change note (optional)" style="width: 100%" /></div>
        <button class="btn btn-primary btn-sm" :disabled="uploadingVersion" @click="submitNewVersion">
          {{ uploadingVersion ? 'Uploading…' : 'Upload version' }}
        </button>
      </div>
    </div>

    <!-- Permissions -->
    <div v-if="tab === 'permissions'" class="card">
      <h3>Who can access this document</h3>
      <table>
        <thead>
          <tr><th>Grantee</th><th>View</th><th>Edit</th><th>Approve</th><th>Download</th><th>Expires</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="p in doc.permissions" :key="p.id">
            <td>{{ p.user_username || `group:${p.group_name}` }}</td>
            <td>{{ p.can_view ? '✓' : '' }}</td>
            <td>{{ p.can_edit ? '✓' : '' }}</td>
            <td>{{ p.can_approve ? '✓' : '' }}</td>
            <td>{{ p.can_download ? '✓' : '' }}</td>
            <td class="muted">{{ p.expires_at ? new Date(p.expires_at).toLocaleDateString() : 'never' }}</td>
            <td>
              <button v-if="auth.isAdmin" class="btn btn-sm btn-danger" @click="doRevoke(p.id)">Revoke</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="isOwnerOrAdmin && users.length" style="margin-top: 16px">
        <h3>Grant access</h3>
        <div class="field">
          <label>User</label>
          <select v-model="grantUserId" style="width: 100%">
            <option value="">Select a user…</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
          </select>
        </div>
        <div class="flex-row" style="margin-bottom: 12px">
          <label class="flex-row"><input v-model="grantCanView" type="checkbox" style="width: auto" /> View</label>
          <label class="flex-row"><input v-model="grantCanEdit" type="checkbox" style="width: auto" /> Edit</label>
          <label class="flex-row"><input v-model="grantCanApprove" type="checkbox" style="width: auto" /> Approve</label>
          <label class="flex-row"><input v-model="grantCanDownload" type="checkbox" style="width: auto" /> Download</label>
        </div>
        <div class="field">
          <label>Expires at (optional)</label>
          <input v-model="grantExpiresAt" type="datetime-local" />
        </div>
        <button class="btn btn-primary btn-sm" :disabled="!grantUserId" @click="doGrant">Grant</button>
      </div>
    </div>

    <!-- Review -->
    <div v-if="tab === 'review'" class="card">
      <h3>Review assignments</h3>

      <div v-if="doc.review_assignments && doc.review_assignments.length" style="margin-bottom: 16px">
        <p v-if="pendingReviewers.length" class="muted">
          Still waiting on: <strong>{{ pendingReviewers.join(', ') }}</strong>
        </p>
        <p v-else class="muted">No reviewers are currently pending on this version.</p>
        <table>
          <thead>
            <tr><th>Reviewer</th><th>Status</th><th>Assigned</th><th>Decided</th><th>Comment</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in doc.review_assignments" :key="a.id">
              <td>{{ a.reviewer_username }}</td>
              <td><span class="badge" :class="`badge-${a.status === 'pending' ? 'in_review' : a.status}`">{{ a.status }}</span></td>
              <td class="muted">{{ new Date(a.assigned_at).toLocaleString() }}</td>
              <td class="muted">{{ a.decided_at ? new Date(a.decided_at).toLocaleString() : '—' }}</td>
              <td class="muted">{{ a.comment || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">This document hasn't been submitted for review yet.</p>

      <div v-if="isOwnerOrAdmin && users.length" style="margin-bottom: 16px">
        <label>Assign reviewers</label>
        <select v-model="reviewerIds" multiple style="width: 100%; min-height: 90px">
          <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
        </select>
        <button class="btn btn-primary btn-sm" style="margin-top: 8px" :disabled="!reviewerIds.length" @click="doSubmitForReview">
          Submit for review
        </button>
      </div>

      <div class="field">
        <label>Comment (for approve/reject decision)</label>
        <input v-model="decisionComment" style="width: 100%" />
      </div>
      <div class="flex-row">
        <button class="btn btn-primary btn-sm" @click="doDecision('approve')">Approve (as reviewer)</button>
        <button class="btn btn-danger btn-sm" @click="doDecision('reject')">Reject (as reviewer)</button>
      </div>
    </div>

    <!-- History -->
    <div v-if="tab === 'history'" class="card">
      <h3>Document history</h3>
      <table>
        <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Details</th></tr></thead>
        <tbody>
          <tr v-for="e in auditEntries" :key="e.id">
            <td class="muted">{{ new Date(e.timestamp).toLocaleString() }}</td>
            <td>{{ e.actor_username || 'system' }}</td>
            <td>{{ e.action }}</td>
            <td class="muted" style="font-size: 0.8rem">{{ JSON.stringify(e.metadata) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
