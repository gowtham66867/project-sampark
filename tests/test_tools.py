from __future__ import annotations

import unittest

from sampark.llm.tools import build_tool_definitions, execute_tool_call


class ToolsTest(unittest.TestCase):
    def test_build_tool_definitions_returns_two_narrow_tools(self):
        tools = build_tool_definitions()
        names = {tool["name"] for tool in tools}
        self.assertEqual(names, {"get_customer_fact", "get_impact_projection"})

    def test_get_customer_fact_ignores_model_supplied_customer_id(self):
        # execute_tool_call has no customer_id parameter at all in tool_input
        # -- allowed_customer_id is the only source of truth, enforced
        # server-side, never trusted from the model.
        result = execute_tool_call(
            "get_customer_fact", {"field": "kyc_level"}, allowed_customer_id="c003"
        )
        self.assertEqual(result["field"], "kyc_level")
        self.assertEqual(result["value"], "MIN")

    def test_get_customer_fact_rejects_disallowed_field(self):
        with self.assertRaises(ValueError):
            execute_tool_call(
                "get_customer_fact", {"field": "consent"}, allowed_customer_id="c001"
            )

    def test_get_impact_projection_returns_projection_dict(self):
        result = execute_tool_call("get_impact_projection", {}, allowed_customer_id="c001")
        self.assertIn("annual_incremental_activations", result)

    def test_unknown_tool_raises(self):
        with self.assertRaises(ValueError):
            execute_tool_call("delete_customer", {}, allowed_customer_id="c001")


if __name__ == "__main__":
    unittest.main()
