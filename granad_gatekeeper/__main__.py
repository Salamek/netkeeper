

def main():
    """Entrypoint to the ``celery`` umbrella command."""
    from granad_gatekeeper.bin.granad_gatekeeper import main as _main
    _main()


if __name__ == '__main__':  # pragma: no cover
    main()