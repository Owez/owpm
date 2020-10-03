"""Reads TOML-formatted `.owpm` files into a clean OwpmFile class"""

import toml
import .exceptions
from pathlib import Path

def _toml_from_path(path: Path) -> dict:
    """Gets dict data from Path or raises appropriate exceptions"""

    if not path.exists():
        raise exceptions.OwpmFileDoesNotExist()
    
    try:
        toml_raw = open(path, "r")
    except:
        raise exceptions.OwpmOpenError()

    try:
        return toml.load(toml_raw)
    except:
        raise exceptions.InvalidOwpmFile()

class OwpmFile:
    """A clean representation of a TOML-formatted `.owpm` file"""

    def __init__(self, owpm_path: Path):
        """Creates a new OwpmFile from given Path or raises appropriate exceptions"""

        toml_file = _toml_from_path(path)

        if "desc" in toml_file:
            self.desc = toml_file.desc
        else:
            self.desc = "No description given"
        
        if "version" in toml_file:
            self.version = version
        else:
            raise exceptions.OwpmFileNoVersion()