from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from config import TEMPERATURE


def make_llm(model: str, base_url: str, api_key: str, extra_headers: dict = None) -> ChatOpenAI:
	headers: dict = {}
	if extra_headers is not None:
		headers = extra_headers
	return ChatOpenAI(
		model=model,
		api_key=api_key,
		base_url=base_url,
		temperature=TEMPERATURE,
		default_headers=headers,
	)


def dicts_to_lc(messages: list) -> list:
	out: list = []
	m: dict = {}
	role: str = ""
	content = ""
	for m in messages:
		role = m.get("role", "")
		content = m.get("content", "")
		if role == "system":
			out.append(SystemMessage(content=content))
		elif role == "user":
			out.append(HumanMessage(content=content))
		elif role == "assistant":
			out.append(AIMessage(content=content))
	return out


def stream_text(client, messages: list):
	lc_msgs: list = dicts_to_lc(messages)
	piece = ""
	chunk = None
	for chunk in client.stream(lc_msgs):
		piece = chunk.content if hasattr(chunk, "content") else ""
		if piece:
			yield piece


def invoke_text(client, prompt: str) -> str:
	resp = client.invoke([HumanMessage(content=prompt)])
	return resp.content if hasattr(resp, "content") else str(resp)