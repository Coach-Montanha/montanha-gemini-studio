"""
Vercel Serverless Function Handler for Montanha Gemini Studio v2.5
With Web Search Hook & Coach Montanha Identity Skills
"""

import os
import json
import time
import uuid
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DEFAULT_SYSTEM_PROMPT = """Você é o Montanha Gemini Studio, o assistente oficial de inteligência do Ecossistema Coach Montanha.
DIRETRIZES DA PERSONA (SKILL: MINHA VOZ):
1. Tom de Voz: Direto, firme, de quem opera no campo de batalha, sem enrolação e sem rodeios.
2. Abertura: Vá direto ao ponto, gancho forte ou constatação crua da realidade. Zero saudações corporativas protocolares.
3. Vocabulário Ativo: na prática, execução, campo de batalha, resultado, esteira, métrica, processo, consistência, ROI, validação.
4. Vocabulário Proibido: mergulhar fundo, revolucionário, no mundo acelerado de hoje, disruptivo, quiçá, em suma, dessarte.
5. Regra do [CONFERIR]: Nunca invente números ou dados não fornecidos. Se faltar dado exato, use [CONFERIR].
"""

def get_live_web_context(query):
    ql = query.lower()
    snippets = []
    if any(k in ql for k in ["clima", "tempo", "temperatura", "previsão", "chuva", "calor", "vento"]):
        city = "Joao Pessoa"
        for candidate in ["joao pessoa", "joão pessoa", "são paulo", "sao paulo", "rio de janeiro", "recife", "fortaleza", "brasília", "curitiba", "salvador"]:
            if candidate in ql:
                city = candidate.title()
                break
        try:
            city_enc = urllib.parse.quote(city)
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_enc}&count=1&language=pt&format=json"
            req_geo = urllib.request.Request(geo_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_geo, timeout=4) as r:
                gdata = json.loads(r.read().decode())
                if gdata.get("results"):
                    res = gdata["results"][0]
                    lat, lon = res["latitude"], res["longitude"]
                    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m"
                    req_w = urllib.request.Request(w_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req_w, timeout=4) as rw:
                        w = json.loads(rw.read().decode())["current"]
                        snippets.append(
                            f"[DADOS METEOROLÓGICOS REAIS AO VIVO]: Cidade: {city}. "
                            f"Temperatura atual: {w['temperature_2m']}°C (Sensação: {w['apparent_temperature']}°C). "
                            f"Umidade: {w['relative_humidity_2m']}%. Vento: {w['wind_speed_10m']} km/h."
                        )
        except Exception:
            pass

    if not snippets and any(k in ql for k in ["quem é", "o que é", "quem foi", "pesquise", "busque", "notícias"]):
        try:
            ddg_url = "https://api.duckduckgo.com/?q=" + urllib.parse.quote(query) + "&format=json&no_html=1&skip_disambig=1"
            req_d = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_d, timeout=3) as rd:
                d = json.loads(rd.read().decode())
                abstract = d.get("AbstractText")
                if abstract:
                    snippets.append(f"[DADOS DA WEB EM TEMPO REAL]: {abstract}")
        except Exception:
            pass

    return "\n".join(snippets)

class handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.endswith("/status"):
            self._send_json({
                "status": "online",
                "platform": "Vercel Serverless Cloud",
                "app": "Montanha Gemini Studio v2.5",
                "model": "gemini-flash-lite-latest",
                "gemini_key_configured": bool(GEMINI_API_KEY)
            })
            return
        elif parsed.path.endswith("/chats"):
            self._send_json({"status": "success", "chats": []})
            return

        self._send_json({"status": "ok", "message": "API Active"})

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(content_len) if content_len > 0 else b""
        try:
            body = json.loads(body_raw.decode("utf-8"))
        except Exception:
            body = {}

        parsed = urllib.parse.urlparse(self.path)

        if parsed.path.endswith("/chat"):
            prompt = body.get("prompt", "").strip()
            system_prompt = body.get("system_prompt", DEFAULT_SYSTEM_PROMPT).strip()
            image_b64 = body.get("image_base64", "")
            mime_type = body.get("mime_type", "image/jpeg")

            if not prompt and not image_b64:
                self._send_json({"status": "error", "message": "Mensagem vazia"}, 400)
                return

            api_key = GEMINI_API_KEY or body.get("api_key", "")
            if not api_key:
                self._send_json({"status": "error", "message": "GEMINI_API_KEY não configurada na Vercel."}, 400)
                return

            web_context = get_live_web_context(prompt)
            current_text = prompt
            if web_context:
                current_text = f"{prompt}\n\n[INFORMAÇÃO EM TEMPO REAL DA INTERNET]:\n{web_context}"

            parts = []
            if current_text:
                parts.append({"text": current_text})
            if image_b64:
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_b64
                    }
                })

            gemini_payload = {
                "contents": [{"role": "user", "parts": parts}],
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
            }

            candidate_models = ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-3.8-flash"]
            text_out = ""
            last_err = ""

            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(gemini_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        resp_data = json.loads(resp.read().decode("utf-8"))
                        cands = resp_data.get("candidates", [])
                        if cands:
                            parts_out = cands[0].get("content", {}).get("parts", [])
                            text_out = "".join(p.get("text", "") for p in parts_out)
                        if text_out:
                            break
                except urllib.error.HTTPError as e:
                    last_err = f"({e.code}): {e.read().decode('utf-8', errors='ignore')}"
                    continue
                except Exception as e:
                    last_err = str(e)
                    continue

            if text_out:
                self._send_json({"status": "success", "chat_id": body.get("chat_id") or "cloud_chat", "response": text_out})
            else:
                self._send_json({"status": "error", "message": f"Erro Gemini API: {last_err}"}, 500)
            return

        elif parsed.path.endswith("/generate-image"):
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_json({"status": "error", "message": "Prompt de imagem vazio"}, 400)
                return

            enc_prompt = urllib.parse.quote(prompt)
            seed = int(time.time() * 1000) % 999999
            image_url = f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1024&height=1024&model=flux&seed={seed}&nologo=true"
            self._send_json({"status": "success", "image_url": image_url, "prompt": prompt})
            return

        self._send_json({"status": "error", "message": "Endpoint Not Found"}, 404)

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
