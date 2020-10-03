"""Contains errors thay may be faced when operating owpm and documentation for
each"""

class OwpmFileDoesNotExist(Exception):
    """Attempted to load a TOML-formatted `.owpm` file which does not exist"""

    pass

class InvalidOwpmFile(Exception):
    """The contents of a TOML-formatted `.owpm` file where invalid"""

    pass

class OwpmFileOpenError(Exception):
    """Could not read from a TOML-formatted `.owpm` file due to IO erorrs with
    operating system. This is primarily caused by insufficiant permissions"""

    pass

class OwpmFileNoVersion(Exception):
    """A given TOML-formatted `.owpm` file didn't have a `version` key which is
    required by owpm"""

    pass
