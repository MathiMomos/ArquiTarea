from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    print("Proyecto: sistemas aislados de ventas y RRHH")
    print(f"Root: {root}")
    print("Revisa README.md para comandos de inicializacion, demo e integracion.")


if __name__ == "__main__":
    main()
