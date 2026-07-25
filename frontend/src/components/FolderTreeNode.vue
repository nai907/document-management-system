<script setup>
defineProps({
  node: { type: Object, required: true },
  selectedId: { type: [Number, String, null], default: null },
})
defineEmits(['select'])
</script>

<template>
  <li>
    <a
      href="#"
      :class="{ active: selectedId === node.id }"
      @click.prevent="$emit('select', node.id)"
    >
      {{ node.name }}
    </a>
    <ul v-if="node.children && node.children.length">
      <FolderTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :selected-id="selectedId"
        @select="$emit('select', $event)"
      />
    </ul>
  </li>
</template>

<style scoped>
ul {
  list-style: none;
  padding-left: 14px;
  margin: 2px 0;
}
li > a {
  display: block;
  padding: 4px 8px;
  border-radius: 6px;
  color: var(--text);
  text-decoration: none;
  font-size: 0.88rem;
}
li > a:hover {
  background: var(--bg-subtle);
}
li > a.active {
  background: var(--accent-bg);
  color: var(--accent);
  font-weight: 600;
}
</style>
