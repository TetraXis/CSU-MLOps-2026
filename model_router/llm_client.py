import json
import subprocess
import time
import urllib.request
from config import (
	LLAMA_SERVER,
	LLAMA_DIR,
	HOST,
	GPU_LAYERS,
	CONTEXT_SIZE,
	OPENROUTER_URL,
	OPENROUTER_API_KEY,
	DEEPSEEK_URL,
	DEEPSEEK_API_KEY,
)


def check_server(port: int) -> bool:
	url: str = "http://" + HOST + ":" + str(port) + "/health"
	resp = None
	ok: bool = False

	try:
		resp = urllib.request.urlopen(url, timeout=2)
	except Exception:
		return False

	ok = resp.status == 200
	resp.close()
	return ok


def wait_ready(port: int, timeout: int) -> bool:
	t0: float = time.time()

	while time.time() - t0 < timeout:
		if check_server(port):
			return True
		time.sleep(0.5)
	return False


def start_server(model_path: str, port: int, log_path: str):
	args: list = []
	log_fh = None
	proc = None

	log_fh = open(log_path, "w", encoding="utf-8")
	args = [
		LLAMA_SERVER,
		"-m", model_path,
		"-ngl", str(GPU_LAYERS),
		"-c", str(CONTEXT_SIZE),
		"--host", HOST,
		"--port", str(port),
	]
	try:
		proc = subprocess.Popen(
			args,
			stdout=log_fh,
			stderr=subprocess.STDOUT,
			cwd=LLAMA_DIR,
		)
	except Exception:
		log_fh.close()
		raise
	return proc, log_fh


def stop_server(proc: subprocess.Popen, log_fh) -> None:
	try:
		proc.terminate()
		proc.wait(timeout=15)
	except subprocess.TimeoutExpired:
		proc.kill()
		try:
			proc.wait(timeout=5)
		except Exception:
			pass
	try:
		log_fh.close()
	except Exception:
		pass


def _sse_stream(url: str, headers: dict, body: dict):
	data: bytes = b""
	req = None
	resp = None
	line_bytes: bytes = b""
	line: str = ""
	payload: str = ""
	obj: dict = {}
	choices: list = []
	delta: dict = {}
	content = None

	data = json.dumps(body).encode("utf-8")
	req = urllib.request.Request(
		url,
		data=data,
		headers=headers,
		method="POST",
	)
	resp = urllib.request.urlopen(req, timeout=300)

	try:
		for line_bytes in resp:
			line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
			if not line.startswith("data: "):
				continue
			payload = line.removeprefix("data: ")
			if payload == "[DONE]":
				break
			try:
				obj = json.loads(payload)
			except json.JSONDecodeError:
				continue
			choices = obj.get("choices", [])
			if len(choices) == 0:
				continue
			delta = choices[0].get("delta", {})
			content = delta.get("content")
			if content is None or content == "":
				continue
			yield content
	finally:
		resp.close()


def stream_chat_local(port: int, messages: list, max_tokens: int, temperature: float):
	body: dict = {}
	url: str = ""
	headers: dict = {}

	body = {
		"messages": messages,
		"max_tokens": max_tokens,
		"temperature": temperature,
		"stream": True,
	}
	url = "http://" + HOST + ":" + str(port) + "/v1/chat/completions"
	headers = {"Content-Type": "application/json"}

	for c in _sse_stream(url, headers, body):
		yield c


def stream_chat_openrouter(model_id: str, messages: list, max_tokens: int, temperature: float):
	body: dict = {}
	url: str = ""
	headers: dict = {}

	body = {
		"model": model_id,
		"messages": messages,
		"max_tokens": max_tokens,
		"temperature": temperature,
		"stream": True,
	}
	url = OPENROUTER_URL
	headers = {
		"Content-Type": "application/json",
		"Authorization": "Bearer " + OPENROUTER_API_KEY,
		"HTTP-Referer": "http://localhost",
		"X-Title": "model_router",
	}

	for c in _sse_stream(url, headers, body):
		yield c


def stream_chat_deepseek(model_id: str, messages: list, max_tokens: int, temperature: float):
	body: dict = {}
	url: str = ""
	headers: dict = {}

	body = {
		"model": model_id,
		"messages": messages,
		"max_tokens": max_tokens,
		"temperature": temperature,
		"stream": True,
	}
	url = DEEPSEEK_URL
	headers = {
		"Content-Type": "application/json",
		"Authorization": "Bearer " + DEEPSEEK_API_KEY,
	}

	for c in _sse_stream(url, headers, body):
		yield c