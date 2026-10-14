import json
import re
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError
from .config import GEMINI_API_KEY, GEMINI_MODEL

class AIUnavailable(RuntimeError):
    pass

def get_client():
    if not GEMINI_API_KEY or GEMINI_API_KEY == "replace_with_your_key":
        raise AIUnavailable("Gemini API key is missing. Add GEMINI_API_KEY to backend/.env and restart the backend.")
    return genai.Client(api_key=GEMINI_API_KEY)

def generate(prompt: str, system: str | None = None) -> str:
    client = get_client()
    cfg = types.GenerateContentConfig(system_instruction=system) if system else None
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=cfg)
    except APIError as e:
        if e.code == 503:
            raise AIUnavailable("Gemini is temporarily experiencing high demand (503 UNAVAILABLE). Wait briefly, then try again.") from e
        raise
    text = getattr(response, "text", None)
    if not text:
        raise AIUnavailable("Gemini returned an empty response. Try again or check the model/API quota.")
    return text.strip()

def json_from_text(text: str):
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for left, right in (("{", "}"), ("[", "]")):
            start, end = cleaned.find(left), cleaned.rfind(right)
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    pass
        raise AIUnavailable("AI response was not valid structured data. Please retry.")

GROUNDING = "You are a careful learning assistant. Use only the supplied source as factual evidence. Do not invent source claims or pretend to know missing details. If the source does not contain the answer, clearly say so and optionally label any general explanation as outside context. Preserve technical terms and explain clearly."

def summarize(content: str, title: str, length: str = "detailed") -> str:
    limit = {"short": "about 150 words", "medium": "about 350 words", "detailed": "a thorough structured summary"}.get(length, "a thorough structured summary")
    prompt = f"Create {limit} of the source titled {title!r}. Include the central thesis, key ideas, examples, terminology, conclusions, and practical takeaways. Use headings and bullets. Do not invent timestamps.\n\nSOURCE:\n{content[:90000]}"
    return generate(prompt, GROUNDING)

def make_notes(content: str, title: str, style: str = "study notes") -> str:
    prompt = f"Create {style} for {title!r}. Include title, learning objectives, topic-wise headings, definitions, step-by-step explanations where appropriate, examples present in source, key takeaways, and 5 revision points. Clearly flag gaps instead of inventing facts.\n\nSOURCE:\n{content[:90000]}"
    return generate(prompt, GROUNDING)

def chat_source(content: str, question: str, history: list[dict]) -> str:
    hist = "\n".join(f"{str(x.get('role', 'user'))[:20]}: {str(x.get('content', ''))[:1500]}" for x in history[-8:])
    prompt = f"SOURCE MATERIAL (may be incomplete):\n{content[:70000]}\n\nRECENT CONVERSATION:\n{hist}\n\nUSER QUESTION:\n{question}\n\nAnswer with concise explanations. Refer to a heading or timestamp only if present in the source. If the source does not support an answer, say: 'I couldn't find that in the selected material.'"
    return generate(prompt, GROUNDING)

def quiz(content: str, count: int, difficulty: str):
    prompt = f'''Generate {count} multiple-choice questions from this source at {difficulty} difficulty. Return ONLY a JSON array. Each item: {{"question":string,"options":[4 strings],"answer_index":integer 0-3,"explanation":string}}. Exactly one correct answer per question. Do not ask about information absent from source.\nSOURCE:\n{content[:65000]}'''
    data = json_from_text(generate(prompt, GROUNDING))
    if isinstance(data, dict):
        data = data.get("questions", [])
    return data

def flashcards(content: str, count: int):
    prompt = f'''Create {count} useful revision flashcards from this source. Return ONLY a JSON array of objects {{"front":string,"back":string,"topic":string}}. Keep answers accurate and concise.\nSOURCE:\n{content[:65000]}'''
    data = json_from_text(generate(prompt, GROUNDING))
    if isinstance(data, dict):
        data = data.get("flashcards", [])
    return data

def interview_question(content: str, difficulty: str, interview_type: str, index: int, count: int, prior: list[dict]):
    previous = json.dumps(prior[-8:], ensure_ascii=False)
    prompt = f"Act as a supportive but rigorous interviewer. Ask exactly ONE question based on this source. Type={interview_type}; difficulty={difficulty}; question {index} of {count}. Avoid repeating these prior Q/A pairs: {previous}. Do not reveal the answer. Keep it natural and specific to the source.\nSOURCE:\n{content[:60000]}"
    return generate(prompt, GROUNDING)

def evaluate_answer(content: str, question: str, answer: str, difficulty: str):
    prompt = f'''Evaluate a learner's mock interview answer using the provided source. Return ONLY JSON object with keys score (0-100 integer), verdict (short string), strengths (array of strings), improvements (array of strings), model_answer (string), follow_up (string). Be constructive, reward reasonable phrasing, do not demand details absent from source. Difficulty={difficulty}.\nSOURCE:\n{content[:50000]}\nQUESTION:\n{question}\nLEARNER ANSWER:\n{answer}'''
    return json_from_text(generate(prompt, GROUNDING))

def analyze_video_file(path, mime_type: str, prompt: str):
    client = get_client()
    uploaded = client.files.upload(file=str(path), config={"mime_type": mime_type})
    for _ in range(60):
        state = getattr(uploaded, "state", None)
        state_name = str(getattr(state, "name", state)).upper()
        if "PROCESSING" not in state_name:
            break
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)
    state = getattr(uploaded, "state", None)
    state_name = str(getattr(state, "name", state)).upper()
    if "FAILED" in state_name:
        raise AIUnavailable("Gemini could not process this video file. Try a shorter MP4 video or provide a transcript.")
    response = client.models.generate_content(model=GEMINI_MODEL, contents=[uploaded, prompt])
    text = getattr(response, "text", None)
    if not text:
        raise AIUnavailable("Gemini returned no video analysis. Try a shorter video or another supported format.")
    return text.strip()
