# Quickstart

`owpm` is a simple python package manager, like `poetry` or `pipenv`.

## Installing

```bash
pip3 install owpm
```

## Using

Initiate a new owpm project in the current directory:

```bash
owpm init
```

Add some packages:

```bash
owpm add [packages] # example: `owpm add click requests flask`
```

Start a virtual enviroment:

```bash
owpm run
```

If you cloned a repository with owpm enabled, simply run `owpm run` to start a virtual enviroment. You can also insert commands with `owpm run [args]` (e.g. `owpm run sleep 20`)!

## Something broke?

If you have changed some packages but owpm has not noticed when creating a new venv, you can do `--force` when using `owpm build` or `owpm run` to forcibly rebuild the package.

If there is still an issue, you may purge all existing virtual enviroments and cache by running simply `owpm clean`.
