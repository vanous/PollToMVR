# PollToMVR

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/PollToMVR_icon.png" width="128px">

[PollToMVR](https://github.com/vanous/PollToMVR) - a tool to perform device
discovery via ArtNet or RDM E1.20 and to save found devices in an
[MVR](https://gdtf-share.com/) (My Virtual Rig) scene file.

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/polltomvr_00.png">

## Overview

- Uses  [pymvr](https://pypi.org/project/pymvr/) to write fixtures to MVR files
- Provides Graphical [Terminal User Interface](https://textual.textualize.io/)
- Uses ArtPoll based device network discovery, can parse DMX Address and Universe from device description if present
- Uses RDM ANSI E1.20 via Robe RUNIT USB Interfaces for DMX line device discovery
- Uses the [GDTF Share](https://gdtf-share.com) Fixture Library for fixture definitions in MVR

## FAQ

### What is this

A tool to quickly create an MVR file based on ArtPoll or RDM scan.

### What this is not

This is not a general tool to create MVR files.

### How do i use PollToMVR?

Read the [Quick Start](#quick-start), see [Screenshots](#screenshots), for
further documentation, check out [Features](#features).

### Does it use ArtRDM?

No, it only uses ArtPoll and ArtPollReply. Some manufacturers put DMX
Address/Universe into `long_name`. If present and parsed, these values will
then be used in the MVR export.

### Can devices be discovered via RDM?

Yes, PollToMVR can use ANSI E1.20 for device discovery and to query the device
for Device Info and Device Model Description. Supported USB interfaces are the
Robe Lighting: `Universal Interface` and `RUNIT WTX` interfaces.

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
- Click Discover to run network discovery
- After discovery, press the "Add devices to MVR Layer", click Add
- Click `Save Devices` to store the result as an MVR file

This will create a bare-bone MVR file with device names and their IP addresses
(and Universes, DMX address, if also discovered). For more featured MVR: set
user login credential in the Config, download some GDTF files and after network
discovery, link the GDTFs to the discovered fixtures. After saving, the MVR
will also contain the full GDTF definitions

## Features

- ### Config
    - Network Discovery Timeout: how long for should be the waiting for
      ArtPollReply from devices
    - GDTF Share credentials: fill in username/password to be able to download
      GDTF files from GDTF Share, create a free account there if needed
- ### Main Screen
    - Shows a list of discovered devices
    - Shows the possibility to define a GDTF file for each device. This GDTF
      file will then be used for the created MVR file. To download the GDTF
      files, use the GDTF Files button on the main screen.
- ### Discover
    - Discover devices on the local network or on DMX line
    - Select a network interface on which the discovery will run
    - Select a USB based Runit interface for RDM based discovery
- ### Add Discovered Devices
    - Add the discovered devices to a selected MVR layer
    - Create a new named MVR Layer
- ### GDTF Files
    - Update GDTF Share data - download the latest list of available GDTF files
      from the GDTF Share
    - Filter the devices by name or by a manufacturer name
    - Filter the devices by creator: Official Manufacturer Files or User
      created files
    - Download the GDTF files

## Screenshots

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/polltomvr_00.png">

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/polltomvr_01.png">

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/polltomvr_02.png">

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/polltomvr_03.png">

<img src="https://raw.githubusercontent.com/vanous/PollToMVR/refs/heads/master/images/polltomvr_04.png">

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
cd PollToMVR-master
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

## Code formatting

All python code is to be formatted with ruff:

```
uv tool run ruff format
``

## Packaging

Initial pyinstaller setup

```
uv run pyinstaller packaging.spec
```

```bibtex
@software{pymvr2025,
  title        = {pyMVR: Python Library for My Virtual Rig},
  author       = {{OpenStage}},
  year         = {2025},
  version      = {1.0.4},
  url          = {https://github.com/open-stage/python-mvr}
}
```
