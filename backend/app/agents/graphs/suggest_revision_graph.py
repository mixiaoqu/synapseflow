"""用户建议驱动修订图"""
from langgraph.graph import StateGraph, END

from app.agents.states.revision_state import UserDrivenRevisionState
from app.agents.nodes.revision.parse_suggestions import parse_suggestions_node
from app.agents.nodes.revision.analyze_document import analyze_document_node
from app.agents.nodes.revision.locate_edits import locate_edits_node
from app.agents.nodes.revision.revise import revise_node


def create_suggest_revision_graph():
    """
    创建用户建议驱动修订图。
    流程：parse_suggestions -> analyze_document -> locate_edits -> revise -> END
    一次性执行，无中断。
    """
    workflow = StateGraph(UserDrivenRevisionState)

    workflow.add_node("parse_suggestions", parse_suggestions_node)
    workflow.add_node("analyze_document", analyze_document_node)
    workflow.add_node("locate_edits", locate_edits_node)
    workflow.add_node("revise", revise_node)

    workflow.set_entry_point("parse_suggestions")
    workflow.add_edge("parse_suggestions", "analyze_document")
    workflow.add_edge("analyze_document", "locate_edits")
    workflow.add_edge("locate_edits", "revise")
    workflow.add_edge("revise", END)

    return workflow.compile()
