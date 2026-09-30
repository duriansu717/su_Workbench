<script setup lang="ts">
import { ArrowLeft, ArrowRight, Plus } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import planApi, { PRIORITY } from '../api'
import type { Todo } from '../api'
import { rangeLabel, rangeOf, shift, type CalendarView } from '../date'
import TodoItem from '../components/TodoItem.vue'

const view = ref<CalendarView>('day')
const anchor = ref(new Date())

const todos = ref<Todo[]>([])
const inbox = ref<Todo[]>([])
const loading = ref(false)

const quickTitle = ref('')
const quickNoDate = ref(false)

const editing = ref(false)
const saving = ref(false)
const form = reactive({
  id: 0,
  title: '',
  note: '',
  planned_date: null as string | null,
  priority: PRIORITY.MEDIUM as number,
})

/** 当前视图要查的日期区间。日 / 周 / 月只是这个区间不同。 */
const range = computed(() => rangeOf(view.value, anchor.value))
const label = computed(() => rangeLabel(view.value, anchor.value))

async function load(): Promise<void> {
  loading.value = true
  try {
    const [inRange, box] = await Promise.all([
      planApi.todos.list({ from: range.value[0], to: range.value[1] }),
      planApi.todos.list({ unscheduled: true }),
    ])
    todos.value = inRange.data
    inbox.value = box.data
  } catch {
    ElMessage.error('加载待办失败')
  } finally {
    loading.value = false
  }
}

function turn(delta: number): void {
  anchor.value = shift(view.value, anchor.value, delta)
}

function goToday(): void {
  anchor.value = new Date()
}

async function quickAdd(): Promise<void> {
  const title = quickTitle.value.trim()
  if (!title) return

  try {
    await planApi.todos.create({
      title,
      // 不排日期就进收集箱；排的话落在当前区间的第一天
      planned_date: quickNoDate.value ? null : range.value[0],
    })
    quickTitle.value = ''
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '添加失败')
  }
}

async function toggle(todo: Todo): Promise<void> {
  try {
    // 只传 is_done，其余字段一个字都不动 —— 这正是 PATCH 存在的意义。
    // done_at 由服务端根据它自动写入或清空，前端不碰。
    await planApi.todos.update(todo.id, { is_done: !todo.is_done })
    await load()
  } catch {
    ElMessage.error('操作失败')
  }
}

function openEdit(todo: Todo): void {
  form.id = todo.id
  form.title = todo.title
  form.note = todo.note ?? ''
  form.planned_date = todo.planned_date
  form.priority = todo.priority
  editing.value = true
}

async function saveEdit(): Promise<void> {
  if (!form.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }

  saving.value = true
  try {
    await planApi.todos.update(form.id, {
      title: form.title.trim(),
      note: form.note.trim() || null,
      // 日期清空 = 丢回收集箱
      planned_date: form.planned_date,
      priority: form.priority,
    })
    editing.value = false
    ElMessage.success('已保存')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(todo: Todo): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除「${todo.title}」？`, '删除待办', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  await planApi.todos.remove(todo.id)
  ElMessage.success('已删除')
  await load()
}

// 切换视图或翻页时重新拉数据。
// anchor 是整体替换的（shift 每次返回新 Date），所以不需要 deep。
watch([view, anchor], load)

onMounted(load)
</script>

<template>
  <div class="plan">
    <div class="head">
      <h1 class="title">计划</h1>
      <el-radio-group v-model="view">
        <el-radio-button value="day">日</el-radio-button>
        <el-radio-button value="week">周</el-radio-button>
        <el-radio-button value="month">月</el-radio-button>
      </el-radio-group>
    </div>

    <div class="nav">
      <el-button :icon="ArrowLeft" circle size="small" @click="turn(-1)" />
      <span class="label">{{ label }}</span>
      <el-button :icon="ArrowRight" circle size="small" @click="turn(1)" />
      <el-button link @click="goToday">回到今天</el-button>
    </div>

    <div class="quick">
      <el-input
        v-model="quickTitle"
        placeholder="记一件要做的事，回车即可添加"
        maxlength="200"
        @keyup.enter="quickAdd"
      />
      <el-checkbox v-model="quickNoDate">不排日期</el-checkbox>
      <el-button type="primary" :icon="Plus" @click="quickAdd">添加</el-button>
    </div>

    <el-card class="panel" v-loading="loading">
      <el-empty
        v-if="!loading && todos.length === 0"
        description="这个时间段还没有待办"
        :image-size="60"
      />
      <TodoItem
        v-for="t in todos"
        :key="t.id"
        :todo="t"
        @toggle="toggle"
        @edit="openEdit"
        @remove="remove"
      />
    </el-card>

    <el-card class="panel">
      <template #header>
        <div class="inbox-head">
          <span>收集箱</span>
          <span class="hint">先记下来、还没安排日期的</span>
        </div>
      </template>
      <el-empty
        v-if="inbox.length === 0"
        description="收集箱是空的"
        :image-size="50"
      />
      <TodoItem
        v-for="t in inbox"
        :key="t.id"
        :todo="t"
        @toggle="toggle"
        @edit="openEdit"
        @remove="remove"
      />
    </el-card>

    <el-dialog v-model="editing" title="编辑待办" width="460px">
      <el-form label-width="60px">
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="200" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            v-model="form.planned_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="不选就留在收集箱"
            clearable
            class="full"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="form.priority">
            <el-radio-button :value="1">高</el-radio-button>
            <el-radio-button :value="2">中</el-radio-button>
            <el-radio-button :value="3">低</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editing = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.plan {
  max-width: 760px;
  margin: 0 auto;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}

.title {
  margin: 0;
  font-size: 22px;
}

.nav {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.label {
  font-size: 15px;
  font-weight: 600;
}

.quick {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.panel {
  margin-bottom: 16px;
}

.inbox-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.hint {
  font-size: 12px;
  font-weight: normal;
  color: var(--el-text-color-secondary);
}

.full {
  width: 100%;
}

@media (max-width: 768px) {
  .quick {
    flex-wrap: wrap;
  }

  .quick :deep(.el-input) {
    width: 100%;
  }
}
</style>
