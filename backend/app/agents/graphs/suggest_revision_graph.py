"""用户建议驱动修订图"""
from langgraph.graph import StateGraph, END

from app.agents.states.revision_state import UserDrivenRevisionState
from app.agents.nodes.revision.parse_edit_request import parse_edit_request_node
from app.agents.nodes.revision.extract_doc_structure import extract_doc_structure_node
from app.agents.nodes.revision.chunk_document import chunk_document_node
from app.agents.nodes.revision.retrieve_relevant_chunks import retrieve_relevant_chunks_node
from app.agents.nodes.revision.locate_section import locate_section_node
from app.agents.nodes.revision.revise_by_suggestions import revise_by_suggestions_node


def create_suggest_revision_graph():
    """
    创建用户建议驱动修订图
    流程：parse_edit_request -> extract_doc_structure -> chunk_document
         -> retrieve_relevant_chunks -> locate_section -> revise_by_suggestions -> END
    """
    workflow = StateGraph(UserDrivenRevisionState)

    workflow.add_node("parse_edit_request", parse_edit_request_node)
    workflow.add_node("extract_doc_structure", extract_doc_structure_node)
    workflow.add_node("chunk_document", chunk_document_node)
    workflow.add_node("retrieve_relevant_chunks", retrieve_relevant_chunks_node)
    workflow.add_node("locate_section", locate_section_node)
    workflow.add_node("revise_by_suggestions", revise_by_suggestions_node)

    workflow.set_entry_point("parse_edit_request")
    workflow.add_edge("parse_edit_request", "extract_doc_structure")
    workflow.add_edge("extract_doc_structure", "chunk_document")
    workflow.add_edge("chunk_document", "retrieve_relevant_chunks")
    workflow.add_edge("retrieve_relevant_chunks", "locate_section")
    workflow.add_edge("locate_section", "revise_by_suggestions")
    workflow.add_edge("revise_by_suggestions", END)

    return workflow.compile()
