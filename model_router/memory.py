import json
from pathlib import Path
from config import MEMORY_PATH

# running custom memory class, it is more interesting
class Memory:
	def __init__(self, path: str = MEMORY_PATH):
		self.path: Path = Path(path)
		self.facts: dict = {}
		self.load()

	def load(self) -> None:
		if not self.path.exists():
			self.facts = {}
			return
		try:
			with open(self.path, "r", encoding="utf-8") as f:
				data = json.load(f)
			self.facts = data if isinstance(data, dict) else {}
		except Exception:
			self.facts = {}

	def save(self) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		tmp: Path = self.path.with_suffix(".tmp")
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump(self.facts, f, indent=2, ensure_ascii=False)
		tmp.replace(self.path)

	def merge(self, new_facts: dict) -> int:
		if not isinstance(new_facts, dict):
			return 0
		n: int = 0
		k: str = ""
		v: str = ""
		for k, v in new_facts.items():
			k = str(k).strip()
			if k == "":
				continue
			v = "" if v is None else str(v).strip()
			if v == "":
				continue
			if self.facts.get(k) != v:
				self.facts[k] = v
				n = n + 1
		if n > 0:
			self.save()
		return n

	def to_context(self) -> str:
		lines: list = []
		k: str = ""
		v: str = ""
		if not self.facts:
			return ""
		lines.append("FACTS ALREADY KNOWN (do NOT ask about these):")
		for k, v in self.facts.items():
			lines.append("- " + k + ": " + v)
		return "\n".join(lines)

	def clear(self) -> None:
		self.facts = {}
		self.save()