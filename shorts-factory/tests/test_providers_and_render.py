import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shorts_factory import pipeline, presets, schema
from shorts_factory.__main__ import main
from shorts_factory.providers import images, script, tts

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent / "examples" / "fuzzbois-dry-run.json"
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
NO_KEYS = {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "SHORTS_SCRIPT": "", "SHORTS_TTS": ""}


def fake_reply(n=5):
    return json.dumps({"title": "Fake", "slides": [{"narration": f"n{i}", "image_prompt": f"p{i}"}
                                                   for i in range(n)]})


class ScriptProviderTests(unittest.TestCase):
    def test_prompt_mentions_schema_and_rules(self):
        system, user = script.build_prompt("Fuzzboi hex codes", presets.get("fuzzbois"), slides=20)
        self.assertIn(schema.SCHEMA_ID, system)
        self.assertIn("Write 8 slides", system)  # clamped to the maximum
        self.assertIn("hex code", system)
        self.assertEqual(user, "Topic: Fuzzboi hex codes")

    def test_generate_fills_defaults(self):
        calls = []
        s = script.generate("topic", presets.get("mommys"),
                            call=lambda sys_, msgs: calls.append(msgs) or f"```json\n{fake_reply()}\n```")
        self.assertEqual(len(calls), 1)
        self.assertEqual(s.preset, "mommys")
        self.assertEqual(s.topic, "topic")

    def test_generate_retries_once_with_problems(self):
        replies = iter([fake_reply(3), fake_reply(6)])
        seen = []

        def call(system, messages):
            seen.append(list(messages))
            return next(replies)
        s = script.generate("t", presets.get("plain"), call=call)
        self.assertEqual(len(s.slides), 6)
        self.assertIn("5 to 8", seen[1][-1]["content"])

    def test_generate_gives_up_after_two(self):
        with self.assertRaises(schema.ScriptError):
            script.generate("t", presets.get("plain"), call=lambda s, m: "nothing")

    def test_pick(self):
        with mock.patch.dict(os.environ, NO_KEYS):
            with self.assertRaises(RuntimeError):
                script.pick("auto")
        with mock.patch.dict(os.environ, {**NO_KEYS, "OPENAI_API_KEY": "x"}):
            self.assertEqual(script.pick(None), "openai")
        with mock.patch.dict(os.environ, {**NO_KEYS, "OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "y"}):
            self.assertEqual(script.pick("auto"), "anthropic")
            self.assertEqual(script.pick("openai"), "openai")


class TtsAndImagePickTests(unittest.TestCase):
    def test_tts_pick(self):
        nothing = {"sapi": False, "piper": False, "espeak": False, "openai": True, "silent": True}
        with mock.patch.dict(os.environ, NO_KEYS), mock.patch.object(tts, "available", return_value=nothing):
            self.assertEqual(tts.pick("auto"), "silent")  # never falls through to a paid provider
        with mock.patch.object(tts, "available", return_value={**nothing, "espeak": True, "sapi": True}):
            self.assertEqual(tts.pick(None), "sapi")
        with self.assertRaises(ValueError):
            tts.pick("openai", offline=True)
        with self.assertRaises(ValueError):
            tts.pick("robot")

    def test_tts_cache_name_changes_with_text(self):
        self.assertNotEqual(tts.cache_name(0, "espeak", "a"), tts.cache_name(0, "espeak", "b"))
        self.assertTrue(tts.cache_name(2, "silent", "a").startswith("voice-03-silent-"))

    def test_image_source(self):
        o = pipeline.Options()
        self.assertEqual(pipeline.resolve_image_source(o), "placeholder")
        o.images_dir = Path(".")
        self.assertEqual(pipeline.resolve_image_source(o), "folder")
        with self.assertRaises(ValueError):
            pipeline.resolve_image_source(pipeline.Options(images_from="openai", offline=True))
        with self.assertRaises(ValueError):
            pipeline.resolve_image_source(pipeline.Options(images_from="folder"))

    def test_folder_assignment(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name in ("b.png", "a.PNG", "notes.txt", "c.jpg"):
                (d / name).write_bytes(b"x")
            files = images.list_folder(d)
            self.assertEqual([f.name for f in files], ["a.PNG", "b.png", "c.jpg"])
            s = schema.load(EXAMPLE)
            for sl in s.slides:
                sl.image = None
            s.slides[1].image = str(d / "c.jpg")
            got = images.assign(s, files)
            self.assertEqual([g.name for g in got], ["a.PNG", "c.jpg", "b.png", "c.jpg", "a.PNG", "b.png"])
            s.slides[0].image = "missing.png"
            with self.assertRaises(FileNotFoundError):
                images.assign(s, files)
            with self.assertRaises(FileNotFoundError):
                images.list_folder(d / "nope")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg and ffprobe are needed for the render test")
class RenderTests(unittest.TestCase):
    def test_offline_render_small(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            out = d / "short.mp4"
            r = pipeline.run(pipeline.Options(script_path=EXAMPLE, offline=True, tts="silent", width=216,
                                              height=384, supersample=1, out=out, workdir=d / "work"),
                             say=lambda *_: None)
            self.assertTrue(out.is_file())
            self.assertEqual((r.probe["width"], r.probe["height"]), (216, 384))
            self.assertEqual(r.probe["audio_codec"], "aac")
            self.assertAlmostEqual(r.probe["duration"], r.plan.total, delta=0.25)
            self.assertTrue((d / "work" / "captions.ass").is_file())
            self.assertTrue((d / "work" / "script.json").is_file())

    def test_cli_with_own_pictures_folder(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pics = d / "pics"
            pics.mkdir()
            for i, colour in enumerate(("ff3ec8", "5ffbf1")):
                images.placeholder_ppm(pics / f"{i}.ppm", width=90, height=160, top="000000", bottom=colour,
                                       body=colour, seed=i)
            script_file = d / "s.json"
            data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            data["slides"] = data["slides"][:5]
            script_file.write_text(json.dumps(data), encoding="utf-8")
            code = main(["make", "--offline", "--script", str(script_file), "--images", str(pics), "--tts", "silent",
                         "--width", "180", "--height", "320", "--supersample", "1", "--crossfade", "0.3",
                         "--out", str(d / "o.mp4"), "--work", str(d / "w")])
            self.assertEqual(code, 0)
            result = json.loads((d / "w" / "result.json").read_text())
            self.assertEqual(result["images"], "folder")
            self.assertEqual((result["width"], result["height"]), (180, 320))

    def test_offline_refuses_topic_only(self):
        self.assertEqual(main(["make", "--offline", "--topic", "x"]), 2)


if __name__ == "__main__":
    unittest.main()
