/**
 * 测 chat.ts 的 SSE 解析。用假的 fetch 造一个字节流，
 * 故意把中文字符切在两个网络包里 —— 这是只有在真实网络上才会出现的情况。
 */

import { streamChat } from '../src/modules/ai/chat.ts'

let passed = 0
const failed: string[] = []

function check(name: string, ok: boolean, detail = '') {
  if (ok) {
    passed++
    console.log(`  ✔ ${name}`)
  } else {
    failed.push(name)
    console.log(`  ✘ ${name}   ${detail}`)
  }
}

/** 造一个把字节按指定大小切碎后吐出来的假响应体。 */
function bodyOf(text: string, chunkBytes: number): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text)
  let i = 0
  return new ReadableStream({
    pull(controller) {
      if (i >= bytes.length) {
        controller.close()
        return
      }
      controller.enqueue(bytes.slice(i, i + chunkBytes))
      i += chunkBytes
    },
  })
}

function mockFetch(text: string, chunkBytes: number, status = 200) {
  globalThis.fetch = (async () =>
    new Response(status === 200 ? bodyOf(text, chunkBytes) : text, {
      status,
      headers: { 'Content-Type': status === 200 ? 'text/event-stream' : 'application/json' },
    })) as typeof fetch
}

/** 把事件收集成简洁形式，方便断言。 */
function collector() {
  const got: string[] = []
  let answer = ''
  let cites: Array<{ title: string; score: number }> = []
  let used: boolean | null = null
  return {
    handlers: {
      onMeta: (u: boolean, c: any[]) => {
        used = u
        cites = c
        got.push('meta')
      },
      onDelta: (t: string) => {
        answer += t
        got.push('delta')
      },
      onDone: (id: number) => got.push(`done:${id}`),
      onError: (d: string) => got.push(`error:${d}`),
    },
    result: () => ({ got, answer, cites, used }),
  }
}

function sse(...frames: Array<[string, unknown]>): string {
  return frames.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join('')
}

async function main() {
  console.log()
  console.log('='.repeat(66))
  console.log('chat.ts 的 SSE 解析')
  console.log('='.repeat(66))

  const ANSWER = '根据《租房合同要注意什么》：押金能要回来。先协商，协商不成向住建部门投诉。'
  const stream = sse(
    ['meta', { used_knowledge: true, citations: [{ article_id: 3, title: '租房合同要注意什么', score: 0.87, chunk_index: 0 }] }],
    ['delta', { text: ANSWER.slice(0, 10) }],
    ['delta', { text: ANSWER.slice(10, 30) }],
    ['delta', { text: ANSWER.slice(30) }],
    ['done', { message_id: 42 }],
  )

  // ---- 1. 正常情况：一次给一整个包 ----
  {
    const c = collector()
    mockFetch(stream, 1_000_000)
    await streamChat(1, '押金能要回来吗', c.handlers)
    const r = c.result()
    check('事件顺序正确', r.got.join(',') === 'meta,delta,delta,delta,done:42', r.got.join(','))
    check('回答拼装完整', r.answer === ANSWER, JSON.stringify(r.answer.slice(0, 40)))
    check('meta 的引用来源解析正确', r.cites.length === 1 && r.cites[0].title === '租房合同要注意什么')
    check('used_knowledge 传对了', r.used === true)
  }

  // ---- 2. 每 1 字节一个包：最极端的情况 ----
  {
    const c = collector()
    mockFetch(stream, 1)
    await streamChat(1, '押金能要回来吗', c.handlers)
    const r = c.result()
    check('逐字节传输时事件仍完整', r.got.join(',') === 'meta,delta,delta,delta,done:42', r.got.join(','))
    check(
      '★ 中文字符被切碎时不乱码（stream:true 的功劳）',
      r.answer === ANSWER,
      JSON.stringify(r.answer.slice(0, 40)),
    )
  }

  // ---- 3. 找一个真的落在中文字符中间的切点 ----
  {
    const bytes = new TextEncoder().encode(stream)
    // 找到第一个「切下去会切断多字节字符」的位置
    let cut = -1
    for (let i = 1; i < bytes.length; i++) {
      // UTF-8 续字节是 10xxxxxx，落在它前面就是切在字符中间
      if ((bytes[i] & 0xc0) === 0x80 && (bytes[i - 1] & 0xc0) !== 0x80) {
        cut = i
        break
      }
    }
    check('找到了一个切断中文字符的位置', cut > 0, `cut=${cut}`)
    if (cut > 0) {
      const c = collector()
      // 前一半一个包（正好切在字符中间），后面一次给完
      globalThis.fetch = (async () =>
        new Response(
          new ReadableStream({
            start(ctrl) {
              ctrl.enqueue(bytes.slice(0, cut))
              ctrl.enqueue(bytes.slice(cut))
              ctrl.close()
            },
          }),
          { status: 200 },
        )) as typeof fetch
      await streamChat(1, '押金能要回来吗', c.handlers)
      const r = c.result()
      check(
        '切在字符中间时前后两半能正确拼接',
        r.answer === ANSWER && !r.answer.includes('\uFFFD'),
        JSON.stringify(r.answer.slice(0, 40)),
      )
    }
  }

  // ---- 4. F13：未引用知识库 ----
  {
    const c = collector()
    mockFetch(
      sse(
        ['meta', { used_knowledge: false, citations: [] }],
        ['delta', { text: '量子纠缠是……' }],
        ['done', { message_id: 7 }],
      ),
      7,
    )
    await streamChat(1, '量子纠缠', c.handlers)
    const r = c.result()
    check('F13 的 used_knowledge 是 false', r.used === false)
    check('F13 的引用来源是空数组', r.cites.length === 0)
  }

  // ---- 5. error 事件 ----
  {
    const c = collector()
    mockFetch(sse(['error', { detail: '被限流或免费额度已用完' }]), 5)
    await streamChat(1, '问题', c.handlers)
    const r = c.result()
    check('error 事件透传到 onError', r.got.length === 1 && r.got[0].startsWith('error:'), r.got.join(','))
  }

  // ---- 6. 非 200 的普通 JSON 错误 ----
  {
    const c = collector()
    mockFetch(JSON.stringify({ detail: '会话不存在' }), 1000, 404)
    await streamChat(999, '问题', c.handlers)
    const r = c.result()
    check('404 的 detail 被取出来', r.got.join(',') === 'error:会话不存在', r.got.join(','))
  }

  // ---- 7. 坏帧不该中断整场回答 ----
  {
    const c = collector()
    const broken = 'event: delta\ndata: {坏掉的JSON\n\n' + sse(['delta', { text: '正常内容' }], ['done', { message_id: 1 }])
    mockFetch(broken, 3)
    await streamChat(1, '问题', c.handlers)
    const r = c.result()
    check('坏帧被跳过，后面的内容照常收到', r.answer === '正常内容', JSON.stringify(r.answer))
    check('坏帧后面的 done 也收到了', r.got.includes('done:1'), r.got.join(','))
  }

  // ---- 8. 取消 ----
  {
    const c = collector()
    let released = false
    globalThis.fetch = (async (_url: any, init: any) => {
      const signal: AbortSignal = init.signal
      const body = new ReadableStream({
        start(ctrl) {
          ctrl.enqueue(new TextEncoder().encode(sse(['delta', { text: '一半' }])))
          signal.addEventListener('abort', () => {
            released = true
            ctrl.error(new DOMException('aborted', 'AbortError'))
          })
        },
      })
      return new Response(body, { status: 200 })
    }) as typeof fetch

    const ac = new AbortController()
    const p = streamChat(1, '问题', c.handlers, ac.signal)
    setTimeout(() => ac.abort(), 30)
    await p
    check('取消后读流被释放', released)
    check('取消不会报错打扰用户', !c.result().got.some((g) => g.startsWith('error:')), c.result().got.join(','))
  }

  console.log()
  console.log('='.repeat(66))
  if (failed.length) {
    console.log(`结果：${passed} 通过，${failed.length} 失败`)
    for (const f of failed) console.log(`  失败：${f}`)
    process.exit(1)
  }
  console.log(`结果：全部 ${passed} 项通过`)
}

main()
