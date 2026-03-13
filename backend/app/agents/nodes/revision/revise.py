"""生成修订内容节点"""
from typing import Dict, Any

from app.agents.states.revision_state import RecursiveRevisionState
from app.core.llm import get_llm_for_content_gen


async def revise_node(state: RecursiveRevisionState) -> Dict[str, Any]:
    """
    生成修订内容节点：生成高质量的补充内容
    使用：content_generation - Kimi内容生成（temperature=0.7）
    """
    if not state.get('missing_items'):
        return {"current_revision": state['current_doc']}

    llm = get_llm_for_content_gen()

    revisions = []
    for item in state['missing_items']:
        if item.get('importance') in ['high', 'medium']:
            revision_prompt = f"""
为文档生成以下缺失内容的补充：

缺失内容：{item.get('description', '')}
插入位置：{item.get('suggested_location', '')}
文档上下文：{state['current_doc'][:1000]}

生成的内容应：
1. 风格与原文档保持一致
2. 逻辑连贯
3. 长度适中（200-500字）

补充内容：
"""

            response = await llm.ainvoke(revision_prompt)
            revisions.append({
                "item": item,
                "content": response.content
            })

    revised_doc = state['current_doc']
    for rev in revisions:
        rev_item = rev.get('item', {})
        revised_doc += f"\n\n## 补充：{rev_item.get('description', '')}\n{rev['content']}"

    return {
        "current_doc": revised_doc,
        "current_revision": revised_doc,
        "revision_history": state.get('revision_history', []) + [
            {"iteration": state['iteration'], "revisions": revisions}
        ]
    }
