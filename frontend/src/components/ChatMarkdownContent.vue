<script lang="ts">
import MarkdownIt from 'markdown-it'

// 禁止原始 HTML 与图片请求，v-html 只接收解析器转义后的输出。
const markdown = new MarkdownIt({ html: false, breaks: true }).disable('image')

markdown.renderer.rules.table_open = () =>
  '<div class="ai-markdown-table" role="region" aria-label="表格，可横向滚动" tabindex="0"><table>\n'
markdown.renderer.rules.table_close = () => '</table></div>\n'
markdown.renderer.rules.link_open = (tokens, index, options, _env, renderer) => {
  tokens[index]?.attrSet('target', '_blank')
  tokens[index]?.attrSet('rel', 'noopener noreferrer')
  return renderer.renderToken(tokens, index, options)
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ content: string }>()
const rendered = computed(() => markdown.render(props.content))
</script>

<template>
  <div class="ai-markdown" v-html="rendered" />
</template>
