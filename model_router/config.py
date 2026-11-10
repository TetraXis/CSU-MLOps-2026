LLAMA_DIR: str = r"D:\Python\llama_cpp"
LLAMA_SERVER: str = LLAMA_DIR + r"\llama-server.exe"
MODELS_DIR: str = r"D:\Python\models"
LOGS_DIR: str = r"D:\Python\Labs\model_router\logs"
HOST: str = "127.0.0.1"
PORT_BASE: int = 8090
GPU_LAYERS: int = 99
CONTEXT_SIZE: int = 2048
MAX_TOKENS: int = 512
TEMPERATURE: float = 0.7
HISTORY_MAX: int = 40
HISTORY_KEEP: int = 30
MAX_TOOL_DEPTH: int = 3

OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY: str = ""

DEEPSEEK_URL: str = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY: str = ""

DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

MEMORY_PATH: str = r"D:\Python\Labs\model_router\memory.json"
EXTRACT_ENABLED: bool = True

SURVEY_TOPICS: list = [
	"user's name",
	"user's profession or tech stack",
	"current project(s)",
	"future project(s)",
	"hardware running this session",
]
SURVEY_MIN_FACTS: int = 3
SURVEY_DONE_MARKER: str = "<survey_done/>"

try:
	from openrouter_api_key import OPENROUTER_API_KEY as _OKEY
	OPENROUTER_API_KEY = _OKEY
except ImportError:
	pass

try:
	from deepseek_api_key import DEEPSEEK_API_KEY as _DKEY
	DEEPSEEK_API_KEY = _DKEY
except ImportError:
	pass

OPENROUTER_MODELS: list = [
	"openrouter/free",
	"meta-llama/llama-3.3-70b-instruct:free",
	"google/gemini-2.0-flash-exp:free",
	"deepseek/deepseek-r1:free",
]

DEEPSEEK_MODELS: list = [
	"deepseek-chat",
	"deepseek-reasoner",
]