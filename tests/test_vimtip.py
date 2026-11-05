import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import vimtip


INDEX = """\
1. Insert mode *insert-index*
Tag\tKey\tAction\t~
|i_CTRL-A|\tCTRL-A\t\tinsert previously
\t\t\t\tinserted text
|i_CTRL-A|\tCTRL-@\t\tinsert previously inserted text
\t\tCTRL-F\t\tnot used in this mode
|i_CTRL-B|\tCTRL-B\t\tmove to previous word
2. Normal mode *normal-index*
|CTRL-A|\tCTRL-A\t\tadd one to number
2.1 Text objects *objects*
|iw|\tiw\t\tselect inner word
3. Visual mode *visual-index*
|v_CTRL-A|\tCTRL-A\t\tincrement selected numbers
4. Command-line editing *ex-edit-index*
|c_CTRL-A|\tCTRL-A\t\tnot included
5. Ex commands *Ex-command* *ex-cmd-index* *:index*
|:write|\t:w[rite]\t\twrite the buffer to a file
"""


class ParseIndexTests(unittest.TestCase):
    def test_extracts_supported_modes_and_wrapped_summaries(self) -> None:
        tips = {tip.tag: tip for tip in vimtip.parse_index(INDEX, "Vim")}

        self.assertEqual(
            tips["i_CTRL-A"].description, "insert previously inserted text"
        )
        self.assertEqual(tips["i_CTRL-A"].mode, "Insert")
        self.assertEqual(tips["CTRL-A"].mode, "Normal")
        self.assertEqual(tips["iw"].mode, "Normal")
        self.assertEqual(tips["v_CTRL-A"].mode, "Visual")
        self.assertEqual(tips[":write"].mode, "Ex")
        self.assertNotIn("i_CTRL-F", tips)
        self.assertNotIn("c_CTRL-A", tips)

    def test_deduplicates_alias_rows_and_editor_indexes(self) -> None:
        tips = vimtip.merge_indexes({"Vim": INDEX, "Neovim": INDEX})
        increment = next(tip for tip in tips if tip.tag == "i_CTRL-A")

        self.assertEqual(increment.description, "insert previously inserted text")
        self.assertEqual(increment.editors, ("Neovim", "Vim"))


class RotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tips: list[vimtip.Tip] = [
            vimtip.Tip(f"tag-{number}", "Normal", str(number), "summary", ("Vim",))
            for number in range(3)
        ]

    def test_repeated_invocations_on_same_day_return_same_tip(self) -> None:
        first, state = vimtip.choose_tip(
            self.tips, {}, date(2026, 11, 5), chooser=lambda options: options[1]
        )
        second, unchanged = vimtip.choose_tip(
            self.tips, state, date(2026, 11, 5), chooser=lambda options: options[0]
        )

        self.assertEqual(second, first)
        self.assertEqual(unchanged, state)

    def test_no_repeats_until_catalog_is_exhausted(self) -> None:
        state = vimtip.RotationState()
        served: list[str] = []
        for day in range(1, 4):
            tip, state = vimtip.choose_tip(
                self.tips,
                state,
                date(2026, 11, day),
                chooser=lambda options: options[0],
            )
            served.append(tip.tag)

        self.assertEqual(len(set(served)), len(self.tips))
        next_tip, _ = vimtip.choose_tip(
            self.tips,
            state,
            date(2026, 11, 4),
            chooser=lambda options: options[0],
        )
        self.assertEqual(next_tip.tag, served[0])

    def test_empty_catalog_has_actionable_error(self) -> None:
        with self.assertRaisesRegex(vimtip.VimTipError, "no actionable commands"):
            vimtip.choose_tip([], {}, date(2026, 11, 5))


class StateTests(unittest.TestCase):
    def test_round_trip_and_malformed_state_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "nested" / "state.json"
            expected = vimtip.RotationState(
                version=1,
                seen=["CTRL-A"],
                last_date="2026-11-05",
                last_tip="CTRL-A",
            )

            vimtip.write_state(path, expected)
            self.assertEqual(vimtip.read_state(path), expected)

            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(vimtip.read_state(path), {})

    def test_reset_starts_a_fresh_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "state.json"
            state_path.write_text(
                json.dumps({
                    "version": 1,
                    "seen": [tip.tag for tip in vimtip.merge_indexes({"Vim": INDEX})],
                    "last_date": "2026-11-04",
                    "last_tip": "i_CTRL-A",
                }),
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch("vimtip.load_indexes", return_value={"Vim": INDEX, "Neovim": INDEX}),
                patch("vimtip.default_state_directory", return_value=Path(temporary_directory)),
                contextlib.redirect_stdout(output),
            ):
                result = vimtip.main(["--reset"])

            state = vimtip.read_state(state_path)
            self.assertEqual(result, 0)
            self.assertEqual(len(state.get("seen", [])), 1)
            self.assertIn("Help: :help", output.getvalue())

    def test_missing_editor_is_reported(self) -> None:
        with patch("vimtip.shutil.which", return_value=None):
            with self.assertRaisesRegex(vimtip.VimTipError, "required editor not found: vim"):
                vimtip.load_indexes()


if __name__ == "__main__":
    unittest.main()