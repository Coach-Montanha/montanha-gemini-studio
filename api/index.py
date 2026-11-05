"""
Vercel Serverless Function Handler for Montanha Gemini Studio
Handles /api/chat, /api/generate-image, /api/status, and /api/tts
"""

import os
import json
import time
import uuid
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DEFAULT_SYSTEM_PROMPT = (
    "Você é o Montanha Gemini Studio, um assistente de inteligência artificial de alta performance "
    "focado em produtividade, copywriting direto, negócios, fitness de alto rendimento, "
    "estratégias digitais e desenvolvimento de software. Seja sempre cirúrgico, objetivo, sem enrolação "
    "e forneça respostas práticas em Markdown bem formatado."
)

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
                "app": "Montanha Gemini Studio v2",
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

            parts = []
            if prompt:
                parts.append({"text": prompt})
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
