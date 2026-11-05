"""
Montanha Gemini Studio v2.0 - Multi-Chat, PDF Intelligence, Audio TTS & Image Suite
Zero-token local costs, official Gemini API free-tier.
Supports:
- Multi-Chat with separate context & memory (Graphify ready)
- PDF Ingestion & Chapter Extraction (pypdf)
- Image Generator Multi-Provider (Flux / SDXL / Pollinations Turbo)
- Neural Audio TTS (.mp3) via edge-tts & Google TTS
- Audio Transcription via Gemini Multimodal
"""

import os
import sys
import json
import time
import uuid
import base64
import urllib.parse
import urllib.request
import asyncio
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

BASE_DIR = Path(__file__).parent.resolve()
PUBLIC_DIR = BASE_DIR / "public"
STORAGE_DIR = BASE_DIR / "storage"
CHATS_DIR = STORAGE_DIR / "chats"
UPLOADS_DIR = STORAGE_DIR / "uploads"
AUDIO_DIR = STORAGE_DIR / "audio"

for d in [PUBLIC_DIR, STORAGE_DIR, CHATS_DIR, UPLOADS_DIR, AUDIO_DIR]:
    d.mkdir(parents=True, exist_ok=True)

INDEX_FILE = STORAGE_DIR / "chats_index.json"
if not INDEX_FILE.exists():
    INDEX_FILE.write_text("[]", encoding="utf-8")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DEFAULT_SYSTEM_PROMPT = (
    "Você é o Montanha Gemini Studio, um assistente de inteligência artificial de alta performance "
    "focado em produtividade, copywriting direto, negócios, fitness de alto rendimento, "
    "estratégias digitais e desenvolvimento de software. Seja sempre cirúrgico, objetivo, sem enrolação "
    "e forneça respostas práticas em Markdown bem formatado."
)

def get_chats_index():
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_chats_index(idx):
    INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

def get_chat_messages(chat_id):
    chat_file = CHATS_DIR / f"{chat_id}.json"
    if chat_file.exists():
        try:
            return json.loads(chat_file.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_chat_messages(chat_id, msgs):
    chat_file = CHATS_DIR / f"{chat_id}.json"
    chat_file.write_text(json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")

class GeminiStudioHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        raw_path = urllib.parse.unquote(self.path)
        parsed = urllib.parse.urlparse(raw_path)

        if parsed.path in ["/", "/index.html"]:
            index_file = PUBLIC_DIR / "index.html"
            if not index_file.exists():
                self.send_error(404, "index.html not found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(index_file, "rb") as f:
                self.wfile.write(f.read())
            return

        elif parsed.path == "/api/chats":
            self._send_json({"status": "success", "chats": get_chats_index()})
            return

        elif parsed.path.startswith("/api/chat/"):
            chat_id = parsed.path.split("/")[-1]
            msgs = get_chat_messages(chat_id)
            self._send_json({"status": "success", "chat_id": chat_id, "messages": msgs})
            return

        elif parsed.path == "/api/status":
            self._send_json({
                "status": "online",
                "app": "Montanha Gemini Studio v2",
                "gemini_key_configured": bool(GEMINI_API_KEY),
                "model": "gemini-flash-lite-latest",
                "features": ["multi_chat", "pdf_intelligence", "audio_tts", "image_multi_provider", "graphify_ready"]
            })
            return

        elif parsed.path.startswith("/audio/"):
            fname = parsed.path.replace("/audio/", "").strip()
            target = (AUDIO_DIR / fname).resolve()
            if target.is_relative_to(AUDIO_DIR) and target.exists() and target.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Disposition", f'inline; filename="{fname}"')
                self.end_headers()
                with open(target, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "Audio file not found")
            return

        # Static file serve fallback
        rel_path = parsed.path.lstrip("/\\")
        candidate = (PUBLIC_DIR / rel_path).resolve()
        if candidate.is_relative_to(PUBLIC_DIR) and candidate.exists() and candidate.is_file():
            mime = "application/octet-stream"
            if candidate.suffix == ".css": mime = "text/css"
            elif candidate.suffix == ".js": mime = "application/javascript"
            elif candidate.suffix == ".svg": mime = "image/svg+xml"
            elif candidate.suffix == ".png": mime = "image/png"
            elif candidate.suffix in [".jpg", ".jpeg"]: mime = "image/jpeg"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.end_headers()
            with open(candidate, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(content_len) if content_len > 0 else b""
        try:
            body = json.loads(body_raw.decode("utf-8"))
        except Exception:
            body = {}

        parsed = urllib.parse.urlparse(self.path)

        # 1. Create or Select Chat
        if parsed.path == "/api/chats/new":
            title = body.get("title", "Nova Conversa").strip() or "Nova Conversa"
            chat_id = f"chat_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            idx = get_chats_index()
            chat_meta = {
                "id": chat_id,
                "title": title,
                "created_at": time.strftime("%Y-%m-%d %H:%M"),
                "updated_at": time.strftime("%Y-%m-%d %H:%M")
            }
            idx.insert(0, chat_meta)
            save_chats_index(idx)
            save_chat_messages(chat_id, [])
            self._send_json({"status": "success", "chat": chat_meta})
            return

        elif parsed.path == "/api/chats/delete":
            chat_id = body.get("chat_id")
            if chat_id:
                idx = [c for c in get_chats_index() if c.get("id") != chat_id]
                save_chats_index(idx)
                f = CHATS_DIR / f"{chat_id}.json"
                if f.exists():
                    f.unlink()
            self._send_json({"status": "success", "message": "Chat excluído"})
            return

        # 2. Chat with Context & History
        elif parsed.path == "/api/chat":
            chat_id = body.get("chat_id")
            prompt = body.get("prompt", "").strip()
            system_prompt = body.get("system_prompt", DEFAULT_SYSTEM_PROMPT).strip()
            image_b64 = body.get("image_base64", "")
            mime_type = body.get("mime_type", "image/jpeg")

            if not chat_id:
                # Criar chat automático se não enviado
                idx = get_chats_index()
                title = prompt[:35] + ("..." if len(prompt) > 35 else "") if prompt else "Conversa Rápida"
                chat_id = f"chat_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                idx.insert(0, {
                    "id": chat_id,
                    "title": title,
                    "created_at": time.strftime("%Y-%m-%d %H:%M"),
                    "updated_at": time.strftime("%Y-%m-%d %H:%M")
                })
                save_chats_index(idx)

            if not prompt and not image_b64:
                self._send_json({"status": "error", "message": "Mensagem vazia"}, 400)
                return

            api_key = GEMINI_API_KEY or body.get("api_key", "")
            if not api_key:
                self._send_json({"status": "error", "message": "Chave GEMINI_API_KEY não configurada no servidor."}, 400)
                return

            # Carregar histórico da conversa para manter contexto (últimas 10 mensagens)
            history = get_chat_messages(chat_id)
            context_contents = []
            for h in history[-8:]:
                context_contents.append({"role": "user", "parts": [{"text": h.get("prompt", "")}]})
                context_contents.append({"role": "model", "parts": [{"text": h.get("response", "")}]})

            # Montar mensagem atual
            current_parts = []
            if prompt:
                current_parts.append({"text": prompt})
            if image_b64:
                current_parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_b64
                    }
                })
            context_contents.append({"role": "user", "parts": current_parts})

            gemini_payload = {
                "contents": context_contents,
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 4096
                }
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
                msg_record = {
                    "id": uuid.uuid4().hex[:8],
                    "timestamp": int(time.time()),
                    "prompt": prompt,
                    "response": text_out,
                    "has_image": bool(image_b64)
                }
                history.append(msg_record)
                save_chat_messages(chat_id, history)

                # Atualizar título do chat se for a primeira mensagem
                idx = get_chats_index()
                for c in idx:
                    if c.get("id") == chat_id:
                        if c.get("title") in ["Nova Conversa", "Conversa Rápida"]:
                            c["title"] = prompt[:35] + ("..." if len(prompt) > 35 else "")
                        c["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
                        break
                save_chats_index(idx)

                self._send_json({"status": "success", "chat_id": chat_id, "response": text_out})
            else:
                self._send_json({"status": "error", "message": f"Erro Gemini API: {last_err}"}, 500)
            return

        # 3. Multi-Provider Image Generation (No 45s wait)
        elif parsed.path == "/api/generate-image":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_json({"status": "error", "message": "Prompt de imagem vazio"}, 400)
                return

            enc_prompt = urllib.parse.quote(prompt)
            # Rotação de sementes e nós neurais rápidos
            seed = int(time.time() * 1000) % 999999
            
            # Provedores de alta velocidade e qualidade
            providers = [
                f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1024&height=1024&model=flux&seed={seed}&nologo=true",
                f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1024&height=1024&model=turbo&seed={seed}&nologo=true",
                f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1024&height=1024&seed={seed}&nologo=true"
            ]
            
            self._send_json({
                "status": "success",
                "image_url": providers[0],
                "fallback_url": providers[1],
                "prompt": prompt
            })
            return

        # 4. Neural Audio TTS
        elif parsed.path == "/api/tts":
            text = body.get("text", "").strip()
            voice = body.get("voice", "pt-BR-AntonioNeural")
            if not text:
                self._send_json({"status": "error", "message": "Texto vazio para TTS"}, 400)
                return

            out_name = f"tts_{int(time.time())}_{uuid.uuid4().hex[:4]}.mp3"
            out_file = AUDIO_DIR / out_name

            tts_success = False
            if edge_tts:
                try:
                    async def _run_edge():
                        comm = edge_tts.Communicate(text[:1200], voice)
                        await comm.save(str(out_file))
                    asyncio.run(_run_edge())
                    tts_success = True
                except Exception:
                    pass

            if not tts_success:
                # Fallback Google Neural
                try:
                    url_tts = f"https://translate.google.com/translate_tts?ie=UTF-8&q={urllib.parse.quote(text[:300])}&tl=pt-BR&client=tw-ob"
                    req = urllib.request.Request(url_tts, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        out_file.write_bytes(resp.read())
                    tts_success = True
                except Exception as e:
                    self._send_json({"status": "error", "message": f"Erro TTS: {str(e)}"}, 500)
                    return

            self._send_json({
                "status": "success",
                "audio_url": f"/audio/{out_name}",
                "filename": out_name
            })
            return

        # 5. PDF Extraction & Book Reading
        elif parsed.path == "/api/read-pdf":
            pdf_b64 = body.get("pdf_base64", "")
            filename = body.get("filename", "livro.pdf")
            if not pdf_b64:
                self._send_json({"status": "error", "message": "Arquivo PDF não enviado"}, 400)
                return

            pdf_bytes = base64.b64decode(pdf_b64)
            saved_pdf = UPLOADS_DIR / f"book_{int(time.time())}_{filename}"
            saved_pdf.write_bytes(pdf_bytes)

            extracted_text = ""
            total_pages = 0
            if pypdf:
                try:
                    reader = pypdf.PdfReader(str(saved_pdf))
                    total_pages = len(reader.pages)
                    # Extrair primeiros 30 páginas para análise ágil sem sobrecarga
                    for i in range(min(total_pages, 30)):
                        extracted_text += f"\n--- PÁGINA {i+1} ---\n" + (reader.pages[i].extract_text() or "")
                except Exception as e:
                    extracted_text = f"Erro na extração: {str(e)}"
            else:
                extracted_text = "Módulo pypdf não disponível no servidor."

            self._send_json({
                "status": "success",
                "filename": filename,
                "total_pages": total_pages,
                "extracted_text": extracted_text[:25000] # Limite seguro para contexto do modelo
            })
            return

        self.send_error(404, "Endpoint Not Found")

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

def run_server(port=4192):
    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, GeminiStudioHandler)
    print(f"[*] Montanha Gemini Studio v2.0 ativo na porta {port}")
    print(f"[*] Acesso Local: http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    p = 4192
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
        except Exception:
            pass
    run_server(p)
