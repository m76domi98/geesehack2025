"""Every Gemini call lives here. Routes call these functions; tests monkeypatch them."""
import base64
import io
import os
import wave
from functools import cache

from google import genai
from pydantic import BaseModel, Field, model_validator

TEXT_MODEL = "gemini-3.8-flash"
TTS_MODEL = "gemini-3.8-flash-tts"
HOSTS = ("Alex", "Sam")
WORDS_PER_MINUTE = 150
REVIEW_MINUTES = 4

VOICES = ("Puck", "Kore", "Charon", "Aoede", "Fenrir", "Leda", "Orus", "Zephyr")
LENGTHS = (5, 10, 15)
DEPTHS = {
    "intro": "Assume no prior knowledge. Build intuition with everyday analogies before any jargon.",
    "exam": "Assume the listener is revising for an exam. Be precise, cover definitions, "
            "common mistakes and the kind of thing that gets asked.",
}


class Line(BaseModel):
    speaker: str = Field(description=f"Exactly one of: {', '.join(HOSTS)}")
    text: str


class Chapter(BaseModel):
    title: str
    lines: list[Line]


class Concept(BaseModel):
    name: str = Field(description="Short, canonical name, e.g. 'Mitosis'. Reuse earlier names exactly.")
    summary: str = Field(description="One sentence.")


class QuizQuestion(BaseModel):
    concept: str = Field(description="Name of the concept this question tests, from `concepts`.")
    question: str
    choices: list[str] = Field(description="4 options.")
    answer_index: int = Field(description="0-based index of the correct choice.")
    explanation: str = Field(description="Why the answer is right, in 1-2 sentences.")

    @model_validator(mode="after")
    def answer_in_range(self) -> "QuizQuestion":
        if not 0 <= self.answer_index < len(self.choices):
            raise ValueError("answer_index out of range")
        return self


class Lesson(BaseModel):
    title: str
    chapters: list[Chapter]
    concepts: list[Concept]
    quiz: list[QuizQuestion]


@cache
def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _pdf(data: bytes) -> dict:
    return {"type": "document", "data": base64.b64encode(data).decode(), "mime_type": "application/pdf"}


def _hosts_brief(options: dict) -> str:
    a, b = HOSTS
    return (
        f"Write a podcast episode as a natural conversation between two hosts, {a} and {b}. "
        f"{a} leads and explains; {b} asks the questions a curious student would, pushes back, "
        "and summarises in their own words. Explain and teach the material, never read it out. "
        "Use concrete examples. No stage directions, sound effects or markdown in the lines. "
        f"{DEPTHS[options['depth']]}"
    )


def _structured(content: list[dict]) -> Lesson:
    interaction = _client().interactions.create(
        model=TEXT_MODEL,
        input=content,
        response_format={"type": "text", "mime_type": "application/json", "schema": Lesson.model_json_schema()},
    )
    return Lesson.model_validate_json(interaction.output_text)


def write_lesson(pdf: bytes, prior_concepts: list[dict], options: dict) -> dict:
    words = options["length"] * WORDS_PER_MINUTE
    if prior_concepts:
        earlier = "; ".join(f"{c['name']}: {c['summary']}" for c in prior_concepts)
        continuity = (
            f"This is a later lesson in a course. Earlier lessons covered: {earlier}. "
            "Briefly connect to them where relevant and reuse their exact concept names."
        )
    else:
        continuity = "This is the first lesson in the course."
    prompt = (
        f"{_hosts_brief(options)}\n\n{continuity}\n\n"
        f"Target about {words} words of dialogue, split into 3-5 titled chapters. "
        "List the 3-6 key concepts taught. Write a 5-question multiple-choice quiz, "
        "each question tagged with one of those concepts."
    )
    return _structured([_pdf(pdf), {"type": "text", "text": prompt}]).model_dump()


def write_review(pdfs: list[bytes], concepts: list[dict], options: dict) -> dict:
    words = REVIEW_MINUTES * WORDS_PER_MINUTE
    targets = "; ".join(f"{c['name']}: {c['summary']}" for c in concepts)
    prompt = (
        f"{_hosts_brief(options)}\n\n"
        f"This is a short review episode. The listener struggled with or is due to revisit: {targets}. "
        "Cover ONLY these concepts, using different examples and angles from a first explanation. "
        f"Target about {words} words in 1-3 chapters. `concepts` must be exactly the concepts above, "
        "with the same names. Write one or two fresh quiz questions per concept."
    )
    return _structured([*map(_pdf, pdfs), {"type": "text", "text": prompt}]).model_dump()


def _speak(lines: list[dict], voices: tuple[str, str]) -> bytes:
    interaction = _client().interactions.create(
        model=TTS_MODEL,
        input=[{
            "type": "user_input",
            "content": [
                {"type": "text", "text": line["text"],
                 "annotations": [{"type": "speech_metadata", "speaker": line["speaker"]}]}
                for line in lines
            ],
        }],
        response_format={"type": "audio"},
        generation_config={"speech_config": {"speakers": [
            {"speaker": host, "voice": voice} for host, voice in zip(HOSTS, voices)
        ]}},
    )
    return base64.b64decode(interaction.output_audio.data)


def join_wavs(clips: list[bytes]) -> bytes:
    """Concatenate WAV clips that share a format (TTS always returns 24 kHz mono 16-bit)."""
    out = io.BytesIO()
    with wave.open(out, "wb") as writer:
        for i, clip in enumerate(clips):
            with wave.open(io.BytesIO(clip), "rb") as reader:
                if i == 0:
                    writer.setparams(reader.getparams())
                writer.writeframes(reader.readframes(reader.getnframes()))
    return out.getvalue()


def synthesize(script: dict, voices: tuple[str, str]) -> bytes:
    # ponytail: one TTS call per chapter keeps each under the input limit; run them in parallel if too slow
    return join_wavs([_speak(chapter["lines"], voices) for chapter in script["chapters"]])


def answer(pdfs: list[bytes], history: list[dict], question: str) -> str:
    transcript = "\n".join(f"{turn['role']}: {turn['text']}" for turn in history)
    prompt = (
        "You are a study assistant. Answer using the attached course documents. "
        "If they don't cover the question, say so briefly before answering from general knowledge. "
        "Be concise.\n\n"
        f"Conversation so far:\n{transcript or '(none)'}\n\nStudent: {question}"
    )
    interaction = _client().interactions.create(
        model=TEXT_MODEL, input=[*map(_pdf, pdfs), {"type": "text", "text": prompt}]
    )
    return interaction.output_text
