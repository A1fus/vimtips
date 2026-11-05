# vimtip

A small, dependency-free CLI that shows one built-in Vim or Neovim command each day. It reads the installed command indexes, combines equivalent help tags, and keeps a local history so tips do not repeat until the catalog has been exhausted.

## Requirements

- Python 3
- Vim and Neovim, both with their help documentation installed

The catalog is built from each editor's `doc/index.txt`. It includes Normal, Visual, Insert, and Ex commands; options, concepts, and plugin commands are excluded. The available tips reflect the versions installed on your machine.

## Install

```sh
pipx install .
```

This installs the package in an isolated environment and exposes the `vimtip` command on your `PATH`. To build a wheel and source distribution, install the `build` package in your build environment, then run:

```sh
python3 -m build
```

The artifacts are written to `dist/`.

## Run

```sh
vimtip
```

Run the displayed `:help` command in Vim or Neovim to read more. Use `vimtip --reset` to start a fresh rotation. From a source checkout, `python3 vimtip.py` also works.

```sh
vimtip --reset
```

The state file is stored in `~/Library/Application Support/vimtip` on macOS, `%LOCALAPPDATA%/vimtip` on Windows, or `$XDG_STATE_HOME/vimtip` on Unix (defaulting to `~/.local/state/vimtip`). Repeated runs on the same local date show the same tip.

## Development Setup and Contributing

From a checkout, create and activate a virtual environment, then install the project in editable mode:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Before submitting a change, run the type check and tests:

```sh
pipx run pyright
python3 -m unittest discover -s tests
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.