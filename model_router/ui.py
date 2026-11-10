import sys

GREEN: str = "\033[32m"
CYAN: str = "\033[36m"
GREY: str = "\033[90m"
WHITE: str = "\033[97m"
RESET: str = "\033[0m"


def read_user() -> str:
	try:
		line: str = input(GREEN + "user> " + RESET + WHITE)
	except EOFError:
		print(RESET)
		raise
	print(RESET)
	return line


def begin_assistant(name: str) -> None:
	sys.stdout.write(CYAN + name + "> " + RESET + WHITE)
	sys.stdout.flush()


def stream_piece(text: str) -> None:
	sys.stdout.write(text)
	sys.stdout.flush()


def end_assistant() -> None:
	sys.stdout.write(RESET + "\n")
	sys.stdout.flush()
	print()

def system_inline(text: str) -> None:
	sys.stdout.write(GREY + text + RESET + "\n")
	sys.stdout.flush()


def system(text: str) -> None:
	print(GREY + "system> " + text + RESET)
	print()