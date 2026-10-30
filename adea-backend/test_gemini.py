import io
import wave

import pytest
from pydantic import ValidationError

import gemini


def _wav(frames: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(frames)
    return out.getvalue()


def test_join_wavs_concatenates_frames():
    joined = gemini.join_wavs([_wav(b"\x01\x00" * 10), _wav(b"\x02\x00" * 5)])

    with wave.open(io.BytesIO(joined), "rb") as r:
        assert (r.getnframes(), r.getframerate()) == (15, 24000)


def test_quiz_question_rejects_answer_out_of_range():
    with pytest.raises(ValidationError):
        gemini.QuizQuestion(concept="c", question="q", choices=["a", "b"], answer_index=2, explanation="e")


def test_synthesize_renders_each_chapter(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini, "_speak", lambda lines, voices: calls.append(lines) or _wav(b"\x00\x00"))
    script = {"chapters": [{"lines": [{"speaker": "Alex", "text": "a"}]},
                           {"lines": [{"speaker": "Sam", "text": "b"}]}]}

    gemini.synthesize(script, ("Puck", "Kore"))

    assert len(calls) == 2
