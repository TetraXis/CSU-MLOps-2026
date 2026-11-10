import sys
import re
import time
import ctypes
import json
from pathlib import Path
from config import (
	MODELS_DIR, LOGS_DIR, PORT_BASE, MAX_TOKENS, TEMPERATURE,
	HISTORY_MAX, HISTORY_KEEP, MAX_TOOL_DEPTH,
	HOST,
	OPENROUTER_MODELS, OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
	DEEPSEEK_MODELS, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
	MEMORY_PATH, EXTRACT_ENABLED,
	SURVEY_MIN_FACTS, SURVEY_DONE_MARKER,
)
from llm_client import start_server, stop_server, wait_ready
from parser import parse_tool_calls, strip_tool_calls
from tools import dispatch
from prompts import build_system_prompt
from llm import make_llm, stream_text
from memory import Memory
from facts import extract_facts
import ui

g_models: list = []
g_messages: list = []
g_llm = None
g_mem: Memory = None
g_extract_on: bool = EXTRACT_ENABLED
g_needs_info: bool = False
g_server_proc = None
g_server_log_fh = None
g_model_name: str = ""
g_model_kind: str = ""
g_model_id: str = ""
g_port: int = 0
g_next_port: int = 0
g_conv_log_path: str = ""
g_conv_log_fh = None


def enable_vt_mode() -> None:
	k = None
	handle = None
	mode = ctypes.c_uint32(0)

	if sys.platform != "win32":
		return

	try:
		k = ctypes.windll.kernel32
		handle = k.GetStdHandle(-11)
		if not k.GetConsoleMode(handle, ctypes.byref(mode)):
			return
		k.SetConsoleMode(handle, mode.value | 0x0004)
	except Exception:
		pass


def kind_tag(kind: str) -> str:
	if kind == "local":
		return "L"
	if kind == "deepseek":
		return "D"
	return "E"


def sanitize(name: str) -> str:
	return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def now_stamp() -> str:
	return time.strftime("%Y-%m-%d %H:%M:%S")


def log_line(text: str) -> None:
	if g_conv_log_fh is None:
		return
	try:
		g_conv_log_fh.write("[" + now_stamp() + "] " + text + "\n")
		g_conv_log_fh.flush()
	except Exception:
		pass


def open_conv_log() -> int:
	global g_conv_log_path, g_conv_log_fh

	logs_dir = None
	name: str = ""

	close_conv_log()
	if g_model_name == "":
		return 1

	logs_dir = Path(LOGS_DIR)
	try:
		logs_dir.mkdir(parents=True, exist_ok=True)
	except Exception as e:
		ui.system("cannot create logs dir: " + str(e))
		return 1

	name = sanitize(g_model_name)
	g_conv_log_path = str(logs_dir / (name + ".log"))

	try:
		g_conv_log_fh = open(g_conv_log_path, "a", encoding="utf-8")
	except Exception as e:
		ui.system("cannot open log: " + str(e))
		g_conv_log_path = ""
		return 1

	log_line("=== session start: " + g_model_name + " (" + g_model_kind + ") ===")
	return 0


def close_conv_log() -> None:
	global g_conv_log_fh, g_conv_log_path

	if g_conv_log_fh is not None:
		try:
			log_line("=== session end ===")
			g_conv_log_fh.close()
		except Exception:
			pass
		g_conv_log_fh = None
	g_conv_log_path = ""


def compute_needs_info(mem: Memory) -> bool:
	return len(mem.facts) < SURVEY_MIN_FACTS


def current_prompt() -> str:
	known: list = []
	k: str = ""
	for k in g_mem.facts.keys():
		known.append(k)
	return build_system_prompt(g_mem.to_context(), g_needs_info, known)


def list_local_models() -> list:
	models: list = []
	root: Path = Path(MODELS_DIR)
	entries: list = []

	if not root.exists():
		return models

	entries = sorted(root.glob("*.gguf"))
	for p in entries:
		models.append(str(p))
	return models


def build_model_list() -> list:
	entries: list = []
	local: list = []
	p: str = ""
	m: str = ""

	local = list_local_models()
	for p in local:
		entries.append({
			"kind": "local",
			"name": Path(p).stem,
			"path": p,
			"model_id": "",
		})
	for m in OPENROUTER_MODELS:
		entries.append({
			"kind": "external",
			"name": m,
			"path": "",
			"model_id": m,
		})
	for m in DEEPSEEK_MODELS:
		entries.append({
			"kind": "deepseek",
			"name": m,
			"path": "",
			"model_id": m,
		})
	return entries


def prompt_choice(models: list) -> int:
	count: int = len(models)
	n: int = 0
	line: str = ""
	m: dict = {}

	print("")
	print("Available models:")
	for idx in range(count):
		m = models[idx]
		print("  [" + str(idx) + "] " + kind_tag(m["kind"]) + "  " + m["name"])
	print("  [q] cancel")

	while True:
		try:
			line = input("select> ").strip().lower()
		except (EOFError, KeyboardInterrupt):
			return -1
		if line == "q":
			return -1
		if not line.isdigit():
			print("  ! enter a number or q")
			continue
		n = int(line)
		if n < 0 or n >= count:
			print("  ! out of range")
			continue
		return n


def unload_model() -> None:
	global g_server_proc, g_server_log_fh, g_model_name, g_model_kind, g_model_id, g_port, g_llm

	close_conv_log()

	if g_server_proc is not None:
		stop_server(g_server_proc, g_server_log_fh)
		g_server_proc = None
		g_server_log_fh = None
	g_model_name = ""
	g_model_kind = ""
	g_model_id = ""
	g_port = 0
	g_llm = None


def load_model(idx: int) -> int:
	global g_server_proc, g_server_log_fh, g_model_name, g_model_kind, g_model_id, g_port, g_next_port, g_llm

	m: dict = {}
	port: int = 0
	path: str = ""
	stem: str = ""
	server_log: str = ""
	proc = None
	fh = None

	unload_model()
	m = g_models[idx]

	if m["kind"] == "external":
		if OPENROUTER_API_KEY == "":
			ui.system("openrouter_api_key.py missing or empty")
			return 1
		g_model_name = m["name"]
		g_model_kind = "external"
		g_model_id = m["model_id"]
		g_llm = make_llm(
			g_model_id,
			OPENROUTER_BASE_URL,
			OPENROUTER_API_KEY,
			{"HTTP-Referer": "http://localhost", "X-Title": "model_router"},
		)
		ui.system("loaded: " + m["name"] + " (openrouter)")
		open_conv_log()
		return 0

	if m["kind"] == "deepseek":
		if DEEPSEEK_API_KEY == "":
			ui.system("deepseek_api_key.py missing or empty")
			return 1
		g_model_name = m["name"]
		g_model_kind = "deepseek"
		g_model_id = m["model_id"]
		g_llm = make_llm(g_model_id, DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY)
		ui.system("loaded: " + m["name"] + " (deepseek)")
		open_conv_log()
		return 0

	if g_next_port < PORT_BASE:
		g_next_port = PORT_BASE
	port = g_next_port
	g_next_port = g_next_port + 1

	path = m["path"]
	stem = Path(path).stem
	server_log = str(Path(__file__).parent / ("server_" + stem + ".log"))

	ui.system("starting server on port " + str(port))
	proc, fh = start_server(path, port, server_log)

	if not wait_ready(port, 180):
		stop_server(proc, fh)
		ui.system("load failed, see " + server_log)
		return 1

	g_server_proc = proc
	g_server_log_fh = fh
	g_model_name = m["name"]
	g_model_kind = "local"
	g_model_id = ""
	g_port = port
	g_llm = make_llm(g_model_name, "http://" + HOST + ":" + str(port) + "/v1", "sk-no-key")

	ui.system("loaded: " + m["name"] + " (local)")
	open_conv_log()
	return 0


def cmd_exit(args: list) -> int:
	return 1


def cmd_help(args: list) -> int:
	names: list = []
	k: str = ""
	for k in COMMANDS:
		names.append(k)
	ui.system_inline("commands: " + "  ".join(names))
	return 0


def cmd_models(args: list) -> int:
	i: int = 0
	m: dict = {}
	marker: str = ""

	for m in g_models:
		marker = " *" if m["name"] == g_model_name else "  "
		ui.system("[" + str(i) + "]" + marker + " " + kind_tag(m["kind"]) + "  " + m["name"])
		i = i + 1
	return 0


def cmd_model(args: list) -> int:
	idx: int = 0

	if len(args) == 0:
		idx = prompt_choice(g_models)
		if idx < 0:
			return 0
		load_model(idx)
		return 0
	if not args[0].isdigit():
		ui.system("usage: /model N")
		return 0
	idx = int(args[0])
	if idx < 0 or idx >= len(g_models):
		ui.system("out of range")
		return 0
	load_model(idx)
	return 0


def cmd_reset(args: list) -> int:
	global g_messages

	g_messages = [{"role": "system", "content": current_prompt()}]
	log_line("RESET")
	ui.system("history cleared")
	return 0


def cmd_forget(args: list) -> int:
	global g_messages, g_needs_info

	g_mem.clear()
	g_needs_info = compute_needs_info(g_mem)
	g_messages = [{"role": "system", "content": current_prompt()}]
	ui.system("memory cleared — onboarding: " + ("on" if g_needs_info else "off"))
	return 0


def cmd_extract(args: list) -> int:
	global g_extract_on

	if len(args) == 1 and args[0] in ("on", "off"):
		g_extract_on = args[0] == "on"
		ui.system("extract: " + args[0])
		return 0
	ui.system("usage: /extract on|off")
	return 0


def cmd_survey(args: list) -> int:
	global g_needs_info

	if len(args) == 1 and args[0] in ("on", "off"):
		g_needs_info = args[0] == "on"
		g_messages[0] = {"role": "system", "content": current_prompt()}
		ui.system("onboarding: " + args[0])
		return 0
	ui.system("usage: /survey on|off")
	return 0


def cmd_facts(args: list) -> int:
	k: str = ""
	v: str = ""

	if not g_mem.facts:
		ui.system("no facts saved")
		return 0
	for k, v in g_mem.facts.items():
		ui.system(k + ": " + v)
	return 0


def cmd_cls(args: list) -> int:
	sys.stdout.write("\033[2J\033[H")
	sys.stdout.flush()
	return 0


def cmd_history(args: list) -> int:
	i: int = 0
	m: dict = {}

	for m in g_messages:
		ui.system("[" + str(i) + "] " + m["role"] + ": " + m["content"])
		i = i + 1
	return 0


def cmd_log(args: list) -> int:
	ui.system("dir: " + LOGS_DIR)
	if g_conv_log_path == "":
		ui.system("file: (none)")
	else:
		ui.system("file: " + g_conv_log_path)
	return 0


COMMANDS: dict = {
	"/help": cmd_help,
	"/exit": cmd_exit,
	"/models": cmd_models,
	"/model": cmd_model,
	"/reset": cmd_reset,
	"/forget": cmd_forget,
	"/extract": cmd_extract,
	"/survey": cmd_survey,
	"/facts": cmd_facts,
	"/cls": cmd_cls,
	"/history": cmd_history,
	"/log": cmd_log,
}


def do_turn(user_line: str) -> None:
	global g_messages, g_needs_info

	depth: int = 0
	reply: str = ""
	piece: str = ""
	calls: list = []
	call: dict = {}
	result: dict = {}
	new_facts: dict = {}
	n: int = 0
	prev: str = ""

	if len(g_messages) > 1:
		prev = g_messages[-1]["content"]

	g_messages.append({"role": "user", "content": user_line})
	log_line("USER: " + user_line)

	ui.begin_assistant(g_model_name)
	try:
		for piece in stream_text(g_llm, g_messages):
			ui.stream_piece(piece)
			reply = reply + piece
	finally:
		ui.end_assistant()
	log_line("ASSISTANT: " + reply)
	g_messages.append({"role": "assistant", "content": reply})

	if SURVEY_DONE_MARKER in reply:
		reply = reply.replace(SURVEY_DONE_MARKER, "").strip()
		g_needs_info = False
		ui.system("onboarding skipped by model")
		g_messages[-1]["content"] = reply

	while True:
		calls = parse_tool_calls(reply)
		if len(calls) == 0:
			break
		if depth >= MAX_TOOL_DEPTH:
			ui.system("tool loop depth reached")
			log_line("WARN: tool loop depth reached")
			break
		depth = depth + 1
		for call in calls:
			ui.system("tool: " + call["name"] + " " + json.dumps(call["args"]))
			log_line("TOOL_CALL: " + call["name"] + " " + json.dumps(call["args"]))
			result = dispatch(call["name"], call["args"])
			ui.system("result: " + json.dumps(result))
			log_line("TOOL_RESULT: " + json.dumps(result))
			g_messages.append({
				"role": "user",
				"content": "TOOL_RESULT " + call["name"] + ": " + json.dumps(result),
			})
		reply = ""
		ui.begin_assistant(g_model_name)
		try:
			for piece in stream_text(g_llm, g_messages):
				ui.stream_piece(piece)
				reply = reply + piece
		finally:
			ui.end_assistant()
		log_line("ASSISTANT: " + reply)
		g_messages.append({"role": "assistant", "content": reply})

	log_line("---")

	if g_extract_on:
		try:
			new_facts = extract_facts(g_llm, user_line, reply, prev_question=prev)
			n = g_mem.merge(new_facts)
			if n > 0:
				ui.system("remembered " + str(n) + " fact(s)")
		except Exception as e:
			ui.system("fact extraction failed: " + str(e))

	g_needs_info = compute_needs_info(g_mem)
	g_messages[0] = {"role": "system", "content": current_prompt()}


def trim_history() -> None:
	global g_messages

	head: dict = {}
	trimmed: list = []
	start: int = 0
	j: int = 0

	if len(g_messages) <= HISTORY_MAX:
		return
	head = g_messages[0]
	trimmed = [head]
	start = len(g_messages) - HISTORY_KEEP
	for j in range(start, len(g_messages)):
		trimmed.append(g_messages[j])
	g_messages = trimmed


def repl() -> None:
	global g_messages

	user_line: str = ""
	parts: list = []
	handler = None
	rc: int = 0

	g_messages = [{"role": "system", "content": current_prompt()}]

	ui.system("memory: " + MEMORY_PATH + " (" + str(len(g_mem.facts)) + " facts)")
	if g_needs_info:
		ui.system("onboarding mode (model decides what to ask)")
	ui.system("model: " + g_model_name + " (" + g_model_kind + ")")
	ui.system("extract: " + ("on" if g_extract_on else "off"))
	cmd_help([])

	while True:
		try:
			user_line = ui.read_user()
		except (EOFError, KeyboardInterrupt):
			break
		user_line = user_line.strip()
		if user_line == "":
			continue

		if user_line.startswith("/"):
			parts = user_line.split()
			handler = COMMANDS.get(parts[0])
			if handler is None:
				ui.system("unknown command: " + parts[0])
				continue
			rc = handler(parts[1:])
			if rc != 0:
				break
			continue

		if g_llm is None:
			ui.system("no model loaded, use /model")
			continue

		try:
			do_turn(user_line)
		except KeyboardInterrupt:
			ui.end_assistant()
			ui.system("interrupted")
			log_line("INTERRUPTED")
			if len(g_messages) > 0 and g_messages[-1]["role"] == "user":
				g_messages.pop()
			continue
		except Exception as e:
			ui.end_assistant()
			ui.system("error: " + str(e))
			log_line("ERROR: " + str(e))
			if len(g_messages) > 0 and g_messages[-1]["role"] == "user":
				g_messages.pop()
			continue

		trim_history()


def main() -> int:
	global g_models, g_mem, g_extract_on, g_needs_info

	idx: int = 0

	enable_vt_mode()

	g_mem = Memory(MEMORY_PATH)
	g_extract_on = EXTRACT_ENABLED
	g_needs_info = compute_needs_info(g_mem)

	g_models = build_model_list()
	if len(g_models) == 0:
		print("[error] no models (local .gguf, OPENROUTER_MODELS, DEEPSEEK_MODELS)")
		return 1

	idx = prompt_choice(g_models)
	if idx < 0:
		return 0

	if load_model(idx) != 0:
		return 1

	try:
		repl()
	finally:
		unload_model()
		ui.system("stopped")
	return 0


if __name__ == "__main__":
	sys.exit(main())