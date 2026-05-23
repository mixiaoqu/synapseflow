from app.services.graph_store import _prepare_attributes


def test_prepare_attributes_prefixes_keys_and_filters_empty_values():
    result = _prepare_attributes(
        {
            "owner": "平台组",
            "version": " 15 ",
            "enabled": True,
            "empty": "",
            "nested": {"x": 1},
        }
    )

    assert result == {
        "attr_owner": "平台组",
        "attr_version": "15",
        "attr_enabled": True,
        "attr_nested": "{'x': 1}",
    }
