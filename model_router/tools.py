import time

RATES: dict = {
	"USD/EUR": 0.92,
	"USD/RUB": 92.50,
	"EUR/RUB": 100.54,
	"USD/JPY": 151.30,
}

WEATHER: dict = {
	"paris":    {"temp_c": 18, "conditions": "cloudy"},
	"london":   {"temp_c": 12, "conditions": "rain"},
	"moscow":   {"temp_c": -3, "conditions": "snow"},
	"tokyo":    {"temp_c": 22, "conditions": "clear"},
	"new york": {"temp_c": 15, "conditions": "windy"},
}


def get_weather(args: dict) -> dict:
	city: str = ""
	hit = None
	result: dict = {}

	city = str(args.get("city", "")).strip().lower()
	hit = WEATHER.get(city)

	if hit is None:
		return {"city": city, "error": "unknown city"}

	result = dict(hit)
	result["city"] = city
	return result


def get_time(args: dict) -> dict:
	return {"local_time": time.strftime("%Y-%m-%d %H:%M:%S")}


def get_rate(args: dict) -> dict:
	pair: str = ""
	rate = None
	parts: list = []
	inv: str = ""
	inv_rate = None

	pair = str(args.get("pair", "")).strip().upper()
	rate = RATES.get(pair)

	if rate is not None:
		return {"pair": pair, "rate": rate}

	parts = pair.split("/")
	if len(parts) != 2:
		return {"pair": pair, "error": "unknown pair"}

	inv = parts[1] + "/" + parts[0]
	inv_rate = RATES.get(inv)
	if inv_rate is None:
		return {"pair": pair, "error": "unknown pair"}

	return {"pair": pair, "rate": round(1.0 / inv_rate, 6), "derived_from": inv}


def convert_currency(args: dict) -> dict:
	raw = None
	amount: float = 0.0
	src: str = ""
	dst: str = ""
	pair: str = ""
	rate = None
	inv: str = ""
	inv_rate = None
	amount_out: float = 0.0

	raw = args.get("amount", 0)
	src = str(args.get("from", "")).strip().upper()
	dst = str(args.get("to", "")).strip().upper()

	try:
		amount = float(raw)
	except (TypeError, ValueError):
		return {"error": "amount must be a number", "got": str(raw)}

	if src == "" or dst == "":
		return {"error": "from and to are required"}

	if src == dst:
		return {"from": src, "to": dst, "amount": amount, "rate": 1.0, "converted": amount}

	pair = src + "/" + dst
	rate = RATES.get(pair)

	if rate is None:
		inv = dst + "/" + src
		inv_rate = RATES.get(inv)
		if inv_rate is None:
			return {"error": "unknown pair " + pair}
		rate = 1.0 / inv_rate

	amount_out = round(amount * rate, 2)

	return {
		"from": src,
		"to": dst,
		"amount": amount,
		"rate": round(rate, 6),
		"converted": amount_out,
	}


TOOLS: dict = {
	"get_weather": get_weather,
	"get_time": get_time,
	"get_rate": get_rate,
	"convert_currency": convert_currency,
}


def dispatch(name: str, args: dict) -> dict:
	fn = TOOLS.get(name)
	if fn is None:
		return {"error": "unknown tool: " + name}
	try:
		return fn(args)
	except Exception as e:
		return {"error": str(e)}