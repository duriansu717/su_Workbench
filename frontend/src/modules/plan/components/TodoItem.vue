<script setup lang="ts">
import { Delete, Edit } from '@element-plus/icons-vue'

import { PRIORITY_LABEL, PRIORITY_TAG } from '../api'
import type { Todo } from '../api'
import { isToday, shortDate } from '../date'

/**
 * 一条待办。日期视图和收集箱两处共用。
 *
 * 自己不调接口，只往上抛事件 —— 数据由父组件统一管，
 * 免得两个列表各拿一份状态、互相不同步。
 */
defineProps<{ todo: Todo }>()

const emit = defineEmits<{
  toggle: [todo: Todo]
  edit: [todo: Todo]
  remove: [todo: Todo]
}>()
</script>

<template>
  <div class="todo" :class="{ 'is-done': todo.is_done }">
    <el-checkbox
      :model-value="todo.is_done"
      class="check"
      @change="emit('toggle', todo)"
    />

    <el-tag size="small" :type="PRIORITY_TAG[todo.priority]" class="prio" disable-transitions>
      {{ PRIORITY_LABEL[todo.priority] }}
    </el-tag>

    <div class="body" @click="emit('edit', todo)">
      <div class="title">{{ todo.title }}</div>
      <div v-if="todo.note" class="note">{{ todo.note }}</div>
    </div>

    <span
      v-if="todo.planned_date"
      class="date"
      :class="{ today: isToday(todo.planned_date) }"
    >
      {{ isToday(todo.planned_date) ? '今天' : shortDate(todo.planned_date) }}
    </span>

    <el-button :icon="Edit" link class="act" @click="emit('edit', todo)" />
    <el-button :icon="Delete" link class="act" @click="emit('remove', todo)" />
  </div>
</template>

<style scoped>
.todo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.todo:last-child {
  border-bottom: none;
}

.check {
  flex: none;
}

.prio {
  flex: none;
  width: 30px;
  justify-content: center;
}

.body {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.title {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.is-done .title {
  color: var(--el-text-color-placeholder);
  text-decoration: line-through;
}

.note {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.date {
  flex: none;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.date.today {
  color: var(--el-color-primary);
  font-weight: 600;
}

.act {
  flex: none;
}

@media (max-width: 768px) {
  /* 手机端缩小间距，把宽度让给正文 */
  .todo {
    gap: 4px;
  }

  .prio {
    display: none;
  }
}
</style>
