"""Route constants for the top-level Agent workflow."""

ROUTE_DIRECT_RESPONSE = "direct_response"
ROUTE_CLARIFY_MAIN = "clarify_main"
ROUTE_UNSUPPORTED = "unsupported"
ROUTE_APPROVAL = "approval"
ROUTE_SAFE_BLOCK = "safe_block"
ROUTE_SINGLE_SUB_AGENT = "single_sub_agent"
ROUTE_MULTI_SUB_AGENT = "multi_sub_agent"
EXECUTION_ROUTE_TYPES = {ROUTE_SINGLE_SUB_AGENT, ROUTE_MULTI_SUB_AGENT}
