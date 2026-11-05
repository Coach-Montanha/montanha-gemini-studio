"""
Vercel Serverless Function Handler for Montanha Gemini Studio v4.0
Multi-Engine Harness (Gemini + Groq + DeepSeek), Dynamic Plugins & Settings
"""

import os
import json
import uuid
import time
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

SKILLS_PROMPTS = {
    "minha-voz": (
        "Você é o Coach Montanha, operando sob a diretriz MINHA VOZ.\n"
        "1. Tom: Direto, firme, de quem opera no campo de batalha, sem enrolação e sem rodeios corporativos.\n"
        "2. Abertura: Gancho forte ou constatação crua da realidade. Zero 'olá pessoal'.\n"
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
    if permanent_skills.get("minha_voz", True):
        parts.append("[DIRETRIZ PERMANENTE - IDENTIDADE COACH MONTANHA]: Fale direto ao ponto, com firmeza e experiência prática.")
    if permanent_skills.get("conferir_rule", True):
        parts.append("[DIRETRIZ PERMANENTE - REGRA [CONFERIR]]: Nunca invente números ou datas. Na ausência do dado, declare [CONFERIR].")
    if permanent_skills.get("karpathy_ponytail", True):
        parts.append("[DIRETRIZ PERMANENTE - PONYTAIL/KARPATHY]: Código limpo, cirúrgico, sem dependências desnecessárias.")

    selected_skill = SKILLS_PROMPTS.get(skill_key, SKILLS_PROMPTS["minha-voz"])
    parts.append(f"[SKILL ATIVA]:\n{selected_skill}")

    enabled_plugins = []
    if plugins_config.get("gcalendar", True):
        enabled_plugins.append("- Google Calendar: Ao agendar eventos, emita bloco estruturado ```workspace_action {\"tool\": \"calendar_create_event\", ...}```")
    if plugins_config.get("gsheets", True):
        enabled_plugins.append("- Google Sheets: Ao salvar linhas em planilhas, emita ```workspace_action {\"tool\": \"sheets_append_row\", ...}```")

    if enabled_plugins:
        parts.append("[PLUGINS WORKSPACE ATIVOS]:\n" + "\n".join(enabled_plugins))

    return "\n\n".join(parts)

def get_live_web_context(query, plugins_config):
    if not plugins_config.get("web_search", True) and not plugins_config.get("live_weather", True):
        return ""
    ql = query.lower()
    snippets = []
    if plugins_config.get("live_weather", True) and any(k in ql for k in ["clima", "tempo", "temperatura", "previsão"]):
        city = "Joao Pessoa"
        for candidate in ["joao pessoa", "joão pessoa", "são paulo", "sao paulo", "rio de janeiro", "recife", "fortaleza", "curitiba"]:
            if candidate in ql:
                city = candidate.title()
                break
        try:
            city_enc = urllib.parse.quote(city)
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_enc}&count=1&language=pt&format=json"
            req_geo = urllib.request.Request(geo_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_geo, timeout=3) as r:
                gdata = json.loads(r.read().decode())
                if gdata.get("results"):
                    res = gdata["results"][0]
                    lat, lon = res["latitude"], res["longitude"]
                    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m"
                    req_w = urllib.request.Request(w_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req_w, timeout=3) as rw:
                        w = json.loads(rw.read().decode())["current"]
                        snippets.append(
                            f"[METEOROLOGIA AO VIVO]: {city} | Temp: {w['temperature_2m']}°C (Sensação: {w['apparent_temperature']}°C) | Umidade: {w['relative_humidity_2m']}%"
                        )
        except Exception:
            pass

    return "\n".join(snippets)

class handler(BaseHTTPRequestHandler):
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
        if parsed.path.endswith("/status"):
            self._send_json({
                "status": "online",
                "platform": "Vercel Serverless Cloud",
                "app": "Montanha Gemini Studio v4.0",
                "model": "gemini-flash-lite-latest",
                "gemini_key_configured": bool(GEMINI_API_KEY),
                "groq_key_configured": bool(GROQ_API_KEY)
            })
            return

        self._send_json({"status": "running", "service": "Montanha Gemini Studio API v4.0"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        if parsed.path.endswith("/chat"):
            prompt = body.get("prompt", "").strip()
            skill_key = body.get("skill", "minha-voz")
            image_b64 = body.get("image_base64", "")
            mime_type = body.get("mime_type", "image/jpeg")
            plugins_config = body.get("plugins", {"web_search": True, "live_weather": True, "gcalendar": True, "gsheets": True})
            permanent_skills = body.get("permanent_skills", {"minha_voz": True, "conferir_rule": True, "karpathy_ponytail": True})
            engine = body.get("engine", "gemini-flash-lite-latest")

            system_prompt = build_system_prompt(skill_key, plugins_config, permanent_skills)

            if not prompt and not image_b64:
                self._send_json({"status": "error", "message": "Mensagem vazia"}, 400)
                return

            # Groq Llama Dispatch
            user_groq_key = body.get("groq_api_key") or GROQ_API_KEY
            if ("groq" in engine.lower() or "llama" in engine.lower()) and user_groq_key and not image_b64:
                try:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {user_groq_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
                    }
                    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        res = json.loads(resp.read().decode())
                        ans = res["choices"][0]["message"]["content"]
                        self._send_json({"status": "success", "response": ans, "model": "Groq Llama 3.3 70B"})
                        return
                except Exception as e:
                    pass

            api_key = body.get("api_key") or GEMINI_API_KEY
            if not api_key:
                self._send_json({"status": "error", "message": "Chave GEMINI_API_KEY não configurada."}, 400)
                return

            web_context = get_live_web_context(prompt, plugins_config)
            current_text = prompt
            if web_context:
                current_text = f"{prompt}\n\n[INFORMAÇÃO EM TEMPO REAL]:\n{web_context}"

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

            payload = {
                "contents": [{"role": "user", "parts": current_parts}],
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
            }

            model_candidates = ["gemini-flash-lite-latest", "gemini-flash-latest"]
            last_err = ""
            for candidate in model_candidates:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={api_key}"
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        res_data = json.loads(resp.read().decode())
                        candidate_resp = res_data.get("candidates", [{}])[0]
                        parts = candidate_resp.get("content", {}).get("parts", [])
                        text_ans = "".join([p.get("text", "") for p in parts]).strip()
                        if text_ans:
                            self._send_json({"status": "success", "response": text_ans, "model": candidate})
                            return
                except Exception as ex:
                    last_err = str(ex)

            self._send_json({"status": "error", "message": f"Erro Gemini API: {last_err}"}, 500)
            return

        elif parsed.path.endswith("/generate-image"):
            prompt = body.get("prompt", "").strip()
            import random
            seed = random.randint(1000, 999999)
            enc_prompt = urllib.parse.quote(prompt)
            image_url = f"https://image.pollinations.ai/prompt/{enc_prompt}?model=flux&width=1024&height=1024&nologo=true&seed={seed}"
            self._send_json({"status": "success", "image_url": image_url, "provider": "Flux.1 Ultra HD"})
            return

        self._send_json({"status": "error", "message": "Endpoint não encontrado"}, 404)
