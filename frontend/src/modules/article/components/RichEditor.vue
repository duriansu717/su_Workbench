<script setup lang="ts">
import '@wangeditor/editor/dist/css/style.css'

import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, shallowRef } from 'vue'

import articleApi from '../api'

/**
 * 富文本编辑器封装。
 *
 * 图片上传**不用编辑器内置的上传**，而是走 customUpload 调我们自己的接口 ——
 * wangEditor 默认约定响应是 `{errno: 0, data: {url}}`，而我们的接口返回
 * `{url, size}`。用 customUpload 完全绕开它的解析，顺便还能复用 api.ts 里
 * 已经配好鉴权和错误处理的 axios 实例。
 */
const modelValue = defineModel<string>({ required: true })

const editorRef = shallowRef<any>(null)

const toolbarConfig = {
  // 这是一个记生活小问题的工具，用不到视频、公式这些
  excludeKeys: ['group-video', 'insertFormula', 'insertTable'],
}

const editorConfig = {
  placeholder: '写点什么…',
  MENU_CONF: {
    uploadImage: {
      customUpload(
        file: File,
        insertFn: (url: string, alt: string, href: string) => void,
      ) {
        articleApi.uploads
          .image(file)
          .then(({ data }) => insertFn(data.url, file.name, data.url))
          .catch((e: any) => {
            ElMessage.error(e?.response?.data?.detail ?? '图片上传失败')
          })
      },
    },
  },
}

function handleCreated(editor: any): void {
  editorRef.value = editor
}

// 编辑器实例必须手动销毁，否则组件卸载后它的事件监听还挂在那儿
onBeforeUnmount(() => {
  editorRef.value?.destroy()
})
</script>

<template>
  <div class="rich-editor">
    <Toolbar
      :editor="editorRef"
      :default-config="toolbarConfig"
      mode="default"
      class="toolbar"
    />
    <Editor
      v-model="modelValue"
      :default-config="editorConfig"
      mode="default"
      class="editor"
      @on-created="handleCreated"
    />
  </div>
</template>

<style scoped>
.rich-editor {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  /* 手机端编辑器体验有限，这里保证最低可用高度 */
  overflow: hidden;
}

.toolbar {
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.editor {
  height: 420px;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .editor {
    height: 300px;
  }
}
</style>
