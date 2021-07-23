# RosEM - Pipeline and GUI for real-space refinement using rosetta and phenix

## Introduction

The GUI and command-line apps should provide easy access to the rosetta cryoem refinement workflow by Frank DiMaio and co.

At the moment only the fastrelax protocol based on this tutorial (https://faculty.washington.edu/dimaio/files/rosetta_density_tutorial_aug18_1.pdf) is implemented.


## Installation (Anaconda) ***recommended***

Install rosetta and phenix from

https://www.rosettacommons.org/software/license-and-download

https://phenix-online.org/download/


```
cd /some/directory/
git clone https://github.com/fmi-basel/RosEM.git
conda env create --file RosEM/rosem-conda.yml
conda activate rosem-conda
cd RosEM-main
python3 setup.py install
# GUI
rosemgui.py
# Commandline app
relax.py
```

Make sure rosetta and phenix executables are in the PATH. If not you need to specify them manually in the GUI settings or use respective flags in the command line app.

Tested on Linux Ubuntu 18.x and MacOS BigSur

## Installation (Virtualenv)

Dependencies
Qt5

```
(git clone https://github.com/fmi-basel/RosEM.git)
cd RosEM
python3 -m venv rosem-env
source rosem-env/bin/activate
pip install -r RosEM/requirements.txt
python3 setup.py install
```
## Usage

GUI Application
```
rosemgui.py
```

![image](https://user-images.githubusercontent.com/29370094/125800628-f74b92e7-4e3e-4be0-8b4d-c2d17d294266.png)

Command line
```
relax.py --help
```


