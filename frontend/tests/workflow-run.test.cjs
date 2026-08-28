const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('../node_modules/typescript')

function loadReducer() {
  const source = fs.readFileSync(path.join(__dirname, '../src/shared/lib/stream/workflowRun.ts'), 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const context = { exports: {}, require }
  vm.runInNewContext(output, context)
  return context.exports.reduceWorkflowRunEvent
}

function event(type, callId, data = {}, nodeId = 'retrieve_knowledge') {
  return {
    type, workflow_id: 'knowledge_qa', node_id: nodeId,
    node_name: '检索知识', timestamp: 1,
    data: { tool_call_id: callId, round: 1, ...data },
  }
}

test('独立调用的进度与完成事件保持隔离', () => {
  const reduce = loadReducer()
  let run = reduce(null, event('node_start', 'a'))
  run = reduce(run, event('node_start', 'b'))
  run = reduce(run, event('node_complete', 'a'))
  const nodes = run.workflows.knowledge_qa.nodes
  assert.equal(nodes['retrieve_knowledge:a'].status, 'success')
  assert.equal(nodes['retrieve_knowledge:b'].status, 'running')
})

test('主节点的后续轮次有独立执行状态', () => {
  const reduce = loadReducer()
  let run = reduce(null, event('node_complete', '', { round: 1 }, 'decide'))
  run = reduce(run, event('progress', '', { round: 2, activity_text: '根据结果继续规划' }, 'decide'))
  const nodes = run.workflows.knowledge_qa.nodes
  assert.equal(nodes['decide:round_1'].status, 'success')
  assert.equal(nodes['decide:round_2'].status, 'running')
  assert.equal(run.currentNodeId, 'decide:round_2')
})

test('完成的活动与新轮次按后端阶段标识显示', () => {
  const reduce = loadReducer()
  let run = reduce(null, event('progress', 'a', {
    display_stage: 'round_1:knowledge_search:a', display_title: '查阅资料',
    activity_text: '已找到相关资料', activity_status: 'completed',
  }))
  run = reduce(run, event('progress', 'b', {
    round: 2, display_stage: 'round_2:knowledge_search:b', display_title: '查阅资料',
    activity_text: '查找新的资料', activity_status: 'running',
  }))
  assert.equal(run.displayStages.length, 2)
  assert.equal(run.displayStages[0].status, 'success')
  assert.equal(run.displayStages[1].status, 'running')
})


test('后启动的并行阶段不会提前完成前一个阶段', () => {
  const reduce = loadReducer()
  let run = reduce(null, event('progress', 'a', {
    display_stage: 'round_1:knowledge_search:a', activity_text: '检索A',
  }))
  run = reduce(run, event('progress', 'b', {
    display_stage: 'round_1:knowledge_search:b', activity_text: '检索B',
  }))
  assert.equal(run.displayStages[0].status, 'running')
  assert.equal(run.displayStages[1].status, 'running')
})
