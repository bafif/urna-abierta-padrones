import sys

# Absolute, so that a packaged program can also use this file as its entry script.
from urna_padrones.lector import main

if __name__ == "__main__":
    sys.exit(main())
