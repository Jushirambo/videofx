# VideoFX — gerador rápido de vídeos (estilo MoneyPrinter)

Cria vídeos curtos verticais (Reels/TikTok/Shorts) a partir de um tema ou roteiro:
narração por TTS neural em português, roteiro por IA (OpenRouter/HuggingFace), imagens
de fundo, legendas pop, partículas com glow, varredura de brilho, 15 transições,
vinheta e barra de progresso — tudo empacotado com ffmpeg.

**Demo:** [demo_universo.mp4](https://github.com/Jushirambo/videofx/raw/main/out/demo_universo.mp4)

## Cadeias de fallback (nunca fica sem conteúdo)

Cada camada tenta o melhor recurso disponível e degrada com elegância ao longo da cadeia:

| Camada | Cadeia (ordem) | Chaves (env ou Colab Secrets) |
|---|---|---|
| **Roteiro** | Gemini → OpenRouter → HuggingFace → template local | `GEMINI_API_KEY` — `OPENROUTER_API_KEY`/`OPENROUTER_KEY` — `HF_TOKEN` |
| **Voz** | ElevenLabs multilingual v2 → Piper pt-BR neural | `ELEVENLABS_API_KEY`/`ELEVEN_LABS_API_KEY` |
| **Imagens** | Pollinations (FLUX) → AI Horde → Pixabay (acervo) → fundo procedural | `POLINATIONS` — `AIHORDE` — `PIXABAY_KEY` |
| **Cenas** | trecho do YouTube → imagens IA → procedural | — |

Use `"provider": "auto"` para tentar toda a cadeia de roteiro automaticamente.

## Trechos do YouTube

Cenas podem usar trechos de vídeos do YouTube como fundo (download parcial via `yt-dlp`),
recortados e convertidos para o formato do vídeo (1080×1920, mute). Cenas com a mesma
divisa-fonte compartilham **um único download** e recebem trechos consecutivos (cena 1
fica pelo início, cena 2 continua de onde a 1 parou) — sem re-baixar o mesmo trecho.
Se uma fonte falhar, as cenas dela voltam para a cadeia de imagens automaticamente.

```jsonc
{
    "yt_clips": [
        "https://youtube.com/watch?v=abc123|12",      // URL | segundo inicial
        "nebula cosmica 4k|30",                       // termo de busca | segundo
        {"query": "saturno 4k", "start": 5}            // dict equivalente
    ],
    "yt_auto": false,          // busca clipes automaticamente a partir do tema/cena
    "yt_height": 720
}
```

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

    "provider": "template",                        // auto | template | openrouter | huggingface | gemini
    "model": null,                                 // ex.: meta-llama/llama-3.3-70b-instruct
    "api_key": null,                               // chave do provedor principal
    "script_providers": null,                      // cadeia custom, ex.: ["gemini", "openrouter"]
    "models": null,                                // ex.: {"gemini": "gemini-2.5-flash"}
    "api_keys": null,                              // ex.: {"openrouter": "sk-or-..."}
    "script_style": "viral",                       // viral | educativo | storytelling
    "n_scenes": 5,
    "duration_target": 30,                         // duração alvo do roteiro IA (s)
    "tts_providers": ["elevenlabs", "piper"],      // cadeia de voz
    "elevenlabs_voice": "rachel",                  // rachel | drew | bella | gabriel | michele
    "image_providers": ["pollinations", "horde", "pixabay"],

    "transitions": ["fade", "slideleft", "zoomin", "smoothleft", "circleopen"],
    "transition_duration": 0.5,
    "subtitle_style": "pop",                       // pop (bounce) | box | clean
    "music_mood": "calm",                          // calm | energetic
    "music_volume": 0.16,
    "subtitle_size": 64,
    "subtitle_max_chars": 26,                      // quebra de legenda
    "scene_padding": 0.7,
    "min_scene_duration": 2.5,
    "particles": false,                            // partículas (off por padrão na v4)
    "shine": false,                                // varredura de brilho
    "vignette": false,                             // escurecimento nas bordas
    "color_boost": false,                          // contraste/saturação realçados
    "progress_bar": false,                         // barra de progresso no rodapé
    "subtitle_position": "bottom",                 // bottom | middle | top
    "subtitle_y": null,                            // afinar: 0.0 (topo) a 1.0 (base)
    "numbered": false,                             // badge por cena: FATO N/M (ou rótulo custom)
    "allow_ai_images": true,                       // tenta IA gratuita por cena
    "image_urls": ["https://.../img1.jpg"],        // opcional: imagens prontas por cena
    "output_name": "demo_universo.mp4"
}
```

## Roteiro por IA

Com `provider` diferente de `template`, o roteiro é escrito por um LLM em JSON
({title, scenes[]}) com estilo viral, educativo ou storytelling — prompts exigem
cenários concretos, números e nomes reais para evitar conteúdo genérico. Se toda
a cadeia falhar, cai automaticamente no template local. Se a chamada falhar
parcialmente, o próximo provedor da cadeia assume.

```bash
export GEMINI_API_KEY=...      # preferred pelo modo auto
export OPENROUTER_API_KEY=sk-or-...
export HF_TOKEN=hf_...
```

```jsonc
{
    "topic": "Por que o céu é azul",
    "provider": "auto",           // tenta Gemini → OpenRouter → HF
    "script_style": "viral",
    "duration_target": 35
}
```

Modelos: não fixe um nome — o VideoFX **descobre dinamicamente** o que está disponível:
- **Gemini:** lista os modelos disponíveis na sua chave (`v1beta/models`) e tenta os flash mais novos
- **OpenRouter:** tenta o modelo padrão e, se a chave estourar limite, cai para os modelos **gratuitos reais** do dia (via `/models`, preço zero)
- **HuggingFace:** exige créditos do Inference Providers ou plano PRO — sem isso, o provedor falha rápido e a cadeia segue
- Prompts de roteiro incluem guardas anti-alucinação: só fatos verificáveis, sem inventar números/datas precisos

## Voz por IA — ElevenLabs

Com `ELEVENLABS_API_KEY` no ambiente, a narração usa ElevenLabs `multilingual v2`
(pt-BR nativo, vozes rachel/drew/bella/gabriel/michele). Sem a chave, usa Piper
pt-BR (open source, gratuito).

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
videofx/llm.py     roteiro IA em cadeia: Gemini → OpenRouter → HuggingFace
videofx/tts.py     voz em cadeia: ElevenLabs → Piper pt-BR (voz auto-baixada)
videofx/images.py  imagens em cadeia: Pollinations → AI Horde → Pixabay → procedural
videofx/ytclips.py trechos de YouTube (yt-dlp) recortados e convertidos p/ 9:16
videofx/music.py   música procedural (chords + reverb)
videofx/effects.py partículas com glow e varredura de brilho (frames numpy)
videofx/render.py  montagem ffmpeg (zoompan, xfade, drawtext, blends, amix)
demo_config.json   exemplo com roteiro automático
demo_universo.json exemplo completo (cenas manuais + imagens IA)
```

## Licenças

- Fonte DejaVu Sans Bold: licença Bitstream/DejaVu (permissiva, incluída em `assets/fonts/`)
- Voz pt-BR faber: modelo open source do projeto Piper/rhasspy
