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
    monkeypatch.setattr(gemini, "_speak", lambda lines, speakers: calls.append(speakers) or _wav(bytes(2)))
    script = {"chapters": [{"lines": [{"speaker": "Alex", "text": "a"}]},
                           {"lines": [{"speaker": "Sam", "text": "b"}]}]}

    gemini.synthesize(script, {"voice_a": "Puck", "voice_b": "Kore", "rot": 90})

    assert calls == [{"Alex": "Puck", "Tung Tung Tung Sahur": "Kore"}] * 2


class FakeInteractions:
    """Stands in for client.interactions: records each request, returns a canned response."""

    def __init__(self, response):
        self.response = response
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


@pytest.fixture
def fake(monkeypatch):
    def install(**response_fields):
        interactions = FakeInteractions(type("Response", (), response_fields)())
        client = type("Client", (), {"interactions": interactions})()
        monkeypatch.setattr(gemini, "_client", lambda: client)
        return interactions
    return install


LESSON_JSON = (
    '{"title": "T", "chapters": [{"title": "C", "lines": [{"speaker": "Alex", "text": "hi"}]}],'
    ' "concepts": [{"name": "X", "summary": "s"}],'
    ' "quiz": [{"concept": "X", "question": "q", "choices": ["a", "b"], "answer_index": 0, "explanation": "e"}]}'
)
OPTIONS = {"length": 10, "depth": "exam", "rot": 0}


def _prompt(request) -> str:
    return request["input"][-1]["text"]


def test_write_lesson_sends_pdf_schema_and_options(fake):
    api = fake(output_text=LESSON_JSON)

    lesson = gemini.write_lesson(b"%PDF", [], OPTIONS)

    request = api.requests[0]
    assert lesson["concepts"] == [{"name": "X", "summary": "s"}]
    assert request["model"] == gemini.TEXT_MODEL
    assert request["input"][0]["mime_type"] == "application/pdf"
    assert request["response_format"]["schema"] == gemini.Lesson.model_json_schema()
    assert "1500 words" in _prompt(request)
    assert gemini.DEPTHS["exam"] in _prompt(request)
    assert "first lesson" in _prompt(request)


def test_write_lesson_mentions_prior_concepts(fake):
    api = fake(output_text=LESSON_JSON)

    gemini.write_lesson(b"%PDF", [{"name": "Mitosis", "summary": "division"}], OPTIONS)

    assert "Mitosis: division" in _prompt(api.requests[0])


def test_write_lesson_rejects_malformed_json(fake):
    fake(output_text='{"title": "missing everything else"}')

    with pytest.raises(ValidationError):
        gemini.write_lesson(b"%PDF", [], OPTIONS)


def test_write_review_targets_only_given_concepts(fake):
    api = fake(output_text=LESSON_JSON)

    gemini.write_review([b"%PDF", b"%PDF"], [{"name": "ATP", "summary": "energy"}], OPTIONS)

    request = api.requests[0]
    assert [part["type"] for part in request["input"]] == ["document", "document", "text"]
    assert "ATP: energy" in _prompt(request)
    assert f"{gemini.REVIEW_MINUTES * gemini.WORDS_PER_MINUTE} words" in _prompt(request)


def test_speak_maps_hosts_to_voices_and_decodes_audio(fake):
    import base64
    audio = type("Audio", (), {"data": base64.b64encode(b"RIFF").decode()})()
    api = fake(output_audio=audio)

    result = gemini._speak([{"speaker": "Sam", "text": "yo"}], {"Alex": "Puck", "Sam": "Kore"})

    request = api.requests[0]
    assert result == b"RIFF"
    assert request["model"] == gemini.TTS_MODEL
    assert request["generation_config"]["speech_config"]["speakers"] == [
        {"speaker": "Alex", "voice": "Puck"}, {"speaker": "Sam", "voice": "Kore"}
    ]
    assert request["input"][0]["content"][0]["annotations"][0]["speaker"] == "Sam"


def test_answer_includes_history_and_question(fake):
    api = fake(output_text="Mitosis splits cells.")

    reply = gemini.answer([b"%PDF"], [{"role": "user", "text": "earlier q"}], "What is mitosis?")

    assert reply == "Mitosis splits cells."
    assert "user: earlier q" in _prompt(api.requests[0])
    assert "Student: What is mitosis?" in _prompt(api.requests[0])


# --- rot factor ---------------------------------------------------------------------

@pytest.mark.parametrize("rot, expected", [(0, ""), (24, ""), (25, "casual"), (50, "brainrot"), (74, "brainrot"),
                                           (75, "Tung Tung Tung Sahur"), (100, "Tung Tung Tung Sahur")])
def test_rot_tier_boundaries(rot, expected):
    assert expected in gemini.rot_tier(rot)


def test_cohost_becomes_tung_sahur_at_75():
    assert gemini.hosts_for(74) == ("Alex", "Sam")
    assert gemini.hosts_for(75) == ("Alex", "Tung Tung Tung Sahur")


def test_high_rot_prompt_keeps_facts_and_quiz_plain(fake):
    api = fake(output_text=LESSON_JSON.replace('"Alex"', '"Tung Tung Tung Sahur"'))

    gemini.write_lesson(b"%PDF", [], {**OPTIONS, "rot": 90})

    prompt = _prompt(api.requests[0])
    assert "Alex and Tung Tung Tung Sahur" in prompt
    assert gemini.ROT_GUARDRAIL in prompt


def test_rejects_script_with_speaker_that_cannot_be_voiced(fake):
    fake(output_text=LESSON_JSON.replace('"Alex"', '"Narrator"'))

    with pytest.raises(ValueError, match="Narrator"):
        gemini.write_lesson(b"%PDF", [], OPTIONS)


def test_tung_sahur_lines_get_a_speaking_style(fake):
    import base64
    api = fake(output_audio=type("Audio", (), {"data": base64.b64encode(b"RIFF").decode()})())

    gemini._speak([{"speaker": "Tung Tung Tung Sahur", "text": "tung"}, {"speaker": "Alex", "text": "ok"}],
                  {"Alex": "Puck", "Tung Tung Tung Sahur": "Kore"})

    annotations = [part["annotations"][0] for part in api.requests[0]["input"][0]["content"]]
    assert annotations[0]["style"] == gemini.SPEAKER_STYLES["Tung Tung Tung Sahur"]
    assert "style" not in annotations[1]
