from app.application.document_service import DocumentService


def test_document_service_normalizes_source_path():
    assert (
        DocumentService._normalize_source_path(r" 项目A\\支付\\FAQ.md ")
        == "项目A/支付/FAQ.md"
    )
    assert DocumentService._normalize_source_path("///") is None


def test_document_service_infers_category_from_top_level_folder():
    assert DocumentService._infer_category_name("支付/FAQ.md") == "支付"
    assert DocumentService._infer_category_name(r"订单\\规则\\退款.md") == "订单"
    assert DocumentService._infer_category_name("FAQ.md") is None
