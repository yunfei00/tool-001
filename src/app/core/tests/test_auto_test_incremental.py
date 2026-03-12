from __future__ import annotations

import tempfile
import unittest

from app.core.auto_test_incremental import (
    AutoTestPlanner,
    AutoTestRepository,
    ComboResult,
    RunStatus,
    TestContext,
    combo_signature,
    schema_signature,
)


class AutoTestPlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/planner.db"
        self.repository = AutoTestRepository(self.db_path)
        self.planner = AutoTestPlanner(self.repository)
        self.context = TestContext(project_name="p1", band="n78", frequency="3500")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_first_power_runs_all_current_set(self) -> None:
        combos = [{"cdr delay": 10}, {"cdr delay": 20}]
        combo_ids = {combo_signature(combo) for combo in combos}

        details = self.planner.build_plan(self.context, target_power=10, current_combo_ids=combo_ids)

        self.assertSetEqual(details.plan_set, combo_ids)
        self.assertSetEqual(details.new_set, combo_ids)
        self.assertIsNone(details.base_run)

    def test_plan_uses_latest_lower_power_passes_and_new_combos(self) -> None:
        run_10 = self.repository.create_run(
            context=self.context,
            power=10,
            param_schema_hash=schema_signature(["cdr delay"]),
            status=RunStatus.SUCCESS,
        )

        combo_a = {"cdr delay": 10}
        combo_b = {"cdr delay": 20}
        combo_n = {"cdr delay": 30}
        id_a = combo_signature(combo_a)
        id_b = combo_signature(combo_b)
        id_n = combo_signature(combo_n)

        for combo, combo_id in ((combo_a, id_a), (combo_b, id_b)):
            self.repository.upsert_combo_catalog(self.context, combo_id, combo, run_10)

        self.repository.record_combo_result(run_10, id_a, ComboResult.PASS)
        self.repository.record_combo_result(run_10, id_b, ComboResult.FAIL)
        self.repository.finish_run(run_10, RunStatus.SUCCESS)

        run_8 = self.repository.create_run(
            context=self.context,
            power=8,
            param_schema_hash=schema_signature(["cdr delay"]),
            status=RunStatus.SUCCESS,
        )
        self.repository.upsert_combo_catalog(self.context, id_b, combo_b, run_8)
        self.repository.record_combo_result(run_8, id_b, ComboResult.PASS)
        self.repository.finish_run(run_8, RunStatus.SUCCESS)

        details = self.planner.build_plan(
            self.context,
            target_power=20,
            current_combo_ids={id_a, id_b, id_n},
        )

        self.assertIsNotNone(details.base_run)
        self.assertEqual(details.base_run.power, 10)
        self.assertSetEqual(details.inherited_set, {id_a})
        self.assertSetEqual(details.new_set, {id_n})
        self.assertSetEqual(details.plan_set, {id_a, id_n})


if __name__ == "__main__":
    unittest.main()
