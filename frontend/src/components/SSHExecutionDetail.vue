<script setup lang="ts">
import { ElTag } from 'element-plus'
import { executionFailure, executionLabel, executionTag, executionTime } from '@/components/sshExecutionDisplay'
import type { ExecutionDetail } from '@/types/sshExecutions'

defineProps<{ detail: ExecutionDetail; disconnected: boolean }>()
</script>

<template>
  <div class="ssh-execution-detail">
    <div class="ssh-execution-detail-head"><h2>{{ detail.name }}</h2><ElTag :type="executionTag(detail.status)" size="small">{{ executionLabel(detail.status) }}</ElTag></div>
    <div class="ssh-execution-meta"><span>主机：{{ detail.host_name }}（{{ detail.address }}）</span><span>创建：{{ executionTime(detail.created_at) }}</span><span v-if="detail.finished_at">结束：{{ executionTime(detail.finished_at) }}</span></div>
    <p v-if="executionFailure(detail.error_code)" class="ssh-field-hint">停止原因：{{ executionFailure(detail.error_code) }}</p>
    <p v-if="disconnected" class="ssh-execution-pending">实时输出未完整接收。</p>
    <div v-for="item in detail.steps" :key="item.id" class="ssh-execution-step-result">
      <div class="ssh-execution-detail-head"><h3>{{ item.position + 1 }}. {{ item.name }}</h3><ElTag :type="executionTag(item.status)" size="small">{{ executionLabel(item.status) }}</ElTag><span>退出码：{{ item.exit_status === null ? '未取得' : item.exit_status }}</span></div>
      <div class="ssh-execution-meta"><span v-if="item.started_at">开始：{{ executionTime(item.started_at) }}</span><span v-if="item.finished_at">结束：{{ executionTime(item.finished_at) }}</span></div>
      <div class="ssh-execution-output"><h4>命令</h4><pre>{{ item.command }}</pre></div>
      <div class="ssh-execution-output"><h4>标准输出</h4><pre>{{ item.stdout || '暂无输出' }}</pre></div>
      <div class="ssh-execution-output"><h4>错误输出</h4><pre>{{ item.stderr || '暂无输出' }}</pre></div>
    </div>
  </div>
</template>
