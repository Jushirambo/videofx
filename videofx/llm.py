import json
import os
import re
import urllib.request

DEFAULT_MODELS = {
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
}

BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "huggingface": "https://router.huggingface.co/v1/chat/completions",
}

ENV_KEYS = {
    "openrouter": "OPENROUTER_API_KEY",
    "huggingface": "HF_TOKEN",
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
        "narração envolvente com tensão crescente, revelações graduais, "
        "climax perto do final"
    ),
}

SYSTEM_PROMPT = (
    "Você é roteirista de vídeos curtos verticais (TikTok/Reels/Shorts) em português do Brasil. "
    "Responda SEMPRE com um JSON válido no formato exato: "
    '{"title": "titulo curto em caixa alta", "scenes": ["fala da cena 1", "fala da cena 2", ...]}. '
    "Regras para as falas: português natural falado (para narração), frases de no máximo 12 palavras, "
    "primeira cena é um gancho forte, última cena é uma chamada para ação curta. NÃO use markdown, "
    "não escreva nada fora do JSON."
)


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
    url = BASE_URLS[provider]
    key = api_key or os.environ.get(ENV_KEYS[provider]) or os.environ.get("LLM_API_KEY")
    if not key:
        raise RuntimeError(
            f"sem API key para {provider}: use 'api_key' na config ou a env {ENV_KEYS[provider]}"
        )
    body = json.dumps({
        "model": model or DEFAULT_MODELS[provider],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.9,
        "max_tokens": 1200,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    req.add_header("HTTP-Referer", "https://github.com/Jushirambo/videofx")
    req.add_header("User-Agent", "videofx/2.0")
    try:
        r = urllib.request.urlopen(req, timeout=90)
        data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"{provider} indisponível: {type(e).__name__}: {str(e)[:200]}")


def generate_script(cfg):
    provider = cfg.get("provider", "template")
    if provider == "template" or not cfg.get("provider"):
        return None, None
    style = STYLES.get(cfg.get("script_style", "viral"), STYLES["viral"])
    user = (
        f"Crie um roteiro de {cfg.get('n_scenes', 5)} cenas sobre: {cfg.get('topic')}. "
        f"Estilo: {style}. Duração total alvo: {cfg.get('duration_target', 30)} segundos."
    )
    content = chat(provider, SYSTEM_PROMPT, user,
                   cfg.get("model"), cfg.get("api_key"))
    title, scenes = _extract_json(content)
    return title, scenes
