import json
import tempfile
import unittest
from pathlib import Path

from digital_twin import (
    answer_question,
    build_chunks,
    load_profile,
    retrieve_context,
)


SAMPLE_PROFILE = {
    "name": "Sam",
    "skills": ["Python", "Data analysis"],
    "projects": [{"name": "Help Bot", "description": "A support chatbot"}],
}


class DigitalTwinTests(unittest.TestCase):
    def test_load_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(SAMPLE_PROFILE), encoding="utf-8")
            self.assertEqual(load_profile(path)["name"], "Sam")

    def test_build_chunks_splits_structured_list_items(self):
        chunks = build_chunks(SAMPLE_PROFILE)
        project_chunks = [item for item in chunks if item["section"] == "Projects"]
        self.assertEqual(len(project_chunks), 1)
        self.assertIn("Help Bot", project_chunks[0]["text"])

    def test_retrieval_finds_skill_synonyms(self):
        chunks = build_chunks(SAMPLE_PROFILE)
        results = retrieve_context("What technology do you know?", chunks)
        self.assertEqual(results[0]["section"], "Skills")

    def test_answer_works_without_ollama(self):
        chunks = build_chunks(SAMPLE_PROFILE)
        answer, context, engine = answer_question("Tell me about your projects", chunks)
        self.assertIn("Help Bot", answer)
        self.assertTrue(context)
        self.assertEqual(engine, "Built-in retrieval")

    def test_unknown_answer_is_honest(self):
        chunks = build_chunks(SAMPLE_PROFILE)
        answer, context, _ = answer_question("What is your favorite food?", chunks)
        self.assertIn("could not find", answer)
        self.assertEqual(context, [])


if __name__ == "__main__":
    unittest.main()
