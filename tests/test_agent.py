from agent.tools import TOOLS, dispatch


def test_tool_catalog():
    names = {tool["name"] for tool in TOOLS}
    assert names == {"list_cities", "list_segments", "rank_interventions"}


def test_dispatch_list_cities():
    result = dispatch("list_cities")
    assert any(row["id"] == "phoenix" for row in result["cities"])
