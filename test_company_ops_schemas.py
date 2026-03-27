"""Pydantic schemas for multi-department / Arbiter (Direction 3)."""

import unittest

from pydantic import ValidationError

from company_ops_schemas import ArbiterInput, ArbiterResolution, DepartmentMemo


class TestCompanyOpsSchemas(unittest.TestCase):
    def test_department_memo_roundtrip(self):
        m = DepartmentMemo(
            department="growth",
            summary="Narrative note",
            confidence=0.5,
            open_questions=["q1"],
        )
        data = m.model_dump()
        self.assertEqual(data["department"], "growth")

    def test_arbiter_input_list(self):
        inp = ArbiterInput(
            memos=[
                DepartmentMemo(department="product", summary="Ship dashboard", confidence=0.8),
            ]
        )
        self.assertEqual(len(inp.memos), 1)

    def test_invalid_department_rejected(self):
        with self.assertRaises(ValidationError):
            DepartmentMemo(department="invalid", summary="x")  # type: ignore[arg-type]

    def test_arbiter_resolution(self):
        r = ArbiterResolution(
            headline="Focus on stability",
            priorities=["p1"],
            conflicts=["c1"],
            needs_data=["d1"],
        )
        self.assertIn("stability", r.headline)


if __name__ == "__main__":
    unittest.main()
