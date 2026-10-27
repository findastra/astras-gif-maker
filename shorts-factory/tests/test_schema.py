import copy
import json
import unittest
from pathlib import Path

from shorts_factory import schema

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "fuzzbois-dry-run.json"


def good(n=5):
    return {"schema": schema.SCHEMA_ID, "title": "T", "slides": [
        {"narration": f"line {i}", "image_prompt": f"pic {i}"} for i in range(n)]}


class SchemaTests(unittest.TestCase):
    def test_example_is_valid(self):
        s = schema.load(EXAMPLE)
        self.assertEqual(len(s.slides), 6)
        self.assertEqual(s.preset, "fuzzbois")
        self.assertEqual(s.slides[0].hex, "ff3ec8")
        self.assertEqual(s.base_dir, EXAMPLE.parent)

    def test_minimal_valid(self):
        self.assertEqual(schema.validate(good()), [])
        s = schema.parse(good())
        self.assertEqual(s.preset, "plain")
        self.assertEqual(s.slides[0].caption_text, "line 0")

    def test_slide_count_bounds(self):
        self.assertIn("5 to 8", " ".join(schema.validate(good(4))))
        self.assertIn("5 to 8", " ".join(schema.validate(good(9))))
        self.assertEqual(schema.validate(good(8)), [])
        self.assertEqual(schema.validate(good(2), min_slides=1), [])

    def test_required_fields_and_types(self):
        d = good()
        del d["title"]
        d["slides"][0]["narration"] = "  "
        del d["slides"][1]["image_prompt"]
        d["slides"][2]["motion"] = "spin"
        d["slides"][3]["hex"] = "red"
        d["slides"][4]["colour"] = "x"
        problems = schema.validate(d)
        joined = " | ".join(problems)
        for needle in ("title is required", "slide 1: narration", "slide 2: image_prompt", "slide 3: motion",
                       "slide 4: hex", "slide 5: unknown field(s) colour"):
            self.assertIn(needle, joined)
        with self.assertRaises(schema.ScriptError) as cm:
            schema.parse(d)
        self.assertEqual(len(cm.exception.problems), len(problems))

    def test_wrong_schema_and_shapes(self):
        self.assertEqual(schema.validate([]), ["the script must be a JSON object"])
        d = good()
        d["schema"] = "v0"
        self.assertTrue(any("schema must be" in p for p in schema.validate(d)))
        d = good()
        d["slides"] = "nope"
        self.assertIn("slides must be a list", schema.validate(d))

    def test_narration_length_limit(self):
        d = good()
        d["slides"][0]["narration"] = "x" * (schema.MAX_NARRATION_CHARS + 1)
        self.assertTrue(any("characters" in p for p in schema.validate(d)))

    def test_hex_normalised(self):
        d = good()
        d["slides"][0]["hex"] = "#FF3EC8"
        self.assertEqual(schema.parse(d).slides[0].hex, "ff3ec8")

    def test_round_trip(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        again = schema.parse(schema.parse(copy.deepcopy(data)).to_json()).to_json()
        self.assertEqual(again["slides"], data["slides"])

    def test_extract_json(self):
        body = json.dumps(good())
        self.assertEqual(schema.extract_json(body)["title"], "T")
        self.assertEqual(schema.extract_json(f"```json\n{body}\n```")["title"], "T")
        self.assertEqual(schema.extract_json(f"Here you go:\n{body}\nEnjoy")["title"], "T")
        with self.assertRaises(schema.ScriptError):
            schema.extract_json("no json here")


if __name__ == "__main__":
    unittest.main()
