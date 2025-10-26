# PollToMVR

> [!Warning]
> Under Heavy Development 🚧

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/PollToMVR_icon.png" width="128px">

[PollToMVR](https://github.com/vanous/PollToMVR) - a tool to perform network
discovery via ArtNet - ArtPoll and save found devices in an
[MVR](https://gdtf-share.com/) (My Virtual Rig) scene file.

## Features

- Uses  [pymvr](https://pypi.org/project/pymvr/) to write fixtures to MVR files
- Provides Graphical [Terminal User Interface](https://textual.textualize.io/)
- Uses ArtPoll based device network discovery to create an MVR file with list of devices discovered on the network

## FAQ

### What is this

A tool to quickly create an MVR file based on network scan.

### What this is not

This is not a general tool to create MVR files. 

### How do i use PollToMVR?

Read the [Quick Start](#quick-start), see [Screenshots](#screenshots) and
[Recording](#recording), for further documentation, check out
[Features](#features).

## Instalation

Binary releases for Linux, macOS and Windows are available from the
[releases](https://github.com/vanous/PollToMVR/releases). For other
operating systems and for development, use the instructions below.

### What is MVR?

The [My Virtual Rig file format is an open standard](https://gdtf-share.com/)
which allows programs to share data and geometry of a scene for the
entertainment industry. A scene is a set of parametric objects such as
fixtures, trusses, video screens, and other objects that are used in the
entertainment industry. See [documentation and further
details](https://www.gdtf.eu/mvr/prologue/introduction/) on [GDTF
Hub](https://gdtf.eu/).

## Quick Start

- Start the PollToMVR
- Select the desired network interface
- Run Discovery
- Use `Save Devices` to store the result as an MVR file

## Features

- ### Network Discovery
    - Create a list of devices found on the local network. MVR file with
      these devices is created
    - Import the discovered devices directly, or from the created file


## Requirements for usage via source code

Install `uv` on your system. `uv` will manage python and dependencies
installation and will also run the application.

- [uv](https://docs.astral.sh/uv/)

## Source Code Installation

Clone the [repository](https://github.com/vanous/PollToMVR/) or [download
it](https://github.com/vanous/PollToMVR/archive/refs/heads/master.zip) and uzip.

## Run PollToMVR

Inside the downloaded/unzipped repository, run:

```bash
uv run run.py
```

## Running on Android in Termux

With a small amount of effort, it is possible to run PollToMVR on Android:

- Install Termux
- Install uv, python, wget:

```sh
pkg install uv python3 wget
```

- Download and unzip PollToMVR:

```sh
wget https://github.com/vanous/PollToMVR/archive/refs/heads/master.zip
unzip master.zip
cd uptime-kume-mvr-master
```

- You will need to edit the pyproject.toml and change python to 3.11, then you
  can run it:

```sh
uv run run.py
```

## Development

```
uv run textual console
```

```
uv run textual run --dev run.py
```

## Packaging

Initial pyinstaller setup

```
uv run pyinstaller packaging.spec
```

@software{pymvr2025,
  title        = {pyMVR: Python Library for My Virtual Rig},
  author       = {{OpenStage}},
  year         = {2025},
  version      = {1.0.3},
  url          = {https://github.com/open-stage/python-mvr}
}
```
