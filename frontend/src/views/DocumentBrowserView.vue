<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { folderTree, listDocuments, listFolders } from '../api/documents'
import FolderTreeNode from '../components/FolderTreeNode.vue'
import UploadModal from '../components/UploadModal.vue'
import { useNotificationStore } from '../stores/notifications'
import { extractErrorMessage } from '../utils/errors'

const router = useRouter()
const notifications = useNotificationStore()

const documents = ref([])
const folders = ref([])
const tree = ref([])
const query = ref('')
const statusFilter = ref('')
const selectedFolder = ref(null)
const showUpload = ref(false)
const loading = ref(false)

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'in_review', label: 'In review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

async function loadDocuments() {
  loading.value = true
  try {
    const params = {}
    if (query.value) params.q = query.value
    if (statusFilter.value) params.status = statusFilter.value
    if (selectedFolder.value) params.folder = selectedFolder.value
    const data = await listDocuments(params)
    documents.value = data.results ?? data
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  } finally {
    loading.value = false
  }
}

async function loadFolders() {
  try {
    const data = await listFolders()
    folders.value = data.results ?? data
    tree.value = await folderTree()
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  }
}

function selectFolder(id) {
  selectedFolder.value = selectedFolder.value === id ? null : id
}

function openDocument(doc) {
  router.push({ name: 'document-detail', params: { id: doc.id } })
}

function onCreated() {
  loadDocuments()
  loadFolders()
}

let debounceHandle
watch(query, () => {
  clearTimeout(debounceHandle)
  debounceHandle = setTimeout(loadDocuments, 300)
})
watch([statusFilter, selectedFolder], loadDocuments)

onMounted(() => {
  loadDocuments()
  loadFolders()
})
</script>

<template>
  <div class="container">
    <div class="flex-between">
      <h1>Documents</h1>
      <button class="btn btn-primary" @click="showUpload = true">+ Upload document</button>
    </div>

    <div style="display: grid; grid-template-columns: 220px 1fr; gap: 20px; align-items: start">
      <aside class="card">
        <h3>Folders</h3>
        <ul style="list-style: none; padding: 0; margin: 0">
          <li>
            <a href="#" :class="{ active: !selectedFolder }" @click.prevent="selectFolder(null)"
               style="display:block;padding:4px 8px;border-radius:6px;text-decoration:none;font-size:0.88rem"
               :style="!selectedFolder ? 'background:var(--accent-bg);color:var(--accent);font-weight:600' : 'color:var(--text)'">
              All documents
            </a>
          </li>
          <FolderTreeNode
            v-for="node in tree"
            :key="node.id"
            :node="node"
            :selected-id="selectedFolder"
            @select="selectFolder"
          />
        </ul>
      </aside>

      <div>
        <div class="card flex-row">
          <input v-model="query" placeholder="Search title, description, code, tags…" style="flex: 1" />
          <select v-model="statusFilter">
            <option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </div>

        <div class="card">
          <table v-if="documents.length">
            <thead>
              <tr>
                <th>Code</th>
                <th>Title</th>
                <th>Folder</th>
                <th>Owner</th>
                <th>Status</th>
                <th>Version</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="doc in documents" :key="doc.id" style="cursor: pointer" @click="openDocument(doc)">
                <td class="muted">{{ doc.code }}</td>
                <td>{{ doc.title }}</td>
                <td class="muted">{{ doc.folder_name || '—' }}</td>
                <td class="muted">{{ doc.owner_username }}</td>
                <td><span class="badge" :class="`badge-${doc.status}`">{{ doc.status }}</span></td>
                <td class="muted">v{{ doc.latest_version_number || '—' }}</td>
                <td class="muted">{{ new Date(doc.updated_at).toLocaleDateString() }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else-if="!loading" class="muted">No documents found. Try adjusting filters or upload a new one.</p>
        </div>
      </div>
    </div>

    <UploadModal
      v-if="showUpload"
      :folders="folders"
      :default-folder-id="selectedFolder"
      @close="showUpload = false"
      @created="onCreated"
    />
  </div>
</template>
