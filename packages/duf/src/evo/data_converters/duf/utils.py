from evo.data_converters.duf.common import DufWrapper


def is_duf(filepath: str) -> bool:
    """Returns `True` if the file appears to be a valid DUF file"""
    try:
        with DufWrapper(filepath, None) as instance:
            instance.LoadSettings()
    except Exception:
        return False
    else:
        return True
