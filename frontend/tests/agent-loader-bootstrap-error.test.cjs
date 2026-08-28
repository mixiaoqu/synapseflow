const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('../node_modules/typescript')

function loadAgentApi(fetchImpl) {
  const source = fs.readFileSync(
    path.join(__dirname, '../src/agent-loader/loader.ts'),
    'utf8'
  )
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText
  const pageUrl = new URL('https://business.example.com/dashboard')
  const window = { location: pageUrl }
  const context = {
    URL,
    Error,
    Map,
    Number,
    Object,
    Promise,
    Set,
    String,
    console,
    document: {
      currentScript: {
        src: 'https://agent.example.com/agent-static/loader/v1/loader.js',
        dataset: {
          bootstrapEndpoint: '/api-backstage/agent_chat/bootstrap',
        },
      },
    },
    exports: {},
    fetch: fetchImpl,
    module: { exports: {} },
    require,
    window,
  }
  vm.runInNewContext(output, context)
  return window.EnterpriseAgent
}

test('Loader 从业务端 4xx JSON 响应提取可展示文案', async () => {
  const api = loadAgentApi(async () => ({
    ok: false,
    status: 403,
    async json() {
      return {
        message: '当前账号未关联具体门店，请切换到已关联具体门店的账号后重试',
      }
    },
  }))

  let error
  try {
    await api.open()
  } catch (caught) {
    error = caught
  }

  assert.equal(error.message, 'Business bootstrap failed with HTTP 403.')
  assert.equal(
    error.displayMessage,
    '当前账号未关联具体门店，请切换到已关联具体门店的账号后重试'
  )
})

test('Loader 不展示业务端 5xx 响应中的内部错误', async () => {
  const api = loadAgentApi(async () => ({
    ok: false,
    status: 500,
    async json() {
      return { message: '数据库连接密码错误' }
    },
  }))

  let error
  try {
    await api.open()
  } catch (caught) {
    error = caught
  }

  assert.equal(error.message, 'Business bootstrap failed with HTTP 500.')
  assert.equal(error.displayMessage, undefined)
})
