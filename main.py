"""Punto de entrada: ``python main.py --help``."""
import sys

from dotenv import load_dotenv

load_dotenv()                                   # lee .env (ANTHROPIC_API_KEY, LLM_PROVIDER, ...)

from visualization.cli import main              # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
