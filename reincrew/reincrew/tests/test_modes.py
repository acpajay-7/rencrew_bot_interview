"""Mode behaviour with the network mocked. No real API or Ollama is contacted."""
import unittest
from unittest import mock

from reincrew import api_ai, engine, local_ai
from reincrew.local_ai import NonLocalEndpointError, assert_loopback
from tests.helpers import fresh_db

Q = {"question": "What is overfitting?", "reference": "Model memorizes noise.", "concepts": {"a": ["memorizes"]}, "depth": []}
GOOD_JSON = '{"correctness_score": 90, "knowledge_depth_score": 70, "completeness_score": 80, "final_score": 1, "status": "complete", "explanation": "ok"}'


class LocalIsolationTests(unittest.TestCase):
    def test_loopback_allowed(self):
        for u in ["http://127.0.0.1:11434/api/generate", "http://localhost:11434/api/generate"]:
            assert_loopback(u)

    def test_remote_endpoint_refused(self):
        for u in ["https://openrouter.ai/api/v1/chat/completions", "http://192.168.1.5:11434/api/generate", "http://example.com/api/generate"]:
            with self.assertRaises(NonLocalEndpointError):
                assert_loopback(u)

    def test_local_mode_never_calls_api_module(self):
        with mock.patch.object(api_ai, "chat") as chat, \
             mock.patch("requests.post", side_effect=ConnectionError("ollama down")):
            res = engine.evaluate_answer("Local AI Mode", Q, "it memorizes noise and fails on new data")
        chat.assert_not_called()
        self.assertEqual(res["scoring_mode"], "rule_based_fallback")  # falls back to rules, still local

    def test_local_mode_only_posts_to_loopback(self):
        seen = []
        def fake_post(url, **kw):
            seen.append(url)
            m = mock.Mock(); m.raise_for_status = lambda: None
            m.json = lambda: {"response": GOOD_JSON}
            return m
        with mock.patch("requests.post", fake_post):
            res = engine.evaluate_answer("Local AI Mode", Q, "memorizes")
        self.assertEqual(res["scoring_mode"], "local_ollama")
        self.assertTrue(all("127.0.0.1" in u or "localhost" in u for u in seen))
        self.assertEqual(res["final_score"], round(90 * .6 + 70 * .25 + 80 * .15))  # recomputed with original weights

    def test_local_mode_refuses_remote_ollama_url(self):
        with mock.patch.object(local_ai.config, "OLLAMA_URL", "https://openrouter.ai/x"), \
             mock.patch("requests.post") as post:
            res = engine.evaluate_answer("Local AI Mode", Q, "memorizes")
        post.assert_not_called()
        self.assertEqual(res["scoring_mode"], "rule_based_fallback")


class ApiAndHybridTests(unittest.TestCase):
    def test_api_mode_uses_api_and_caches(self):
        db = fresh_db()
        with mock.patch.object(api_ai, "chat", return_value=GOOD_JSON) as chat:
            r1 = engine.evaluate_answer("API Mode", Q, "memorizes noise", db=db, api_key="k")
            r2 = engine.evaluate_answer("API Mode", Q, "memorizes noise", db=db, api_key="k")
        self.assertEqual(chat.call_count, 1)  # second call served from cache
        self.assertEqual(r1["scoring_mode"], "api_openrouter"); self.assertEqual(r1, r2)

    def test_api_mode_without_key_degrades_visibly(self):
        with mock.patch.object(api_ai.config, "openrouter_key", return_value=""):
            res = engine.evaluate_answer("API Mode", Q, "memorizes noise")
        self.assertEqual(res["scoring_mode"], "rule_based_fallback")
        self.assertIn("API unavailable", res["explanation"])

    def test_hybrid_makes_exactly_one_api_call(self):
        db = fresh_db()
        items = [{"question": Q, "transcript": f"answer {i} memorizes", "evaluation": {"final_score": 10, "explanation": ""}} for i in range(4)]
        batch = '{"results": [' + ",".join('{"n": %d, "correctness_score": 80, "knowledge_depth_score": 60, "completeness_score": 70, "status": "partial"}' % (i + 1) for i in range(4)) + ']}'
        with mock.patch.object(api_ai, "chat", return_value=batch) as chat:
            out = engine.finalize_hybrid(items, db=db, api_key="k")
            engine.finalize_hybrid(items, db=db, api_key="k")  # repeat: cached
        self.assertEqual(chat.call_count, 1)
        self.assertTrue(all(o["scoring_mode"] == "hybrid_api_batch" for o in out))

    def test_hybrid_api_failure_keeps_local_scores(self):
        items = [{"question": Q, "transcript": "memorizes", "evaluation": {"final_score": 42, "explanation": "local"}}]
        with mock.patch.object(api_ai, "chat", side_effect=ConnectionError("x")):
            out = engine.finalize_hybrid(items, api_key="k")
        self.assertEqual(out[0]["final_score"], 42)
        self.assertIn("Hybrid API step failed", out[0]["explanation"])

    def test_empty_answer_never_calls_api(self):
        with mock.patch.object(api_ai, "chat") as chat:
            res = engine.evaluate_answer("API Mode", Q, "")
        chat.assert_not_called(); self.assertEqual(res["final_score"], 0)


if __name__ == "__main__":
    unittest.main()
