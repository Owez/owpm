# Quickstart

`owpm` is a simple python package manager, like `poetry` or `pipenv`.

## Installing

```bash
pip3 install owpm
```

Or to build an executable on Linux,

```bash
./buildexe.sh # It will output ./build/owpm/
```

NOTE: If you are using this, never move owpm.exe outside of the `owpm/` folder.

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
