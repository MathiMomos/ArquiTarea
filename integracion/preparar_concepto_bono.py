try:
    from . import aplicar_bonos as backend
except ImportError:
    import aplicar_bonos as backend


def main() -> None:
    with backend.connect_database(backend.RRHH_DB) as connection:
        backend.register_bonus_concept(connection)
        connection.commit()

    print(f"Concepto {backend.BONUS_CONCEPT_CODE} disponible en {backend.RRHH_DB}")


if __name__ == "__main__":
    main()
