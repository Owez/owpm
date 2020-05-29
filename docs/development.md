# Development Notes

Welcome to the development documentation & notes section of owpm. This document will assist in developing inside of the owpm ecosystem with some general maintainability and structuring notes.

## Code style

For development, I write in a style similar to the `black` formatting module (which itself is an extension of PEP8) so any code produced should fit that. Unless you are using sphinx-compatible RST docstrings, make them in a format similar to the following:

```py
def testfunc():
    """This is a docstring, if this entire thing goes over a whole 80 or so
    characters, wrap it like this. Remember to not put a full-stop at the end
    of your last paragraph and try not to make it over 3 lines long"""

    pass
```

Commenting is also allowed but try to keep them to a minimum and only use them if you think you or someone else will get stuck trying to quickly read over, the overall explication is kept for the docstrings, which in turn used in the main sphinx docs.

## Maintainability notes

- Start to use different branches for a more stable use even when in prerelease (as it currently is).
- For breaking changes inside of the lockfile when developing, remember to bump the `OWPM_LOCKFILE_VERSION` constant so older versions of lockfiles don't work as a failsafe for old locks.
- As good maintainability practise, always use type hints and a default value for optional arguments where it applies. This helps a developer using the main api of owpm simplify code.
- Document *every* function, even if it is internal and won't show up on the main `sphinx` docs.
