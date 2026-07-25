<script setup>
import { computed, ref } from 'vue'
import { exportBackup, importBackup } from '../api/backup'
import { useNotificationStore } from '../stores/notifications'
import { extractErrorMessage } from '../utils/errors'

const notifications = useNotificationStore()

const exporting = ref(false)
const restoring = ref(false)
const pendingFile = ref(null)
const confirmText = ref('')
const confirmOpen = ref(false)
const lastResult = ref(null)
const error = ref('')

const CONFIRM_PHRASE = 'RESTORE'
const canConfirm = computed(() => confirmText.value.trim() === CONFIRM_PHRASE)

async function download() {
  exporting.value = true
  error.value = ''
  try {
    const filename = await exportBackup()
    notifications.push(`Backup downloaded: ${filename}`)
  } catch (e) {
    notifications.push(extractErrorMessage(e), 'error')
  } finally {
    exporting.value = false
  }
}

function onFileChange(e) {
  pendingFile.value = e.target.files[0] || null
  lastResult.value = null
  error.value = ''
}

function openConfirm() {
  if (!pendingFile.value) return
  confirmText.value = ''
  confirmOpen.value = true
}

function closeConfirm() {
  confirmOpen.value = false
}

async function confirmRestore() {
  if (!canConfirm.value || !pendingFile.value) return
  restoring.value = true
  error.value = ''
  try {
    const result = await importBackup(pendingFile.value)
    lastResult.value = result
    confirmOpen.value = false
    pendingFile.value = null
    notifications.push('Backup restored. Everything since that backup was taken has been replaced.')
  } catch (e) {
    error.value = extractErrorMessage(e)
  } finally {
    restoring.value = false
  }
}
</script>

<template>
  <div class="container">
    <h1>Backup &amp; restore</h1>

    <div class="card">
      <h3>Create a backup</h3>
      <p class="muted">
        Downloads one archive containing every document record, permission grant, review, and
        audit entry, plus the actual uploaded files - everything needed to fully rebuild the
        system elsewhere.
      </p>
      <button class="btn btn-primary" :disabled="exporting" @click="download">
        {{ exporting ? 'Preparing archive…' : 'Download backup' }}
      </button>
    </div>

    <div class="card">
      <h3>Restore from a backup</h3>
      <p class="muted">
        Restoring replaces <strong>everything</strong> currently in the system - every document,
        version, permission, review, and audit entry, plus all files - with exactly what's in the
        archive. Anything created since that backup was taken is gone afterwards. This cannot be
        undone from within the app.
      </p>

      <div class="field">
        <label for="restore-file">Backup archive (.zip)</label>
        <input id="restore-file" type="file" accept=".zip" @change="onFileChange" />
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>

      <button class="btn btn-danger" :disabled="!pendingFile || restoring" @click="openConfirm">
        Restore from backup…
      </button>

      <div v-if="lastResult" class="stack" style="margin-top: 14px">
        <p class="muted" style="margin: 0">Last restore, from an archive created {{ new Date(lastResult.manifest.created_at).toLocaleString() }}:</p>
        <table>
          <thead><tr><th>Record type</th><th>Restored</th></tr></thead>
          <tbody>
            <tr v-for="(count, label) in lastResult.counts" :key="label">
              <td>{{ label }}</td>
              <td>{{ count }}</td>
            </tr>
            <tr><td>Files</td><td>{{ lastResult.file_count }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="modal-backdrop" v-if="confirmOpen" @click.self="closeConfirm">
      <div class="modal">
        <div class="flex-between">
          <h2>Confirm restore</h2>
          <button class="btn btn-sm" @click="closeConfirm">✕</button>
        </div>
        <p>
          This will permanently delete all current documents, permissions, reviews, audit
          history, and files, and replace them with the contents of
          <strong>{{ pendingFile?.name }}</strong>. There is no undo.
        </p>
        <p class="muted" style="font-size: 0.85rem">
          If your own account isn't in that backup, you'll be signed out once it finishes.
        </p>
        <div class="field">
          <label for="confirm-phrase">Type {{ CONFIRM_PHRASE }} to confirm</label>
          <input id="confirm-phrase" v-model="confirmText" style="width: 100%" autocomplete="off" />
        </div>
        <p v-if="error" class="error-text">{{ error }}</p>
        <div class="flex-row">
          <button class="btn btn-danger" :disabled="!canConfirm || restoring" @click="confirmRestore">
            {{ restoring ? 'Restoring…' : 'Permanently restore' }}
          </button>
          <button class="btn" @click="closeConfirm">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>
