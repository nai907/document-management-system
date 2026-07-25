<script setup>
import { ref } from 'vue'
import { createDocument } from '../api/documents'
import { extractErrorMessage } from '../utils/errors'

const props = defineProps({
  folders: { type: Array, default: () => [] },
  defaultFolderId: { type: [Number, String, null], default: null },
})
const emit = defineEmits(['close', 'created'])

const title = ref('')
const description = ref('')
const folder = ref(props.defaultFolderId || '')
const tagsInput = ref('')
const file = ref(null)
const error = ref('')
const loading = ref(false)

function onFileChange(e) {
  file.value = e.target.files[0] || null
}

async function submit() {
  error.value = ''
  if (!file.value) {
    error.value = 'Choose a file to upload.'
    return
  }
  loading.value = true
  try {
    const doc = await createDocument({
      title: title.value,
      description: description.value,
      folder: folder.value || null,
      tagNames: tagsInput.value.split(',').map((t) => t.trim()).filter(Boolean),
      file: file.value,
    })
    emit('created', doc)
    emit('close')
  } catch (e) {
    error.value = extractErrorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal">
      <div class="flex-between">
        <h2>Upload document</h2>
        <button class="btn btn-sm" @click="$emit('close')">✕</button>
      </div>

      <form @submit.prevent="submit">
        <div class="field">
          <label for="up-title">Title</label>
          <input id="up-title" v-model="title" required style="width: 100%" />
          <p class="muted" style="font-size: 0.78rem; margin-top: 4px">Must be unique — no two documents can share a title.</p>
        </div>
        <div class="field">
          <label for="up-desc">Description</label>
          <textarea id="up-desc" v-model="description" rows="2" style="width: 100%"></textarea>
        </div>
        <div class="field">
          <label for="up-folder">Folder</label>
          <select id="up-folder" v-model="folder" style="width: 100%">
            <option value="">(none)</option>
            <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="up-tags">Tags (comma separated)</label>
          <input id="up-tags" v-model="tagsInput" style="width: 100%" />
        </div>
        <div class="field">
          <label for="up-file">File</label>
          <input id="up-file" type="file" accept=".pdf,.txt,.xlsx,.xls" required @change="onFileChange" />
          <p class="muted" style="font-size: 0.78rem; margin-top: 4px">Allowed types: PDF, .txt, .xlsx, .xls</p>
        </div>
        <p v-if="error" class="error-text">{{ error }}</p>
        <div class="flex-row">
          <button class="btn btn-primary" type="submit" :disabled="loading">
            {{ loading ? 'Uploading…' : 'Upload' }}
          </button>
          <button class="btn" type="button" @click="$emit('close')">Cancel</button>
        </div>
      </form>
    </div>
  </div>
</template>
