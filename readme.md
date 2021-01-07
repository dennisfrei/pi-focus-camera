# P(r)i(me) Focus Camera

Use your Raspberry Pi (RP) with the camera module as prime focus camera for your telescope.

%%%%%%%%%%%%%%% WIP %%%%%%%%%%%%%%%%%%%

% Work in Progress

% The repo does not yet works as expected

% or has not yet been set up completely

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%



How it works:

- RP + camera is mounted onto the focuser.
- Local hosted API on the RP via Python client application.
- Local hosted frontend on the RP with the ELM framework. The frontend contains a live stream of the camera, a capture button and the possibility to adjust camera settings.
- The RP is used as an access point. If you log in into the network you are able to reach the local hosted frontend and therefore to use the camera.

- - -
## Prerequisites

### Software

- Python 3.8^
- Node 12^

### Hardware
- Raspberry Pi (Tested with RP 4 Model B)
- Raspberry Pi Camera Module V1 or V2
- Camera Mount for your telescope (see `Camera Mount`)


## Instructions

### Install

```bash
git clone https://github.com/dennisfrei/pi-focus-camera.git
cd pi-focus-camera
cp .env.example .env
pip install -r requirements.txt
```

### Configuration


### Setup the RP

- Adjust energy settings
- Enable autostart (pm2)
- Setup access point


- - -

## Good To Know

### Camera Mount
You need an option to mount the camera to your telescope for sure, however, there are unlimited possibilities to do this.
If you ask Google for it you can find a solution which fits best for your needs.

As it was done at [1](#Sources), I also asked a friend to print [this](https://www.thingiverse.com/thing:1812708) mount for me.


### Power Supply
Use power-pack or accumulator for the RP.


### Glossary

- `RP`: Raspberry Pi


### Sources
I was inspired for this project by some excellent blog articles / repositories:

- [1] https://medium.com/swlh/astrophotography-with-the-raspberry-pi-camera-a-cheapskates-guide-to-solar-system-photography-fb0b82142f8d
- [2] http://astronomy.robpettengill.org/astroRPi.html
- [3] https://github.com/RemovedMoney326/Hubble-Pi/blob/master/Astrocam/AstroCam.py
