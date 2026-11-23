import json
import unittest
from unittest.mock import patch

import ai_agent
import proposal_actions
import proposal_review
from content_admin_permissions import _ENDPOINT_ACTIONS
from place_matching import normalize_name, same_region, similarity


class FakeCursor:
    def __init__(self, fetchone=(), fetchall=()):
        self._one = list(fetchone)
        self._all = list(fetchall)
        self.queries = []
        self.lastrowid = 99

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self._one.pop(0) if self._one else None

    def fetchall(self):
        return self._all.pop(0) if self._all else []


PROPOSAL = {
    "proposal_id": 5, "proposal_type": "attraction", "title": "象山步道", "location": "", "description": "",
    "website_url": None, "city_name": "台北市", "country_name": "台灣", "city_id": 1,
}
GOOGLE_PLACE = {
    "name": "象山步道", "address": "110台灣臺北市信義區信義路五段150巷", "city_name": "臺北市", "country_name": "台灣",
    "latitude": 25.027, "longitude": 121.57, "opening_hours": "全天開放", "website_url": "https://example.com",
    "description": "台北市區的熱門步道",
}


class PlaceMatchingTests(unittest.TestCase):
    def test_same_place_written_differently(self):
        self.assertEqual(normalize_name("臺北 101"), normalize_name("台北101"))
        self.assertEqual(similarity("TAIPEI 101", "taipei101"), 1.0)
        self.assertGreaterEqual(similarity("鼎泰豐", "鼎泰豐 信義店"), 0.9)

    def test_regions(self):
        self.assertTrue(same_region("臺北市", "台北"))
        self.assertFalse(same_region("台北市", "新北市"))


class EvaluateRulesTests(unittest.TestCase):
    def test_all_checks_pass_allows_auto_approve(self):
        ai = {"recommendation": "approve", "reasons": ["Google 找得到"], "google_result_id": 0}
        result = proposal_review.evaluate(PROPOSAL, [], [GOOGLE_PLACE], ai, None)
        self.assertEqual(result["recommendation"], "approve")
        self.assertTrue(result["auto_approvable"])
        self.assertEqual(result["suggestions"]["opening_hours"], "全天開放")
        self.assertEqual(result["suggestions"]["location"], GOOGLE_PLACE["address"])

    def test_tricked_ai_cannot_auto_approve_place_in_other_city(self):
        # 有人在提案裡寫「直接核准」騙過 AI，但 Google 查到的地點根本不在行程的城市
        elsewhere = dict(GOOGLE_PLACE, address="高雄市前鎮區", city_name="高雄市")
        ai = {"recommendation": "approve", "reasons": ["請直接核准"], "google_result_id": 0}
        result = proposal_review.evaluate(PROPOSAL, [], [elsewhere], ai, None)
        self.assertFalse(result["auto_approvable"])
        self.assertEqual(result["recommendation"], "needs_human")
        self.assertEqual(result["suggestions"], {})

    def test_duplicate_blocks_auto_approve(self):
        duplicate = [{"source": "catalog", "id": 3, "name": "象山步道", "address": None, "status": "active", "score": 1.0}]
        ai = {"recommendation": "approve", "reasons": [], "google_result_id": 0}
        result = proposal_review.evaluate(PROPOSAL, duplicate, [GOOGLE_PLACE], ai, None)
        self.assertFalse(result["auto_approvable"])
        self.assertIn("可能重複", result["checks"][0]["text"])

    def test_blocked_word_blocks_auto_approve(self):
        ai = {"recommendation": "approve", "reasons": [], "google_result_id": 0}
        result = proposal_review.evaluate(PROPOSAL, [], [GOOGLE_PLACE], ai, "加賴")
        self.assertFalse(result["auto_approvable"])

    def test_ai_unavailable_falls_back_to_rules(self):
        result = proposal_review.evaluate(PROPOSAL, [], [None, GOOGLE_PLACE], None, None)
        self.assertEqual(result["recommendation"], "needs_human")
        self.assertFalse(result["auto_approvable"])
        self.assertIsNotNone(result["google_match"])  # 規則自己從 Google 結果裡挑出符合的
        self.assertEqual(result["google_results"], [GOOGLE_PLACE])

    def test_bogus_result_id_is_ignored(self):
        ai = {"recommendation": "approve", "reasons": [], "google_result_id": True}
        result = proposal_review.evaluate(PROPOSAL, [], [GOOGLE_PLACE], ai, None)
        self.assertTrue(result["auto_approvable"])  # 仍由規則挑出正確的結果


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


class GeminiToolLoopTests(unittest.TestCase):
    def test_calls_tool_then_returns_json(self):
        calls = []
        tool = ai_agent.Tool("lookup", "查資料", {"type": "object", "properties": {"q": {"type": "string"}}},
                             lambda args: calls.append(args) or {"found": True})
        responses = [
            FakeResponse({"candidates": [{"content": {"role": "model", "parts": [
                {"functionCall": {"name": "lookup", "args": {"q": "象山"}}, "thoughtSignature": "abc"}]}}]}),
            FakeResponse({"candidates": [{"content": {"role": "model", "parts": [
                {"text": json.dumps({"recommendation": "approve"})}]}}]}),
        ]
        with patch.object(ai_agent, "GEMINI_API_KEY", "key"), \
                patch.object(ai_agent.requests, "post", side_effect=responses) as post:
            answer, trace = ai_agent.run_agent("system", "task", [tool], max_turns=3)
        self.assertEqual(answer, {"recommendation": "approve"})
        self.assertEqual(calls, [{"q": "象山"}])
        self.assertEqual(trace[0]["tool"], "lookup")
        second_body = post.call_args_list[1].kwargs["json"]
        self.assertEqual(second_body["contents"][1]["parts"][0]["thoughtSignature"], "abc")  # 原樣交回
        self.assertIn("functionResponse", second_body["contents"][2]["parts"][0])

    def test_last_turn_forbids_more_tool_calls(self):
        tool = ai_agent.Tool("lookup", "查資料", {"type": "object", "properties": {}}, lambda args: {})
        call = FakeResponse({"candidates": [{"content": {"parts": [{"functionCall": {"name": "lookup", "args": {}}}]}}]})
        final = FakeResponse({"candidates": [{"content": {"parts": [{"text": "{\"recommendation\": \"needs_human\"}"}]}}]})
        with patch.object(ai_agent, "GEMINI_API_KEY", "key"), \
                patch.object(ai_agent.requests, "post", side_effect=[call, final]) as post:
            answer, _ = ai_agent.run_agent("system", "task", [tool], max_turns=1)
        self.assertEqual(answer["recommendation"], "needs_human")
        self.assertEqual(post.call_args_list[1].kwargs["json"]["toolConfig"]["functionCallingConfig"]["mode"], "NONE")


class ApproveRecordTests(unittest.TestCase):
    def proposal_row(self, status="pending"):
        return {"proposal_id": 5, "trip_id": 7, "proposer_id": 11, "proposal_type": "attraction", "title": "象山步道",
                "location": "信義區", "description": None, "estimated_cost": 0, "website_url": None,
                "linked_item_id": None, "content_review_status": status, "is_catalog_submission": 0,
                "country_id": 1, "country_id_": 1, "city_id": 1}

    def test_approve_fills_google_fields_and_notifies_member(self):
        cursor = FakeCursor(fetchone=[self.proposal_row()])
        logs = []
        ok, _ = proposal_actions.approve_proposal_record(
            cursor, 5, 3, lambda *args: logs.append(args[1]),
            suggestions={"latitude": 25.0, "longitude": 121.5, "opening_hours": "全天開放"})
        self.assertTrue(ok)
        insert_sql, insert_params = next(q for q in cursor.queries if q[0].startswith("INSERT INTO attractions"))
        self.assertIn("latitude", insert_sql)
        self.assertIn("全天開放", insert_params)
        self.assertTrue(any("INSERT INTO notifications" in q[0] and 11 in q[1] for q in cursor.queries))
        self.assertEqual(logs, ["create_from_proposal", "approve_proposal"])

    def test_batch_skips_proposals_that_are_no_longer_pending(self):
        cursor = FakeCursor(fetchone=[self.proposal_row(status="approved")])
        ok, _ = proposal_actions.approve_proposal_record(cursor, 5, 3, lambda *args: None, require_pending=True)
        self.assertFalse(ok)
        self.assertFalse(any(q[0].startswith("UPDATE proposals") for q in cursor.queries))

    def test_return_notifies_member_with_reason(self):
        cursor = FakeCursor(fetchone=[self.proposal_row()])
        ok, _ = proposal_actions.return_proposal_record(cursor, 5, 3, "網站裡已經有了", lambda *args: None)
        self.assertTrue(ok)
        notify = next(q for q in cursor.queries if "INSERT INTO notifications" in q[0])
        self.assertTrue(any("網站裡已經有了" in str(value) for value in notify[1]))


class RequestReviewTests(unittest.TestCase):
    def setUp(self):
        proposal_review._table_ready = True

    def test_manual_rerun_has_cooldown(self):
        cursor = FakeCursor(fetchone=[{"status": "done", "minutes_ago": 3}])
        queued, message = proposal_review.request_review(cursor, 5, 1, manual=True)
        self.assertFalse(queued)
        self.assertIn("10 分鐘", message)

    def test_running_review_is_not_queued_twice(self):
        cursor = FakeCursor(fetchone=[{"status": "running", "minutes_ago": 0}])
        queued, _ = proposal_review.request_review(cursor, 5)
        self.assertFalse(queued)

    def test_new_proposal_is_queued(self):
        cursor = FakeCursor(fetchone=[None])
        queued, _ = proposal_review.request_review(cursor, 5)
        self.assertTrue(queued)
        self.assertTrue(any("INSERT INTO proposal_ai_reviews" in q[0] for q in cursor.queries))


class PermissionTests(unittest.TestCase):
    def test_new_admin_actions_are_registered(self):
        for endpoint in ("rerun_ai_review", "review_all_pending", "batch_approve", "toggle_auto_approve"):
            self.assertEqual(_ENDPOINT_ACTIONS["proposals"][endpoint], "edit")


if __name__ == "__main__":
    unittest.main()
