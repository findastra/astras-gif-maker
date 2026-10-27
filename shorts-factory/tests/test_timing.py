import unittest

from shorts_factory import timing


class PlanTests(unittest.TestCase):
    def test_offsets_starts_and_total(self):
        p = timing.plan([2.0, 3.0, 1.0, 2.5, 4.0], crossfade=0.5, fps=30, lead_in=0.25, tail=0.45, min_slide=2.5)
        x = p.crossfade
        self.assertAlmostEqual(x, 0.5)
        # slide length = lead_in + audio + tail (+ crossfade unless last), at least min_slide
        self.assertAlmostEqual(p.durations[0], 0.25 + 2.0 + 0.45 + 0.5)
        self.assertAlmostEqual(p.durations[2], 2.5)          # short narration -> min_slide
        self.assertAlmostEqual(p.durations[4], 0.25 + 4.0 + 0.45)  # last slide has no fade after it
        self.assertEqual(p.starts[0], 0.0)
        for i in range(1, 5):
            self.assertAlmostEqual(p.starts[i], sum(p.durations[:i]) - i * x, places=5)
        self.assertEqual(p.xfade_offsets, p.starts[1:])
        self.assertAlmostEqual(p.total, sum(p.durations) - 4 * x, places=5)
        # the audio track is exactly as long as the picture
        self.assertAlmostEqual(sum(p.audio_slots), p.total, places=5)
        # narration always fits its slot
        for a, slot in zip([2.0, 3.0, 1.0, 2.5, 4.0], p.audio_slots):
            self.assertGreaterEqual(slot, a + 0.25)

    def test_frame_snapping(self):
        p = timing.plan([1.234, 2.345, 3.456, 1.0, 1.5], crossfade=0.47, fps=24)
        for d in p.durations + [p.crossfade]:
            self.assertAlmostEqual(d * 24, round(d * 24), places=6)
        self.assertEqual(p.frames(0), round(p.durations[0] * 24))

    def test_single_slide_has_no_crossfade(self):
        p = timing.plan([2.0], crossfade=0.5)
        self.assertEqual(p.crossfade, 0.0)
        self.assertEqual(p.xfade_offsets, [])
        self.assertAlmostEqual(p.total, p.durations[0])

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            timing.plan([])
        with self.assertRaises(ValueError):
            timing.plan([1.0], crossfade=-1)
        with self.assertRaises(ValueError):
            timing.slide_duration(-1)

    def test_slide_long_enough_for_two_fades(self):
        p = timing.plan([0.1] * 5, crossfade=1.5, min_slide=0.5)
        for d in p.durations:
            self.assertGreater(d, 2 * p.crossfade)
        self.assertTrue(all(b > a for a, b in zip(p.starts, p.starts[1:])))

    def test_estimate(self):
        self.assertAlmostEqual(timing.estimate_speech_seconds("one two three four five six seven eight nine ten "
                                                              "eleven twelve thirteen"), 5.0)
        self.assertEqual(timing.estimate_speech_seconds(""), 0.8)


class CaptionTimingTests(unittest.TestCase):
    def test_chunks(self):
        self.assertEqual(timing.chunk_words("Stop scrolling. This little guy is a Fuzzboi."),
                         ["Stop scrolling.", "This little guy", "is a Fuzzboi."])
        self.assertEqual(timing.chunk_words(""), [])
        for c in timing.chunk_words("its look = a 6-digit hex code and a whole new world of colour"):
            self.assertLessEqual(len(c.split()), 4)
            self.assertNotIn(c.split()[-1].lower(), {"a", "=", "the"})

    def test_cues_stay_inside_their_slide(self):
        audio = [2.0, 3.2, 1.1, 2.4, 2.8]
        caps = ["one two three four five six", "seven eight nine", "ten", "eleven twelve thirteen fourteen",
                "fifteen sixteen"]
        p = timing.plan(audio)
        cues = timing.caption_cues(caps, audio, p)
        self.assertTrue(cues)
        self.assertTrue(all(c.end > c.start for c in cues))
        self.assertTrue(all(b.start >= a.end - 1e-3 for a, b in zip(cues, cues[1:])))
        self.assertLessEqual(cues[-1].end, p.total + 1e-6)
        # every slide's first cue starts after its lead-in
        firsts = {}
        for c in cues:
            i = max(k for k, s in enumerate(p.starts) if s <= c.start + 1e-9)
            firsts.setdefault(i, c)
        for i, c in firsts.items():
            self.assertAlmostEqual(c.start, p.starts[i] + timing.DEFAULT_LEAD_IN, places=2)


if __name__ == "__main__":
    unittest.main()
