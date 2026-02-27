"""Insurance tools: coverage verification (EDI 270/271). Staff only."""

from langchain_core.tools import tool

from app.llm.tools._utils import _tool_result
from app.services.data_service import verify_insurance as _verify_insurance_svc


@tool
def verify_insurance(member_id: str) -> str:
    """Verify insurance coverage. Staff only. Use member ID (e.g. MEM-987654321, AET-MEM-555123, UHC-MEM-777888) or patient ID (e.g. pat-001, test-pat-001)."""
    result = _verify_insurance_svc(member_id)
    return _tool_result(result)
