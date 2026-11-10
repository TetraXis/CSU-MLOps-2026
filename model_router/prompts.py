import json
from config import SURVEY_TOPICS, SURVEY_DONE_MARKER

TOOL_SPECS: list = [
	{"name": "get_weather", "args": {"city": "string"}, "desc": "current weather for a city"},
	{"name": "get_time", "args": {}, "desc": "current local time"},
	{"name": "get_rate", "args": {"pair": "string"}, "desc": "exchange rate for a pair like USD/EUR"},
	{"name": "convert_currency", "args": {"amount": "number", "from": "string", "to": "string"}, "desc": "convert an amount between currencies, e.g. 250 USD to RUB"},
]

TOPIC_KEYS: dict = {
	"user's name": ["name"],
	"user's profession or tech stack": ["profession", "stack", "tech_stack"],
	"current project(s)": ["current_project", "current_projects", "project", "current_work"],
	"future project(s)": ["future_project", "future_projects", "goal", "dissertation"],
	"hardware running this session": ["hardware", "gpu", "cpu"],
}


def _topic_known(topic: str, known_keys: list) -> bool:
	keys: list = []
	k: str = ""
	if topic not in TOPIC_KEYS:
		return False
	keys = TOPIC_KEYS[topic]
	for k in keys:
		if k in known_keys:
			return True
	return False


def build_system_prompt(facts_context: str = "", needs_info: bool = False, known_keys: list = None) -> str:
	lines: list = []
	spec: dict = {}
	topic: str = ""
	known: list = []

	if known_keys is not None:
		known = known_keys

	if needs_info:
		lines.append("You are meeting this user for the first time.")
		lines.append("Topics of interest — status shown next to each:")
		for topic in SURVEY_TOPICS:
			if _topic_known(topic, known):
				lines.append("- " + topic + "  [ALREADY KNOWN — do NOT ask]")
			else:
				lines.append("- " + topic + "  [UNKNOWN — ask this]")
		lines.append("")
		lines.append("Ask only about topics marked UNKNOWN, ONE at a time.")
		lines.append("Never re-ask a topic marked ALREADY KNOWN.")
		lines.append("Do not use any tool while onboarding.")
		lines.append("When no UNKNOWN topics remain, greet normally and continue.")
		lines.append("If the user signals they do not want to answer more, emit " + SURVEY_DONE_MARKER + " on its own line and stop asking.")
		lines.append("")

	if facts_context:
		lines.append(facts_context)
		lines.append("")

	lines.append("You are a concise assistant with access to tools.")
	lines.append("")
	lines.append("To use a tool, output EXACTLY one line in this form and then stop:")
	lines.append('<tool>{"name": "TOOL_NAME", "args": {JSON}}</tool>')
	lines.append("")
	lines.append("Available tools:")
	for spec in TOOL_SPECS:
		lines.append(
			"- " + spec["name"]
			+ " args=" + json.dumps(spec["args"])
			+ " -> " + spec["desc"]
		)
	lines.append("")
	lines.append("Rules:")
	lines.append("0. Only state facts about the user that appear in the memory block above or earlier in this conversation.")
	lines.append("0a. Always speak TO the user in second person ('you'). Never refer to them in third person by name. Use their name only as a greeting or address.")
	lines.append("1. Emit at most one tool call per reply.")
	lines.append("2. The tag must be COMPLETE: it starts with <tool> and ends with </tool>.")
	lines.append("3. After a tool call, stop and wait for TOOL_RESULT. Do not answer yet.")
	lines.append("4. Never invent tool names. If a tool isn't listed above, do not call it — just answer in text.")
	lines.append("5. Numbers in args must be JSON numbers, not quoted strings.")
	lines.append("6. If no tool is needed (e.g. the user asks you to remember something, or asks a general question), answer in plain natural language. Do not write 'no tool' or any tag.")
	lines.append("7. Never claim data is unavailable. Always call the tool; the tool will report errors.")
	lines.append("8. Never write TOOL_RESULT yourself. Only the system emits TOOL_RESULT.")
	lines.append("9. Never invent tool output. Wait for the real TOOL_RESULT.")
	lines.append("")
	lines.append("Example - weather:")
	lines.append("User: What's the weather in Paris?")
	lines.append('Assistant: <tool>{"name": "get_weather", "args": {"city": "Paris"}}</tool>')
	lines.append('User: TOOL_RESULT get_weather: {"city": "paris", "temp_c": 18, "conditions": "cloudy"}')
	lines.append("Assistant: It is 18 C and cloudy in Paris.")
	lines.append("")
	lines.append("Example - currency conversion:")
	lines.append("User: Convert 250 USD to RUB")
	lines.append('Assistant: <tool>{"name": "convert_currency", "args": {"amount": 250, "from": "USD", "to": "RUB"}}</tool>')
	lines.append('User: TOOL_RESULT convert_currency: {"from": "USD", "to": "RUB", "amount": 250, "rate": 92.5, "converted": 23125.0}')
	lines.append("Assistant: 250 USD is 23125.00 RUB.")
	lines.append("")
	lines.append("WRONG (missing closing tag):")
	lines.append('<tool>{"name": "get_time", "args": {}}')
	lines.append("RIGHT:")
	lines.append('<tool>{"name": "get_time", "args": {}}</tool>')
	return "\n".join(lines)