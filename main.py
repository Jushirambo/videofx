import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from videofx.config import load_config
from videofx.render import render


def main():
    ap = argparse.ArgumentParser(description="VideoFX — gerador rápido de vídeos estilo MoneyPrinter")
    ap.add_argument("--config", "-c", required=True, help="arquivo JSON de configuração")
    ap.add_argument("--output", "-o", help="nome do arquivo final (ex.: meu_video.mp4)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.output:
        cfg["output_name"] = args.output
    path = render(cfg)
    print(path)


if __name__ == "__main__":
    main()
