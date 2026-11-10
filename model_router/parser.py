import json
import re

TOOL_STRICT = re.compile(r"<tool>\s*(\{.*?\})\s*</tool>", re.DOTALL)


def _find_object(text: str, start: int) -> str:
	depth: int = 0
	i: int = start
	in_str: bool = False
	escape: bool = False
	c: str = ""

	while i < len(text):
		c = text[i]
		if escape:
			escape = False
		elif c == "\\":
			escape = True
		elif c == '"':
			in_str = not in_str
		elif not in_str:
			if c == "{":
				depth = depth + 1
			elif c == "}":
				depth = depth - 1
				if depth == 0:
					return text[start:i + 1]
		i = i + 1
	return ""


def _parse_blob(raw: str):
	obj = None
	name: str = ""
	args = None

	try:
		obj = json.loads(raw)
	except json.JSONDecodeError:
		return None
	if not isinstance(obj, dict):
		return None
	name = str(obj.get("name", "")).strip()
	if name == "":
		return None
	args = obj.get("args", {})
	if not isinstance(args, dict):
		args = {}
	return {"name": name, "args": args}


def parse_tool_calls(text: str) -> list:
	calls: list = []
	raw: str = ""
	parsed = None
	pos: int = 0
	blob: str = ""

	if text is None or text == "":
		return calls

	for raw in TOOL_STRICT.findall(text):
		parsed = _parse_blob(raw)
		if parsed is not None:
			calls.append(parsed)
	if len(calls) > 0:
		return calls

	while True:
		pos = text.find("<tool>", pos)
		if pos < 0:
			break
		pos = pos + 6
		while pos < len(text) and text[pos] in " \t\r\n":
			pos = pos + 1
		if pos >= len(text) or text[pos] != "{":
			continue
		blob = _find_object(text, pos)
		if blob == "":
			pos = pos + 1
			continue
		parsed = _parse_blob(blob)
		if parsed is not None:
			calls.append(parsed)
		pos = pos + len(blob)
	return calls


def strip_tool_calls(text: str) -> str:
	if text is None or text == "":
		return ""
	return TOOL_STRICT.sub("", text).strip()