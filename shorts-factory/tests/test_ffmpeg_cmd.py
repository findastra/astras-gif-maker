import re
import unittest
from pathlib import Path

from shorts_factory import captions, ffmpeg_cmd, presets, timing


def build(n=5, **kw):
    p = timing.plan([1.5 + i * 0.3 for i in range(n)], crossfade=0.5, fps=30)
    imgs = [Path(f"/pics/slide {i}.png") for i in range(n)]
    auds = [Path(f"/voice/v{i}.wav") for i in range(n)]
    motions = (["zoom-in", "zoom-out", "pan-left", "pan-right", "pan-up", "pan-down", "still"] * 2)[:n]
    args = dict(images=imgs, audios=auds, plan=p, motions=motions, output=Path("/out/v.mp4"), workdir=Path("/w"))
    args.update(kw)
    return p, ffmpeg_cmd.build_command(**args)


class CommandTests(unittest.TestCase):
    def test_inputs_and_outputs(self):
        p, r = build()
        a = r.args
        self.assertEqual(a.count("-i"), 10)
        # pictures first, then voices, each path passed as one argument (spaces survive)
        self.assertEqual(a[a.index("-i") + 1], "/pics/slide 0.png")
        self.assertIn("/voice/v4.wav", a)
        self.assertEqual(a[-1], "/out/v.mp4")
        self.assertEqual(a[a.index("-t") + 1], f"{p.total:.4f}")
        for flag, val in (("-c:v", "libx264"), ("-pix_fmt", "yuv420p"), ("-c:a", "aac"), ("-r", "30")):
            self.assertEqual(a[a.index(flag) + 1], val)
        self.assertEqual(r.cwd, Path("/w"))

    def test_filter_graph(self):
        p, r = build()
        g = r.filter_graph
        self.assertEqual(g.count("zoompan="), 5)
        self.assertIn("s=1080x1920", g)
        self.assertIn("scale=2160:3840:force_original_aspect_ratio=increase", g)
        offsets = [float(x) for x in re.findall(r"xfade=transition=fade:duration=[\d.]+:offset=([\d.]+)", g)]
        self.assertEqual(len(offsets), 4)
        for got, want in zip(offsets, p.xfade_offsets):
            self.assertAlmostEqual(got, want, places=3)
        for i, slot in enumerate(p.audio_slots):
            self.assertIn(f"[{5 + i}:a]", g)
            self.assertIn(f"apad=whole_dur={slot:.4f}", g)
        self.assertIn("[a0][a1][a2][a3][a4]concat=n=5:v=0:a=1[aout]", g)
        self.assertIn("[x4]subtitles=captions.ass,format=yuv420p[vout]", g)
        for i in range(5):
            self.assertIn(f"d={p.frames(i)}:", g)

    def test_no_captions_and_size(self):
        _, r = build(captions_file=None, width=540, height=960, supersample=1)
        self.assertNotIn("subtitles", r.filter_graph)
        self.assertIn("s=540x960", r.filter_graph)
        self.assertIn("scale=540:960:", r.filter_graph)

    def test_single_slide(self):
        p = timing.plan([2.0])
        r = ffmpeg_cmd.build_command(images=[Path("a.png")], audios=[Path("a.wav")], plan=p, motions=["still"],
                                     output=Path("o.mp4"), workdir=Path("."))
        self.assertNotIn("xfade", r.filter_graph)
        self.assertIn("[v0]subtitles=", r.filter_graph)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            build(width=1081)
        with self.assertRaises(ValueError):
            build(transition="explode")
        p = timing.plan([1.0, 1.0])
        with self.assertRaises(ValueError):
            ffmpeg_cmd.build_command(images=[Path("a")], audios=[Path("a"), Path("b")], plan=p,
                                     motions=["still", "still"], output=Path("o"), workdir=Path("."))

    def test_motion_expressions(self):
        z, x, y = ffmpeg_cmd.motion_expr("zoom-in", 91)
        self.assertEqual(z, "1+0.15*(on/90)")
        self.assertEqual(ffmpeg_cmd.motion_expr("pan-right", 91)[1], "(iw-iw/zoom)*(on/90)")
        self.assertEqual(ffmpeg_cmd.motion_expr("pan-up", 91)[2], "(ih-ih/zoom)*(1-(on/90))")
        for m in ("zoom-out", "pan-left", "pan-down", "still"):
            exprs = ffmpeg_cmd.motion_expr(m, 10)
            self.assertEqual(len(exprs), 3)
            self.assertFalse(any("," in e for e in exprs), "commas would break the filter graph")
        with self.assertRaises(ValueError):
            ffmpeg_cmd.motion_expr("spin", 10)


class CaptionFileTests(unittest.TestCase):
    def test_ass_helpers(self):
        self.assertEqual(captions.ass_time(0), "0:00:00.00")
        self.assertEqual(captions.ass_time(61.257), "0:01:01.26")
        self.assertEqual(captions.ass_time(3725.5), "1:02:05.50")
        self.assertEqual(captions.ass_color("ff3ec8"), "&H00C83EFF")
        self.assertEqual(captions.ass_color("#000000", 0x80), "&H80000000")
        self.assertEqual(captions.escape_text("a{b}\nc"), "a(b)\\Nc")

    def test_build_ass(self):
        cues = [timing.Cue(0.25, 1.0, "hello there"), timing.Cue(1.0, 1.8, "{\\b1}sneaky")]
        text = captions.build_ass(cues, presets.get("fuzzbois"), width=1080, height=1920)
        self.assertIn("PlayResX: 1080", text)
        self.assertIn("Style: Cap,Arial Black,84,", text)
        lines = [l for l in text.splitlines() if l.startswith("Dialogue:")]
        self.assertEqual(len(lines), 2)
        self.assertIn("0:00:00.25,0:00:01.00,Cap", lines[0])
        self.assertTrue(lines[0].endswith("HELLO THERE"))
        self.assertIn(",Hi,", lines[1])
        self.assertNotIn("{\\B1}", lines[1])
        small = captions.build_ass(cues, presets.get("plain"), width=540, height=960)
        self.assertIn("Style: Cap,Arial,42,", small)


if __name__ == "__main__":
    unittest.main()
