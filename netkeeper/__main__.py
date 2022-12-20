

def main() -> None:
    """Entrypoint to the ``celery`` umbrella command."""
    from netkeeper.bin.netkeeper import main as _main  # pylint: disable=import-outside-toplevel
    _main()


if __name__ == '__main__':  # pragma: no cover
    main()
