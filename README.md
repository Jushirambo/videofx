# VideoFX — gerador rápido de vídeos (estilo MoneyPrinter)

Cria vídeos curtos verticais (Reels/TikTok/Shorts) a partir de um tema ou roteiro:
narração por TTS neural em português, imagens de fundo, legendas sincronizadas,
música de fundo e efeito Ken Burns — tudo empacotado com ffmpeg.

## Pipeline

```
config JSON ──> roteiro (cenas)
                 ├─> TTS Piper (voz pt-BR) ─> duração de cada cena
                 ├─> imagens (image_urls / IA gratuita / fundo procedural)
                 ├─> música procedural (numpy)
                 └─> ffmpeg: Ken Burns + legendas + título + mix de áudio
```

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
    "title": "5 FATOS DO UNIVERSO",                // opcional: título (2,6s iniciais)
    "aspect": "9:16",                              // 9:16, 16:9 ou 1:1
    "voice": "voices/pt_BR-faber-medium.onnx",     // voz Piper
    "music_mood": "calm",                          // calm | energetic
    "music_volume": 0.16,
    "subtitle_size": 64,
    "subtitle_max_chars": 26,                      // quebra de legenda
    "scene_padding": 0.7,
    "min_scene_duration": 2.5,
    "allow_ai_images": true,                       // tenta IA gratuita por cena
    "image_urls": ["https://.../img1.jpg", ...]    // opcional: imagens prontas por cena
    "output_name": "demo_universo.mp4"
}
```

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
videofx/tts.py     Piper TTS pt-BR (voz auto-baixada)
videofx/images.py  imagens: locais, URLs, IA ou procedural
videofx/music.py   música procedural (chords + reverb)
videofx/render.py  montagem ffmpeg (zoompan, drawtext, concat, amix)
demo_config.json   exemplo com roteiro automático
demo_universo.json exemplo completo (cenas manuais + imagens IA)
```

## Licenças

- Fonte DejaVu Sans Bold: licença Bitstream/DejaVu (permissiva, incluída em `assets/fonts/`)
- Voz pt-BR faber: modelo open source do projeto Piper/rhasspy
