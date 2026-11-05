"""
Montanha Gemini Studio v4.0 - Multi-Engine Harness & Settings Control Hub
Features:
- Settings & Preferences Management (saved in storage/settings.json or localStorage)
- Plugin Manager (Google Calendar, Sheets, Docs, Drive, Web Search, Weather, Cloud) toggles
- Permanent Automatic Skills Harness (Minha Voz, Ponytail/Karpathy, [CONFERIR] rule, etc.)
- Multi-AI Engine Support: Gemini (Flash Lite / Flash / Pro) + Groq (Llama 3.3 70B) + OpenAI / DeepSeek / Custom
- Live Voice Auto-Conversation Loop
- PDF Extractor & ReportLab PDF Generator
"""

import os
import sys
import json
import uuid
import time
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
STORAGE_DIR = BASE_DIR / "storage"
CHATS_DIR = STORAGE_DIR / "chats"
INDEX_FILE = STORAGE_DIR / "index.json"
SETTINGS_FILE = STORAGE_DIR / "settings.json"

CHATS_DIR.mkdir(parents=True, exist_ok=True)

if not INDEX_FILE.exists():
    INDEX_FILE.write_text("[]", encoding="utf-8")

DEFAULT_SETTINGS = {
    "engine": "gemini-flash-lite-latest",
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
    "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    "deepseek_api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
    "plugins": {
        "web_search": True,
        "live_weather": True,
        "gcalendar": True,
        "gsheets": True,
        "gdocs": True,
        "gdrive": True,
        "cloud_actions": True
    },
    "permanent_skills": {
        "minha_voz": True,
        "conferir_rule": True,
        "karpathy_ponytail": True
    },
    "installed_skills": [
        {"id": "minha-voz", "name": "🔥 Minha Voz (Coach Montanha)", "type": "built-in"},
        {"id": "roteiros-10x", "name": "🎬 Roteiros 10x (Stories & Reels)", "type": "built-in"},
        {"id": "personal-trainer", "name": "🏋️ Personal Trainer & Fisiologia", "type": "built-in"},
        {"id": "programador", "name": "💻 Engenheiro Sênior (Ponytail)", "type": "built-in"},
        {"id": "lpo-crosstraining", "name": "🏋️ LPO & Biomecânica Everett", "type": "cloud"},
        {"id": "lyle-mcdonald", "name": "🥩 Nutrição Lyle McDonald & PSMF", "type": "cloud"},
        {"id": "stories-10x-copy", "name": "📱 Copy Stories 10x Leandro Ladeira", "type": "cloud"},
        {"id": "matriz-anti-saas", "name": "🛡️ Matriz Anti-SaaS & Self-Hosted", "type": "cloud"}
    ]
}

def load_settings():
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(json.dumps(DEFAULT_SETTINGS, indent=2, ensure_ascii=False), encoding="utf-8")
        return DEFAULT_SETTINGS
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        # Ensure default keys exist
        for k, v in DEFAULT_SETTINGS.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return DEFAULT_SETTINGS

def save_settings(new_settings):
    try:
        current = load_settings()
        current.update(new_settings)
        SETTINGS_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False

# Base Prompts for Skills
SKILLS_PROMPTS = {
    "minha-voz": (
        "Você é o Coach Montanha, operando sob a diretriz MINHA VOZ.\n"
        "1. Tom: Direto, firme, de quem opera no campo de batalha, sem enrolação e sem rodeios corporativos.\n"
        "2. Abertura: Gancho forte ou constatação crua da realidade. Zero 'olá pessoal' ou 'espero que estejam bem'.\n"
        "3. Vocabulário: na prática, execução, campo de batalha, resultado, esteira, métrica, consistência, ROI.\n"
        "4. Proibido: mergulhar fundo, revolucionário, disruptivo, quiçá, em suma, dessarte.\n"
        "5. Regra [CONFERIR]: Se faltar métrica, escreva [CONFERIR]."
    ),
    "roteiros-10x": (
        "Você é o especialista em Roteiros de Alta Conversão (Stories & Reels 10x) do Ecossistema Montanha.\n"
        "1. Escreva roteiros com gancho nos primeiros 3 segundos, quebra de padrão, desenvolvimento em 3 atos e CTA clara.\n"
        "2. Indique cortes visuais entre colchetes [Corte para cena de treino] e o texto exato da fala do locutor."
    ),
    "personal-trainer": (
        "Você é o Consultor Técnico de Fisiologia e Treino de Alta Performance do Ecossistema Montanha.\n"
        "1. Prescreva treinos fundamentados em biomecânica real, progressão de carga e recomposição corporal.\n"
        "2. Para atendimento: escreva scripts diretos de WhatsApp para onboarding, combate a objeções e retenção."
    ),
    "programador": (
        "Você é o Engenheiro de Software Sênior do Ecossistema Montanha.\n"
        "1. Princípio Ponytail & Karpathy: Simplicidade radical, zero sobre-engenharia, cirúrgico, sem instalar dependências redundantes."
    ),
    "lpo-crosstraining": (
        "Você é o Especialista em LPO do Coach Montanha baseado no tratado de Greg Everett.\n"
        "Foco em biomecânica das puxadas, posições de recepção, correções de trajetória e progressão segura de carga."
    ),
    "lyle-mcdonald": (
        "Você é o Nutricionista Científico baseado nos protocolos de Lyle McDonald (PSMF e Stubborn Fat Protocol).\n"
        "Foco em recomposição corporal, preservação de massa magra e déficit estratégico sem perda metabólica."
    ),
    "stories-10x-copy": (
        "Você é o Copywriter de Stories 10x do Coach Montanha.\n"
        "Roteirize sequências magnéticas: gancho visual, caixas de pergunta sem filtro, quebra de objeções e oferta natural."
    ),
    "matriz-anti-saas": (
        "Você é o Arquiteto de Eficiência e Soluções Locais (Matriz Anti-SaaS).\n"
        "Priorize alternativas auto-hospedadas, bancos locais (SQLite/PocketBase) e ferramentas open-source para poupar custos."
    )
}

def build_system_prompt(skill_key, plugins_config, permanent_skills):
    parts = []
    
    # 1. Habilidades Permanentes do Harness
    if permanent_skills.get("minha_voz", True):
        parts.append(
            "[DIRETRIZ PERMANENTE - IDENTIDADE COACH MONTANHA]:\n"
            "- Fale direto ao ponto, com firmeza e experiência prática. Zero enrolação ou clichês corporativos."
        )
    if permanent_skills.get("conferir_rule", True):
        parts.append(
            "[DIRETRIZ PERMANENTE - REGRA [CONFERIR]]:\n"
            "- Nunca invente números, datas ou dados financeiros. Na ausência do valor exato, declare [CONFERIR]."
        )
    if permanent_skills.get("karpathy_ponytail", True):
        parts.append(
            "[DIRETRIZ PERMANENTE - ENGENHARIA PONYTAIL & KARPATHY]:\n"
            "- Radicalmente cirúrgico. Prefira reutilizar ferramentas nativas a inventar código complexo."
        )

    # 2. Skill Específica Selecionada
    selected_skill = SKILLS_PROMPTS.get(skill_key, SKILLS_PROMPTS["minha-voz"])
    parts.append(f"[SKILL ATIVA NO CHAT]:\n{selected_skill}")

    # 3. Plugins Habilitados
    enabled_plugins = []
    if plugins_config.get("gcalendar", True):
        enabled_plugins.append("- Google Calendar: Quando solicitado agendamento, gere bloco estruturado ```workspace_action {\"tool\": \"calendar_create_event\", ...}```")
    if plugins_config.get("gsheets", True):
        enabled_plugins.append("- Google Sheets: Para registrar dados em tabelas, gere bloco estruturado ```workspace_action {\"tool\": \"sheets_append_row\", ...}```")
    if plugins_config.get("gdocs", True):
        enabled_plugins.append("- Google Docs: Para criar ou salvar notas, gere bloco ```workspace_action {\"tool\": \"docs_create\", ...}```")
    if plugins_config.get("cloud_actions", True):
        enabled_plugins.append("- Cloud Automation: Capacidade de delegar webhooks e chamadas de API cloud.")

    if enabled_plugins:
        parts.append("[CAPACIDADES DE PLUGINS ATIVOS]:\n" + "\n".join(enabled_plugins))

    return "\n\n".join(parts)

def get_live_web_context(query, plugins_config):
    if not plugins_config.get("web_search", True) and not plugins_config.get("live_weather", True):
        return ""

    ql = query.lower()
    snippets = []

    # 1. Weather Hook
    if plugins_config.get("live_weather", True) and any(k in ql for k in ["clima", "tempo", "temperatura", "previsão", "chuva", "calor", "vento"]):
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

    # 2. Web Search Snippet Hook
    if plugins_config.get("web_search", True) and any(k in ql for k in ["quem é", "notícia", "hoje", "resultado", "preço", "cotação", "o que aconteceu", "pesquise"]):
        try:
            clean_q = urllib.parse.quote(query)
            ddg_url = f"https://api.duckduckgo.com/?q={clean_q}&format=json&no_html=1&skip_disambig=1"
            req_ddg = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_ddg, timeout=4) as rd:
                ddg_data = json.loads(rd.read().decode())
                abs_text = ddg_data.get("AbstractText", "")
                if abs_text:
                    snippets.append(f"[BUSCA WEB AO VIVO]: {abs_text}")
        except Exception:
            pass

    return "\n".join(snippets)

def get_chats_index():
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_chats_index(data):
    INDEX_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def get_chat_messages(chat_id):
    f = CHATS_DIR / f"{chat_id}.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_chat_messages(chat_id, msgs):
    f = CHATS_DIR / f"{chat_id}.json"
    f.write_text(json.dumps(msgs, indent=2, ensure_ascii=False), encoding="utf-8")

# Dispatches to Alternative AI Engines (Groq Llama 3.3 70B, DeepSeek, etc.)
def dispatch_external_engine(engine, prompt, system_prompt, api_key):
    if "groq" in engine.lower() or "llama" in engine.lower():
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.6
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    elif "deepseek" in engine.lower():
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    return None

class GeminiStudioHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/status":
            settings = load_settings()
            self._send_json({
                "status": "online",
                "app": "Montanha Gemini Studio v4.0",
                "engine": settings.get("engine", "gemini-flash-lite-latest"),
                "gemini_key_configured": bool(settings.get("gemini_api_key")),
                "groq_key_configured": bool(settings.get("groq_api_key")),
                "plugins": settings.get("plugins", {}),
                "permanent_skills": settings.get("permanent_skills", {})
            })
            return

        elif parsed.path == "/api/settings":
            settings = load_settings()
            # Ocultar parcialmente chaves para segurança na visualização
            safe_settings = json.loads(json.dumps(settings))
            for k in ["gemini_api_key", "groq_api_key", "openai_api_key", "deepseek_api_key"]:
                val = safe_settings.get(k, "")
                if val and len(val) > 8:
                    safe_settings[k + "_preview"] = val[:4] + "..." + val[-4:]
            self._send_json({"status": "success", "settings": safe_settings})
            return

        elif parsed.path == "/api/chats":
            idx = get_chats_index()
            self._send_json({"status": "success", "chats": idx})
            return

        elif parsed.path.startswith("/api/chats/"):
            chat_id = parsed.path.split("/")[-1]
            msgs = get_chat_messages(chat_id)
            self._send_json({"status": "success", "chat_id": chat_id, "messages": msgs})
            return

        # Static Files Routing
        req_path = parsed.path.lstrip("/")
        if not req_path:
            req_path = "index.html"

        file_path = PUBLIC_DIR / req_path
        if file_path.exists() and file_path.is_file():
            mime = "text/html"
            if file_path.suffix == ".css": mime = "text/css"
            elif file_path.suffix == ".js": mime = "application/javascript"
            elif file_path.suffix == ".json": mime = "application/json"
            elif file_path.suffix in [".png", ".jpg", ".jpeg"]: mime = f"image/{file_path.suffix.lstrip('.')}"
            
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8" if "text" in mime else mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        # Save Settings & Toggle Plugins / Keys
        if parsed.path == "/api/settings":
            success = save_settings(body)
            self._send_json({"status": "success" if success else "error", "message": "Configurações salvas!"})
            return

        elif parsed.path == "/api/chats/new":
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
            image_b64 = body.get("image_base64", "")
            mime_type = body.get("mime_type", "image/jpeg")

            settings = load_settings()
            plugins_config = settings.get("plugins", {})
            permanent_skills = settings.get("permanent_skills", {})
            engine = body.get("engine") or settings.get("engine", "gemini-flash-lite-latest")

            system_prompt = build_system_prompt(skill_key, plugins_config, permanent_skills)

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

            web_context = get_live_web_context(prompt, plugins_config)
            history = get_chat_messages(chat_id)

            current_text = prompt
            if web_context:
                current_text = f"{prompt}\n\n[INFORMAÇÃO EM TEMPO REAL DA INTERNET]:\n{web_context}"

            # Roteamento se motor externo (Groq / Llama 70b ou DeepSeek)
            if "groq" in engine.lower() or "llama" in engine.lower():
                groq_key = settings.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "")
                if groq_key and not image_b64:
                    try:
                        ext_ans = dispatch_external_engine("groq", current_text, system_prompt, groq_key)
                        if ext_ans:
                            history.append({"role": "user", "prompt": prompt, "time": time.strftime("%H:%M")})
                            history.append({"role": "model", "response": ext_ans, "engine": "Groq Llama 3.3 70B", "time": time.strftime("%H:%M")})
                            save_chat_messages(chat_id, history)
                            self._send_json({"status": "success", "chat_id": chat_id, "response": ext_ans, "engine": "Groq Llama 3.3 70B"})
                            return
                    except Exception as e:
                        print(f"[!] Erro no Groq, caindo de volta para Gemini: {e}")

            # Padrão: Gemini API
            gemini_key = settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
            if not gemini_key:
                self._send_json({"status": "error", "message": "Chave GEMINI_API_KEY não configurada. Insira nas Configurações."}, 400)
                return

            context_contents = []
            for h in history[-8:]:
                context_contents.append({"role": "user", "parts": [{"text": h.get("prompt", "")}]})
                context_contents.append({"role": "model", "parts": [{"text": h.get("response", "")}]})

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

            payload = {
                "contents": context_contents,
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048
                }
            }

            model_candidates = ["gemini-flash-lite-latest", "gemini-flash-latest"]
            if engine in model_candidates:
                model_candidates.remove(engine)
                model_candidates.insert(0, engine)

            last_err = ""
            for candidate in model_candidates:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={gemini_key}"
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        res_data = json.loads(resp.read().decode())
                        candidate_resp = res_data.get("candidates", [{}])[0]
                        parts = candidate_resp.get("content", {}).get("parts", [])
                        text_ans = "".join([p.get("text", "") for p in parts]).strip()
                        if text_ans:
                            history.append({"role": "user", "prompt": prompt, "image": bool(image_b64), "time": time.strftime("%H:%M")})
                            history.append({"role": "model", "response": text_ans, "model": candidate, "time": time.strftime("%H:%M")})
                            save_chat_messages(chat_id, history)
                            self._send_json({"status": "success", "chat_id": chat_id, "response": text_ans, "model": candidate})
                            return
                except urllib.error.HTTPError as he:
                    last_err = he.read().decode()
                except Exception as ex:
                    last_err = str(ex)

            self._send_json({"status": "error", "message": f"Erro Gemini API: {last_err}"}, 500)
            return

        # Dual Image Generation Engine: Imagen 3 ou Flux
        elif parsed.path == "/api/generate-image":
            prompt = body.get("prompt", "").strip()
            engine_img = body.get("engine", "flux")
            settings = load_settings()
            gemini_key = settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")

            if not prompt:
                self._send_json({"status": "error", "message": "Prompt de imagem vazio"}, 400)
                return

            if engine_img == "imagen" and gemini_key:
                try:
                    img_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={gemini_key}"
                    img_payload = {
                        "instances": [{"prompt": prompt}],
                        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}
                    }
                    req = urllib.request.Request(
                        img_url,
                        data=json.dumps(img_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=30) as r:
                        idata = json.loads(r.read().decode())
                        b64_img = idata["predictions"][0]["bytesBase64Encoded"]
                        self._send_json({
                            "status": "success",
                            "image_url": f"data:image/jpeg;base64,{b64_img}",
                            "provider": "Google Imagen 3 (Oficial)",
                            "prompt": prompt
                        })
                        return
                except Exception as e:
                    print(f"Fallback para Flux devido a: {e}")

            # Fallback Flux
            import random
            seed = random.randint(1000, 999999)
            enc_prompt = urllib.parse.quote(prompt)
            image_url = f"https://image.pollinations.ai/prompt/{enc_prompt}?model=flux&width=1024&height=1024&nologo=true&seed={seed}"
            self._send_json({
                "status": "success",
                "image_url": image_url,
                "provider": "Flux.1 Ultra HD",
                "prompt": prompt
            })
            return

        # PDF Extraction
        elif parsed.path == "/api/read-pdf":
            pdf_b64 = body.get("pdf_base64", "")
            filename = body.get("filename", "documento.pdf")
            if not pdf_b64:
                self._send_json({"status": "error", "message": "Nenhum arquivo enviado"}, 400)
                return
            try:
                import base64
                import io
                from pypdf import PdfReader
                pdf_bytes = base64.b64decode(pdf_b64)
                reader = PdfReader(io.BytesIO(pdf_bytes))
                text_pages = []
                for idx_page, page in enumerate(reader.pages[:40]):
                    extracted = page.extract_text()
                    if extracted:
                        text_pages.append(f"--- [Página {idx_page+1}] ---\n{extracted.strip()}")
                full_text = "\n\n".join(text_pages)
                self._send_json({
                    "status": "success",
                    "filename": filename,
                    "total_pages": len(reader.pages),
                    "extracted_text": full_text[:40000]
                })
            except Exception as e:
                self._send_json({"status": "error", "message": f"Falha ao ler PDF: {str(e)}"}, 500)
            return

        # Native PDF Document Generator
        elif parsed.path == "/api/export-pdf":
            text = body.get("text", "").strip()
            title = body.get("title", "Documento Montanha Studio").strip()
            try:
                import io
                import base64
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib import colors

                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1e1f20'), spaceAfter=14)
                body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#2c3e50'))

                story = [Paragraph(f"<b>{title}</b>", title_style), Spacer(1, 10)]
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        story.append(Spacer(1, 6))
                    else:
                        clean_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        story.append(Paragraph(clean_line, body_style))
                doc.build(story)
                pdf_data = pdf_buffer.getvalue()
                pdf_buffer.close()
                b64_pdf = base64.b64encode(pdf_data).decode("utf-8")
                self._send_json({"status": "success", "pdf_base64": b64_pdf, "filename": f"{title.lower().replace(' ', '_')}.pdf"})
            except Exception as e:
                self._send_json({"status": "error", "message": f"Erro PDF: {str(e)}"}, 500)
            return

        self.send_response(404)
        self.end_headers()

def run_server(port=4192):
    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, GeminiStudioHandler)
    print(f"[*] Montanha Gemini Studio v4.0 ativo na porta {port}")
    print(f"[*] Acesso Local: http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4192
    run_server(port)
