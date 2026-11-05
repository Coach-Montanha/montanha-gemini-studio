"""
Montanha Gemini Studio v3.0 - Multi-Skill, PDF Engine, Audio Speed Control & Web Intelligence
Zero-token local costs, official Gemini API free-tier.
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

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

BASE_DIR = Path(__file__).parent.resolve()
PUBLIC_DIR = BASE_DIR / "public"
STORAGE_DIR = BASE_DIR / "storage"
CHATS_DIR = STORAGE_DIR / "chats"
UPLOADS_DIR = STORAGE_DIR / "uploads"
AUDIO_DIR = STORAGE_DIR / "audio"
PDF_DIR = STORAGE_DIR / "pdf"

for d in [PUBLIC_DIR, STORAGE_DIR, CHATS_DIR, UPLOADS_DIR, AUDIO_DIR, PDF_DIR]:
    d.mkdir(parents=True, exist_ok=True)

INDEX_FILE = STORAGE_DIR / "chats_index.json"
if not INDEX_FILE.exists():
    INDEX_FILE.write_text("[]", encoding="utf-8")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Catálogo Oficial de Skills do Ecossistema Montanha
SKILLS_PROMPTS = {
    "minha-voz": (
        "Você é o Coach Montanha, operando sob a diretriz MINHA VOZ.\n"
        "1. Tom: Direto, firme, de quem opera no campo de batalha, sem enrolação e sem rodeios corporativos.\n"
        "2. Abertura: Gancho forte ou constatação crua da realidade. Zero 'olá pessoal' ou 'espero que estejam bem'.\n"
        "3. Vocabulário: na prática, execução, campo de batalha, resultado, escala, esteira, métrica, consistência, ROI.\n"
        "4. Proibido: mergulhar fundo, revolucionário, disruptivo, quiçá, em suma, dessarte.\n"
        "5. Regra [CONFERIR]: Nunca invente números ou dados de faturamento. Se faltar métrica, escreva [CONFERIR]."
    ),
    "roteiros-10x": (
        "Você é o especialista em Roteiros de Alta Conversão (Stories & Reels 10x) do Ecossistema Montanha.\n"
        "1. Escreva roteiros com gancho nos primeiros 3 segundos, quebra de padrão, desenvolvimento em 3 atos e CTA clara.\n"
        "2. Indique cortes visuais entre colchetes [Corte rápido para cena de treino] e o texto exato da fala do locutor.\n"
        "3. Estilo: Enérgico, dinâmico e otimizado para retenção máxima no Instagram e TikTok."
    ),
    "personal-trainer": (
        "Você é o Consultor Técnico de Fisiologia e Treino de Alta Performance do Ecossistema Montanha.\n"
        "1. Prescreva treinos fundamentados em biomecânica real, progressão de carga e recomposição corporal.\n"
        "2. Para atendimento: escreva scripts diretos de WhatsApp para onboarding, combate a objeções e retenção (anti-churn).\n"
        "3. Explique de forma cirúrgica o porquê de cada estímulo metabólico ou neural."
    ),
    "programador": (
        "Você é o Engenheiro de Software Sênior do Ecossistema Montanha.\n"
        "1. Princípio Ponytail & Karpathy: Simplicidade radical, zero sobre-engenharia, cirúrgico, sem instalar dependências redundantes.\n"
        "2. Código limpo, testável, bem comentado apenas no essencial e pronto para produção."
    )
}

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
                "app": "Montanha Gemini Studio v3.0",
                "gemini_key_configured": bool(GEMINI_API_KEY),
                "model": "gemini-flash-lite-latest",
                "features": ["multi_skill_selector", "pdf_generator", "audio_speed_control", "live_web_search", "graphify_ready"]
            })
            return

        elif parsed.path.startswith("/audio/"):
            fname = parsed.path.replace("/audio/", "").strip()
            target = (AUDIO_DIR / fname).resolve()
            if target.is_relative_to(AUDIO_DIR) and target.exists() and target.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.end_headers()
                with open(target, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "Audio file not found")
            return

        elif parsed.path.startswith("/pdf/"):
            fname = parsed.path.replace("/pdf/", "").strip()
            target = (PDF_DIR / fname).resolve()
            if target.is_relative_to(PDF_DIR) and target.exists() and target.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.end_headers()
                with open(target, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "PDF file not found")
            return

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

        elif parsed.path == "/api/chat":
            chat_id = body.get("chat_id")
            prompt = body.get("prompt", "").strip()
            skill_key = body.get("skill", "minha-voz")
            system_prompt = SKILLS_PROMPTS.get(skill_key, SKILLS_PROMPTS["minha-voz"])
            image_b64 = body.get("image_base64", "")
            mime_type = body.get("mime_type", "image/jpeg")

            if not chat_id:
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

            web_context = get_live_web_context(prompt)
            history = get_chat_messages(chat_id)
            context_contents = []
            for h in history[-8:]:
                context_contents.append({"role": "user", "parts": [{"text": h.get("prompt", "")}]})
                context_contents.append({"role": "model", "parts": [{"text": h.get("response", "")}]})

            current_text = prompt
            if web_context:
                current_text = f"{prompt}\n\n[INFORMAÇÃO EM TEMPO REAL DA INTERNET]:\n{web_context}"

            current_parts = []
            if current_text:
                current_parts.append({"text": current_text})
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
                    "has_image": bool(image_b64),
                    "has_web_context": bool(web_context),
                    "skill": skill_key
                }
                history.append(msg_record)
                save_chat_messages(chat_id, history)

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

        # Gerador Nativo de PDF em Alta Qualidade para Download
        elif parsed.path == "/api/export-pdf":
            text = body.get("text", "").strip()
            title = body.get("title", "Documento Montanha Studio").strip()
            if not text:
                self._send_json({"status": "error", "message": "Texto vazio"}, 400)
                return

            pdf_filename = f"documento_{int(time.time())}_{uuid.uuid4().hex[:4]}.pdf"
            pdf_path = PDF_DIR / pdf_filename

            if REPORTLAB_AVAILABLE:
                try:
                    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
                    styles = getSampleStyleSheet()
                    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#131314'), spaceAfter=14)
                    body_style = ParagraphStyle('DocBody', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=15, textColor=colors.HexColor('#282a2c'), spaceAfter=8)

                    story = []
                    story.append(Paragraph(title, title_style))
                    story.append(Spacer(1, 10))

                    for paragraph in text.split("\n\n"):
                        clean_p = paragraph.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
                        if clean_p.strip():
                            story.append(Paragraph(clean_p, body_style))
                            story.append(Spacer(1, 4))

                    doc.build(story)
                    self._send_json({
                        "status": "success",
                        "pdf_url": f"/pdf/{pdf_filename}",
                        "filename": pdf_filename
                    })
                    return
                except Exception as e:
                    self._send_json({"status": "error", "message": f"Erro ao gerar PDF: {str(e)}"}, 500)
                    return
            else:
                self._send_json({"status": "error", "message": "ReportLab indisponível"}, 500)
                return

        # Geração de Áudio TTS com Controle de Velocidade e Download
        elif parsed.path == "/api/tts":
            text = body.get("text", "").strip()
            voice = body.get("voice", "pt-BR-AntonioNeural")
            speed = body.get("speed", 1.0) # ex: 0.9, 1.0, 1.1, 1.25

            if not text:
                self._send_json({"status": "error", "message": "Texto vazio para TTS"}, 400)
                return

            pct = int(round((float(speed) - 1.0) * 100))
            rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"

            out_name = f"locucao_{int(time.time())}_{uuid.uuid4().hex[:4]}.mp3"
            out_file = AUDIO_DIR / out_name

            tts_success = False
            if edge_tts:
                try:
                    async def _run_edge():
                        comm = edge_tts.Communicate(text[:1500], voice, rate=rate_str)
                        await comm.save(str(out_file))
                    asyncio.run(_run_edge())
                    tts_success = True
                except Exception:
                    pass

            if not tts_success:
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
                "filename": out_name,
                "speed": speed
            })
            return

        elif parsed.path == "/api/generate-image":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_json({"status": "error", "message": "Prompt de imagem vazio"}, 400)
                return

            enc_prompt = urllib.parse.quote(prompt)
            seed = int(time.time() * 1000) % 999999
            image_url = f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1024&height=1024&model=flux&seed={seed}&nologo=true"
            fallback_url = f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1024&height=1024&model=turbo&seed={seed}&nologo=true"

            self._send_json({
                "status": "success",
                "image_url": image_url,
                "fallback_url": fallback_url,
                "prompt": prompt
            })
            return

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
                "extracted_text": extracted_text[:25000]
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
    print(f"[*] Montanha Gemini Studio v3.0 ativo na porta {port}")
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
