# VideoFX — gerador rápido de vídeos (estilo MoneyPrinter)

Cria vídeos curtos verticais (Reels/TikTok/Shorts) a partir de um tema ou roteiro:
narração por TTS neural em português, roteiro por IA (OpenRouter/HuggingFace), imagens
de fundo, legendas pop, partículas com glow, varredura de brilho, 15 transições,
vinheta e barra de progresso — tudo empacotado com ffmpeg.

**Demo:** [demo_universo.mp4](https://github.com/Jushirambo/videofx/raw/main/out/demo_universo.mp4)

## Pipeline

```
config JSON ──> roteiro (template local ou LLM: OpenRouter / HuggingFace)
                 ├──> TTS Piper (voz pt-BR) ─> duração de cada cena
                 ├──> imagens (image_urls / IA gratuita / fundo procedural)
                 ├──> música procedural (numpy)
                 └──> ffmpeg: Ken Burns + xfade + legendas + título animado
                              + partículas + shine + vinheta + barra de progresso
                              + mix de áudio (narração + música)
```

## Rodar sem instalar nada

**Google Colab (1 clique):**

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Jushirambo/videofx/blob/main/videofx_colab.ipynb)

O notebook `videofx_colab.ipynb` instala tudo, oferece formulário + interface Gradio interativa e baixa o MP4 no navegador.

**Kaggle:** *File → Import Notebook → from GitHub* → cole `https://github.com/Jushirambo/videofx` → Settings → **Internet: ON**.

## Requisitos

- Python 3.10+
- `pip install -r requirements.txt`
- ffmpeg **não** precisa estar instalado (o pacote `imageio-ffmpeg` baixa o binário)
- A voz pt-BR do Piper é baixada automaticamente na primeira execução (~60 MB, Hugging Face)

## Uso

```bash
python main.py --config demo_config.json
python main.py --config demo_config.json -o meuvideo.mp4
```

O vídeo final é salvo em `out/`.

## Config

```jsonc
{
    "topic": "Fatos incríveis sobre o universo",   // tema (gera roteiro automático)
    "scenes": ["Fala 1...", "Fala 2..."],          // opcional: roteiro manual
    "title": "5 FATOS DO UNIVERSO",                // opcional: título animado no início
    "aspect": "9:16",                              // 9:16, 16:9 ou 1:1
    "voice": "voices/pt_BR-faber-medium.onnx",     // voz Piper

    "provider": "template",                        // template | openrouter | huggingface
    "model": null,                                 // ex.: meta-llama/llama-3.3-70b-instruct
    "api_key": null,                               // ou env OPENROUTER_API_KEY / HF_TOKEN
    "script_style": "viral",                       // viral | educativo | storytelling
    "n_scenes": 5,
    "duration_target": 30,                         // duração alvo do roteiro IA (s)

    "transitions": ["fade", "slideleft", "zoomin", "smoothleft", "circleopen"],
    "transition_duration": 0.5,
    "subtitle_style": "pop",                       // pop (bounce) | box | clean
    "music_mood": "calm",                          // calm | energetic
    "music_volume": 0.16,
    "subtitle_size": 64,
    "subtitle_max_chars": 26,                      // quebra de legenda
    "scene_padding": 0.7,
    "min_scene_duration": 2.5,
    "particles": true,                             // partículas flutuantes com glow
    "shine": true,                                 // varredura de brilho periódica
    "vignette": true,                              // escurecimento nas bordas
    "color_boost": true,                           // contraste/saturação realçados
    "progress_bar": true,                          // barra de progresso no rodapé
    "allow_ai_images": true,                       // tenta IA gratuita por cena
    "image_urls": ["https://.../img1.jpg"],        // opcional: imagens prontas por cena
    "output_name": "demo_universo.mp4"
}
```

## Roteiro por IA (OpenRouter / HuggingFace)

Com `provider` diferente de `template`, o roteiro é escrito por um LLM em JSON
({title, scenes[]}) com estilo viral, educativo ou storytelling. Se a chamada
falhar, cai automaticamente no template local.

```bash
export OPENROUTER_API_KEY=sk-or-...   # ou HF_TOKEN=hf_...
```

```jsonc
{
    "topic": "Por que o céu é azul",
    "provider": "openrouter",
    "model": "meta-llama/llama-3.3-70b-instruct",
    "script_style": "viral",
    "duration_target": 35
}
```

Modelos base:
- **OpenRouter:** `meta-llama/llama-3.3-70b-instruct` (qualquer modelo de chat serve)
- **HuggingFace:** `meta-llama/Llama-3.1-8B-Instruct` (via router.huggingface.co)

## Efeitos visuais

- **Ken Burns** por cena (zoom in/out alternado)
- **15 transições** xfade entre cenas (fade, slideleft, zoomin, circleopen, pixelize, ...)
- **Legendas pop** com bounce e fade; estilos `box` (caixa translúcida) e `clean`
- **Título animado** com slide-in e fade-out
- **Partículas** com glow gaussiano em blend screen
- **Shine**: varredura de gradiente vermelho/azul a cada 6s
- **Vinheta**, **realce de cores** e **barra de progresso** no rodapé

Todos ligáveis/desligáveis via config.

### Origens de imagem por cena (ordem de prioridade)

1. Arquivo já existente em `images_out/sceneN.jpg`
2. URLs em `image_urls` (ex.: imagens geradas por IA)
3. IA gratuita (pollinations.ai) via prompt derivado do tema/cena
4. Fundo procedural (gradiente + partículas, sempre funciona offline)

Para trocar as imagens, basta substituir os arquivos em `images_out/` e rodar de novo.

## Estrutura

```
main.py            CLI
videofx/config.py  defaults + resolução por aspecto
videofx/scriptgen  roteiro automático (hooks + fillers) ou manual
videofx/llm.py     roteiro via OpenRouter / HuggingFace (fallback para template)
videofx/tts.py     Piper TTS pt-BR (voz auto-baixada)
videofx/images.py  imagens: locais, URLs, IA ou procedural
videofx/music.py   música procedural (chords + reverb)
videofx/effects.py partículas com glow e varredura de brilho (frames numpy)
videofx/render.py  montagem ffmpeg (zoompan, xfade, drawtext, blends, amix)
demo_config.json   exemplo com roteiro automático
demo_universo.json exemplo completo (cenas manuais + imagens IA)
```

## Licenças

- Fonte DejaVu Sans Bold: licença Bitstream/DejaVu (permissiva, incluída em `assets/fonts/`)
- Voz pt-BR faber: modelo open source do projeto Piper/rhasspy
