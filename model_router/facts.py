import json
from llm import invoke_text
from prompts import TOPIC_KEYS

_KEYS: list = []
_ks: list = []
for _ks in TOPIC_KEYS.values():
	_KEYS.append(_ks[0])
_KEY_HINTS: str = ", ".join(_KEYS)

FACT_PROMPT: str = (
	"You are a fact extractor. "
	"Read the previous question, the user's answer, and the assistant's reply. "
	"Treat the USER message as the answer to the PREVIOUS QUESTION when one is shown. "
	"Extract only DURABLE facts about the user. "
	"Prefer these keys when applicable: " + _KEY_HINTS + ". "
	"Capture project descriptions even if brief. "
	"Also capture any fact the user explicitly asks to remember. "
	"Skip transient info (greetings, confirmations, weather, current question). "
	"Return ONLY a JSON object mapping short snake_case keys to short string values. "
	"If nothing durable, return {{}}.\n\n"
	"PREVIOUS QUESTION: {prev}\n"
	"USER: {user}\n"
	"ASSISTANT: {assistant}\n\n"
	"JSON:"
)


def _find_json_obj(text: str) -> str:
	depth: int = 0
	start: int = -1
	in_str: bool = False
	esc: bool = False
	i: int = 0
	c: str = ""
	for i, c in enumerate(text):
		if esc:
			esc = False
			continue
		if c == "\\":
			esc = True
			continue
		if c == '"':
			in_str = not in_str
			continue
		if in_str:
			continue
		if c == "{":
			if depth == 0:
				start = i
			depth = depth + 1
		elif c == "}":
			depth = depth - 1
			if depth == 0 and start >= 0:
				return text[start:i + 1]
	return ""


def extract_facts(llm, user_text: str, assistant_text: str, prev_question: str = "") -> dict:
	prompt: str = ""
	try:
		prompt = FACT_PROMPT.format(prev=prev_question, user=user_text, assistant=assistant_text)
	except Exception:
		return {}
	try:
		raw: str = invoke_text(llm, prompt)
	except Exception:
		return {}
	blob: str = _find_json_obj(raw)
	if blob == "":
		return {}
	try:
		obj = json.loads(blob)
	except Exception:
		return {}
	return obj if isinstance(obj, dict) else {}