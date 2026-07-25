import { defineStore } from 'pinia'

let nextId = 1

export const useNotificationStore = defineStore('notifications', {
  state: () => ({
    items: [],
  }),
  actions: {
    push(message, type = 'info') {
      const id = nextId++
      this.items.push({ id, message, type })
      setTimeout(() => this.dismiss(id), 5000)
    },
    dismiss(id) {
      this.items = this.items.filter((n) => n.id !== id)
    },
  },
})
