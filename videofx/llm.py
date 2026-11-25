import json
import os
import re
import time
import urllib.error
import urllib.request

DEFAULT_MODELS = {
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
    "gemini": "gemini-2.5-flash",
}

MODEL_FALLBACKS = {
    "openrouter": ["meta-llama/llama-3.3-70b-instruct:free"],
    "gemini": ["gemini-flash-latest", "gemini-2.0-flash"],
    "huggingface": ["meta-llama/Meta-Llama-3-8B-Instruct"],
}

ENV_KEYS = {
    "openrouter": ["OPENROUTER_API_KEY", "OPENROUTER_KEY"],
    "huggingface": ["HF_TOKEN", "HUGGINGFACE_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
}

STYLES = {
    "viral": (
        "ganchos de choque nos primeiros segundos, linguagem de internet, "
        "frases curtas e diretas, provocação de curiosidade, tom informal"
    ),
    "educativo": (
        "explicações claras, fatos concretos, tom confiável porém acessível, "
        "sem jargão desnecessário"
    ),
    "storytelling": (
        "narrativa envolvente com tensão crescente, revelações graduais, "
        "clímax perto do final"
    ),
}

SYSTEM_PROMPT = (
    "Você é roteirista de vídeos curtos verticais (TikTok/Reels/Shorts) em português do Brasil. "
    "Responda SEMPRE com um JSON válido no formato exato: "
    '{"title": "titulo curto em caixa alta", "scenes": ["fala da cena 1", "fala da cena 2", ...]}. '
    "Regras para as falas: português natural falado (para narração), frases de no máximo 12 palavras, "
    "primeira cena é um gancho forte, última cena é uma chamada para ação curta. Você escreve roteiros "
    "originais, específicos e concretos: cote números, nomes e exemplos reais do tema, evite frases "
    "genéricas de apresentação ('neste vídeo', 'vamos ver'). NÃO use markdown, não escreva nada fora do JSON."
)


def script_chain(cfg):
    if cfg.get("scenes"):
        return []
    chain = cfg.get("script_providers")
    if not chain:
        single = cfg.get("provider")
        if not single or single == "template":
            return []
        if single == "auto":
            chain = ["gemini", "openrouter", "huggingface"]
        else:
            chain = [single]
    return [p.strip() for p in chain if p.strip()]


def resolve_key(cfg, provider):
    keys = cfg.get("api_keys") or {}
    key = keys.get(provider)
    if key:
        return key
    for name in ENV_KEYS.get(provider, []):
        key = os.environ.get(name)
        if key:
            return key
    if provider == cfg.get("provider"):
        return cfg.get("api_key") or None
    if cfg.get("provider") == "auto" and provider == "openrouter":
        return cfg.get("api_key") or None
    return None


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("modelo não retornou JSON")
    data = json.loads(m.group(0))
    scenes = [str(s).strip() for s in data.get("scenes", []) if str(s).strip()]
    if not scenes:
        raise ValueError("JSON sem cenas")
    return data.get("title", ""), scenes


def _http_error(name, e):
    body = ""
    try:
        body = e.read().decode()[:300]
    except Exception:
        pass
    return RuntimeError(f"{name} HTTP {e.code}: {body}")


def _post_with_retry(url, body, headers, name, timeout=90):
    for attempt in range(2):
        req = urllib.request.Request(url, data=body, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt == 0:
                time.sleep(2)
                continue
            raise _http_error(name, e)
    if provider == "gemini":
        return _chat_gemini(system, user, model, api_key)
    if provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
    elif provider == "huggingface":
        url = "https://router.huggingface.co/v1/chat/completions"
    else:
        raise RuntimeError(f"provedor desconhecido: {provider}")
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.9,
        "max_tokens": 1200,
    }).encode()
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Jushirambo/videofx",
        "User-Agent": "videofx/2.0",
    }
    data = json.loads(_post_with_retry(url, body, headers, provider).decode())
    return data["choices"][0]["message"]["content"]


def _chat_gemini(system, user, model, api_key):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 1200},
    }).encode()
    data = json.loads(_post_with_retry(url, body, {"Content-Type": "application/json"},
                                       "gemini").decode())
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p["text"] for p in parts if "text" in p)


def generate_script(cfg):
    chain = script_chain(cfg)
    if not chain:
        return None, None
    style = STYLES.get(cfg.get("script_style", "viral"), STYLES["viral"])
    user = (
        f"Crie um roteiro de {cfg.get('n_scenes', 5)} cenas sobre: {cfg.get('topic')}. "
        f"Estilo: {style}. Duração total alvo: {cfg.get('duration_target', 30)} segundos."
    )
    tried = []
    for provider in chain:
        key = resolve_key(cfg, provider)
        if not key:
            tried.append(f"{provider}:sem chave")
            continue
        models = []
        chosen = (cfg.get("models") or {}).get(provider)
        if chosen:
            models.append(chosen)
        elif provider == cfg.get("provider") and cfg.get("model"):
            models.append(cfg["model"])
        models += [DEFAULT_MODELS[provider]] if DEFAULT_MODELS[provider] not in models else []
        models += [m for m in MODEL_FALLBACKS.get(provider, []) if m not in models]
        for model in models:
            try:
                content = chat(provider, SYSTEM_PROMPT, user, model, key)
                title, scenes = _extract_json(content)
                return title, scenes
            except Exception as e:
                tried.append(f"{provider}({model}):{str(e)[:160]}")
    raise RuntimeError(
        "nenhum provedor de roteiro funcionou \n  - " + "\n  - ".join(tried)
    )
