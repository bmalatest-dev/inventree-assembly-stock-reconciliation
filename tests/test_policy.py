import unittest
from decimal import Decimal

import importlib.util
from pathlib import Path

_POLICY_PATH = Path(__file__).resolve().parents[1] / "assembly_stock_reconciliation" / "policy.py"
_SPEC = importlib.util.spec_from_file_location("asr_policy", _POLICY_PATH)
_POLICY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_POLICY)
spillage_per_project = _POLICY.spillage_per_project
evaluate_policy = _POLICY.evaluate_policy
aggregate_allocation_policy = _POLICY.aggregate_allocation_policy
select_effective_price = _POLICY.select_effective_price
distribute_consumption_by_policy = _POLICY.distribute_consumption_by_policy
compact_tracking_note = _POLICY.compact_tracking_note

D = Decimal


class SpillageRuleTests(unittest.TestCase):
    def test_passive_0201(self):
        self.assertEqual(spillage_per_project("0201", 1, "Resistors")[0], D(200))

    def test_passive_0402(self):
        self.assertEqual(spillage_per_project("0402", 1, "Capacitors")[0], D(100))

    def test_passive_0603(self):
        self.assertEqual(spillage_per_project("0603", 1, "Inductors")[0], D(50))

    def test_passive_0805(self):
        self.assertEqual(spillage_per_project("0805", 1, "Resistors")[0], D(25))

    def test_passive_1206_1210(self):
        self.assertEqual(spillage_per_project("1206", 1, "Resistors")[0], D(20))
        self.assertEqual(spillage_per_project("1210", 1, "Resistors")[0], D(20))

    def test_price_bands(self):
        self.assertEqual(spillage_per_project("QFN", 201, "IC")[0], D(0))
        self.assertEqual(spillage_per_project("QFN", 51, "IC")[0], D(1))
        self.assertEqual(spillage_per_project("QFN", 11, "IC")[0], D(2))
        self.assertEqual(spillage_per_project("QFN", 10, "IC")[0], D(5))

    def test_missing_price_fallbacks(self):
        self.assertEqual(spillage_per_project("0402", 0, "Resistor")[0], D(100))
        self.assertEqual(spillage_per_project("UNKNOWN", 0, "Capacitor")[0], D(5))
        self.assertEqual(spillage_per_project("QFN", 0, "IC")[0], D(5))


class ReconciliationPolicyTests(unittest.TestCase):
    def evaluate(self, returned, nominal=90, maximum=100, allocated=100, current=100):
        return evaluate_policy(
            current_quantity=current,
            returned_quantity=returned,
            selected_allocation=allocated,
            nominal_expected=nominal,
            acceptable_max=maximum,
        )

    def test_exact_nominal(self):
        r = self.evaluate(returned=10)
        self.assertFalse(r["blocking_error"])
        self.assertFalse(r["hard_warning"])
        self.assertEqual(r["policy_classification"], "within_nominal")

    def test_excess_return_under_consumption_warns(self):
        # User's real-world 100 stock / nominal 90 / returned 25 case.
        r = self.evaluate(returned=25)
        self.assertFalse(r["blocking_error"])
        self.assertTrue(r["hard_warning"])
        self.assertEqual(r["policy_classification"], "below_nominal")

    def test_consumption_within_spillage_is_allowed(self):
        r = self.evaluate(returned=5)  # consume 95, within 90..100
        self.assertFalse(r["blocking_error"])
        self.assertFalse(r["hard_warning"])
        self.assertEqual(r["policy_classification"], "within_spillage")

    def test_consumption_over_spillage_warns(self):
        r = self.evaluate(returned=4, maximum=95, allocated=100)  # consume 96
        self.assertFalse(r["blocking_error"])
        self.assertTrue(r["hard_warning"])
        self.assertEqual(r["policy_classification"], "above_spillage_allowance")

    def test_consumption_above_policy_max_warns_even_if_jit_may_be_possible(self):
        # Existing allocation is no longer the policy ceiling in v0.3.1; the live
        # plugin separately verifies whether extra StockItem allocation can be made.
        r = self.evaluate(returned=5, nominal=80, maximum=90, allocated=90)  # consume 95
        self.assertFalse(r["blocking_error"])
        self.assertTrue(r["hard_warning"])
        self.assertEqual(r["policy_classification"], "above_spillage_allowance")

    def test_return_exceeds_current_stock_blocks(self):
        r = self.evaluate(returned=101)
        self.assertTrue(r["blocking_error"])
        self.assertEqual(r["policy_classification"], "return_exceeds_stock")

    def test_no_op_only_clean_when_no_nominal_remains(self):
        r = self.evaluate(returned=100, nominal=0, maximum=0, allocated=0)
        self.assertFalse(r["blocking_error"])
        self.assertFalse(r["hard_warning"])
        self.assertEqual(r["policy_classification"], "no_op")

    def test_full_return_warns_when_nominal_consumption_remains(self):
        r = self.evaluate(returned=100, nominal=50, maximum=55, allocated=55)
        self.assertTrue(r["hard_warning"])
        self.assertEqual(r["policy_classification"], "below_nominal")


class MultiBuildPolicyTests(unittest.TestCase):
    def test_multi_bo_nominal_total_and_excess_return_warning(self):
        # Exact current user scenario: 100 stock, BO11=60, BO12=30.
        limits = aggregate_allocation_policy([
            {"build_reference": "BO-0011", "allocated": 60, "required": 60, "consumed": 0},
            {"build_reference": "BO-0012", "allocated": 30, "required": 30, "consumed": 0},
        ], 5)
        self.assertEqual(limits["nominal_expected_consumption"], D(90))
        self.assertEqual(limits["acceptable_consumption_max"], D(100))
        result = evaluate_policy(
            current_quantity=100, returned_quantity=25, selected_allocation=90,
            nominal_expected=limits["nominal_expected_consumption"],
            acceptable_max=limits["acceptable_consumption_max"],
        )
        self.assertTrue(result["hard_warning"])
        self.assertEqual(result["policy_classification"], "below_nominal")

    def test_multi_bo_mixed_spillage_allowance(self):
        # Allocations include planned overage: 60+5 and 30+2. Actual consumption 95
        # is above nominal 90 but within the selected planned allowance of 97.
        limits = aggregate_allocation_policy([
            {"build_reference": "BO-A", "allocated": 65, "required": 60, "consumed": 0},
            {"build_reference": "BO-B", "allocated": 32, "required": 30, "consumed": 0},
        ], 5)
        self.assertEqual(limits["nominal_expected_consumption"], D(90))
        self.assertEqual(limits["acceptable_consumption_max"], D(100))
        result = evaluate_policy(
            current_quantity=100, returned_quantity=5, selected_allocation=97,
            nominal_expected=90, acceptable_max=97,
        )
        self.assertFalse(result["blocking_error"])
        self.assertFalse(result["hard_warning"])
        self.assertEqual(result["policy_classification"], "within_spillage")

    def test_partial_prior_reconciliation_reduces_nominal_remaining(self):
        limits = aggregate_allocation_policy([
            {"build_reference": "BO-0010", "allocated": 51, "required": 75, "consumed": 24},
        ], 5)
        self.assertEqual(limits["nominal_expected_consumption"], D(51))
        # v0.3.1 retains the unused planned spillage allowance even though operators
        # normally allocate only the remaining nominal requirement.
        self.assertEqual(limits["acceptable_consumption_max"], D(56))

    def test_prior_over_nominal_consumption_uses_spillage_allowance(self):
        limits = aggregate_allocation_policy([
            {"build_reference": "BO-X", "allocated": 3, "required": 75, "consumed": 77},
        ], 5)
        detail = limits["project_details"][0]
        self.assertEqual(detail["spillage_already_used"], D(2))
        self.assertEqual(detail["spillage_remaining"], D(3))
        self.assertEqual(limits["nominal_expected_consumption"], D(0))
        self.assertEqual(limits["acceptable_consumption_max"], D(3))


    def test_effective_price_prefers_part_pricing(self):
        result = select_effective_price(D("75"), D("25"))
        self.assertEqual(result["effective_price"], D("75"))
        self.assertEqual(result["price_source"], "part_pricing_max")

    def test_effective_price_falls_back_to_stock_item(self):
        result = select_effective_price(D("0"), D("25"))
        self.assertEqual(result["effective_price"], D("25"))
        self.assertEqual(result["price_source"], "stock_item_unit_price")
        spill, rule = spillage_per_project("", result["effective_price"], "IC")
        self.assertEqual(spill, D("2"))
        self.assertEqual(rule, "price_10_to_50")

    def test_effective_price_missing_uses_fallback(self):
        result = select_effective_price(D("0"), D("0"))
        self.assertEqual(result["effective_price"], D("0"))
        self.assertEqual(result["price_source"], "missing_price_fallback")


class DistributionPolicyTests(unittest.TestCase):
    def test_multi_bo_above_spillage_distributes_planned_first(self):
        details = [
            {
                "build": 13, "build_line": 130,
                "nominal_expected_from_selected_stock": D("10"),
                "acceptable_consumption_max": D("15"),
            },
            {
                "build": 14, "build_line": 140,
                "nominal_expected_from_selected_stock": D("10"),
                "acceptable_consumption_max": D("15"),
            },
        ]
        result = distribute_consumption_by_policy(details, D("31"))
        self.assertEqual(result[0]["nominal_consumed"], D("10"))
        self.assertEqual(result[1]["nominal_consumed"], D("10"))
        self.assertEqual(result[0]["spillage_consumed"], D("5"))
        self.assertEqual(result[1]["spillage_consumed"], D("5"))
        self.assertEqual(result[0]["exception_consumed"], D("1"))
        self.assertEqual(result[1]["exception_consumed"], D("0"))
        self.assertEqual(result[0]["total_consumption"], D("16"))
        self.assertEqual(result[1]["total_consumption"], D("15"))

    def test_exact_nominal_consumes_nominal_across_bos_before_spillage(self):
        details = [
            {
                "build": 13, "build_line": 130,
                "nominal_expected_from_selected_stock": D("10"),
                "acceptable_consumption_max": D("15"),
            },
            {
                "build": 14, "build_line": 140,
                "nominal_expected_from_selected_stock": D("10"),
                "acceptable_consumption_max": D("15"),
            },
        ]
        result = distribute_consumption_by_policy(details, D("20"))
        self.assertEqual(result[0]["total_consumption"], D("10"))
        self.assertEqual(result[1]["total_consumption"], D("10"))
        self.assertEqual(result[0]["spillage_consumed"], D("0"))
        self.assertEqual(result[1]["spillage_consumed"], D("0"))

    def test_within_spillage_uses_each_bo_allowance_in_order(self):
        details = [
            {
                "build": 13, "build_line": 130,
                "nominal_expected_from_selected_stock": D("10"),
                "acceptable_consumption_max": D("15"),
            },
            {
                "build": 14, "build_line": 140,
                "nominal_expected_from_selected_stock": D("10"),
                "acceptable_consumption_max": D("15"),
            },
        ]
        result = distribute_consumption_by_policy(details, D("27"))
        self.assertEqual(result[0]["total_consumption"], D("15"))
        self.assertEqual(result[1]["total_consumption"], D("12"))
        self.assertEqual(result[0]["spillage_consumed"], D("5"))
        self.assertEqual(result[1]["spillage_consumed"], D("2"))
        self.assertEqual(result[0]["exception_consumed"], D("0"))
        self.assertEqual(result[1]["exception_consumed"], D("0"))



class TrackingNoteTests(unittest.TestCase):
    def test_compact_note_stays_within_512(self):
        note = compact_tracking_note([
            "Stock Rec", "BO BO-0014", "Start 300", "Return 272",
            "Consumed 13", "Nominal 20", "SpillAllow 10", "SpillUsed 3",
            "Exception 0", "JIT 3", "ExAlloc 0", "Policy within_spillage",
            "Rule price_under_10_or_unknown", "Price 10", "Src stock_item_unit_price"
        ])
        self.assertLessEqual(len(note), 512)
        self.assertTrue(note.startswith("Stock Rec"))

    def test_compact_note_truncates_long_tail(self):
        note = compact_tracking_note([
            "Stock Rec",
            "BO " + ("X" * 300),
            "Notes " + ("Y" * 500),
            "OVERRIDE " + ("Z" * 500),
        ])
        self.assertLessEqual(len(note), 512)
        self.assertTrue(note.endswith("..."))

    def test_compact_note_keeps_clean_integers(self):
        note = compact_tracking_note(["Start 300", "Consumed 12", "JIT 2"])
        self.assertNotIn(".00000", note)


if __name__ == '__main__':
    unittest.main()


class TestJITPolicy(unittest.TestCase):
    def test_normal_allocation_does_not_cap_spillage_policy(self):
        result = aggregate_allocation_policy([{
            "build": 14, "build_line": 140, "allocated": D("10"),
            "required": D("10"), "consumed": D("0")
        }], D("2"))
        self.assertEqual(result["nominal_expected_consumption"], D("10"))
        self.assertEqual(result["acceptable_consumption_max"], D("12"))

    def test_within_spillage_can_exceed_existing_allocation(self):
        result = evaluate_policy(current_quantity=D("300"), returned_quantity=D("288"),
            selected_allocation=D("10"), nominal_expected=D("10"), acceptable_max=D("12"))
        self.assertFalse(result["blocking_error"])
        self.assertFalse(result["hard_warning"])
        self.assertEqual(result["policy_classification"], "within_spillage")
