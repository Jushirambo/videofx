import json
import os
import re
import urllib.request

DEFAULT_MODELS = {
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
    "gemini": "gemini-2.5-flash",
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
    return cfg.get("api_key") or None


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("modelo não retornou JSON")
    data = json.loads(m.group(0))
    scenes = [str(s).strip() for s in data.get("scenes", []) if str(s).strip()]
    if not scenes:
        raise ValueError("JSON sem cenas")
    return data.get("title", ""), scenes


def chat(provider, system, user, model, api_key):
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
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + api_key)
    req.add_header("Content-Type", "application/json")
    req.add_header("HTTP-Referer", "https://github.com/Jushirambo/videofx")
    req.add_header("User-Agent", "videofx/2.0")
    try:
        r = urllib.request.urlopen(req, timeout=90)
        data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"]
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{provider}: resposta não JSON: {e}")


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
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "videofx/2.0")
    try:
        r = urllib.request.urlopen(req, timeout=90)
        data = json.loads(r.read().decode())
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p["text"] for p in parts if "text" in p)
    except Exception as e:
        raise RuntimeError(f"gemini indisponível: {type(e).__name__}: {str(e)[:200]}")


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
        model = ((cfg.get("models") or {}).get(provider)
                 or (cfg.get("model") if provider == cfg.get("provider") else None)
                 or DEFAULT_MODELS[provider])
        try:
            content = chat(provider, SYSTEM_PROMPT, user, model, key)
            title, scenes = _extract_json(content)
            return title, scenes
        except Exception as e:
            tried.append(f"{provider}:{type(e).__name__}")
    raise RuntimeError(
        "nenhum provedor de roteiro funcionou (" + ", ".join(tried) + ")"
    )
