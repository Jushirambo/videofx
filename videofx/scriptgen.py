import random

TEMPLATES = [
    "Prepare-se: {topic} vai mudar a forma como você enxerga o mundo.",
    "Preste atenção, porque {topic} é mais surreal do que parece.",
    "Aqui vai algo que quase ninguém sabe sobre {topic}.",
    "Isso pode soar exagerado, mas é a pura verdade sobre {topic}.",
]


def split_scenes(text):
    import re
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return parts


def build_scenes(topic, script_text=None, n_scenes=4, seed=None):
    rng = random.Random(seed)
    if script_text:
        body = split_scenes(script_text)
    else:
        hooks = rng.sample(TEMPLATES, 1)
        fillers = [
            "Estudos recentes mostram que {topic} esconde detalhes surpreendentes.",
            "A cada ano, novas descobertas sobre {topic} deixam cientistas perplexos.",
            "Poucas pessoas conhecem os números reais por trás de {topic}.",
            "E o mais estranho: quanto mais estudamos {topic}, mais perguntas surgem.",
            "Existem fatos sobre {topic} que desafiam a lógica.",
            "Os dados mais recentes sobre {topic} são impressionantes.",
        ]
        body = [f.format(topic=topic) for f in rng.sample(fillers, min(n_scenes, len(fillers)))]
        body.insert(0, hooks[0].format(topic=topic))
        body.append("Se você chegou até aqui, comente o que achou e siga para mais conteúdo assim.")
    return body
