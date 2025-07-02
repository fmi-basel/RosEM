# RosEM - Pipeline and GUI for cryoEM model refinement using rosetta and phenix

## Introduction

The GUI and command-line apps provide easy access to the rosetta cryo-EM refinement protocol by Frank DiMaio et al. The pipeline automates testing of different density weights, use of reference/starting model restraints and selections.

At the moment only the FastRelax protocol based on this tutorial (https://faculty.washington.edu/dimaio/files/rosetta_density_tutorial_aug18_1.pdf) is implemented.


## Installation

Install rosetta and phenix from

https://www.rosettacommons.org/software/license-and-download

https://phenix-online.org/download/

Compatibility was tested against phenix v1.21.2 and rosetta v3.14.

### Installation (conda) ***recommended***

```
cd /some/directory/
git clone https://github.com/fmi-basel/RosEM.git
conda env create rosem-conda python=3.10
conda activate rosem-conda
cd RosEM
python3 -m pip install .
# GUI
rosemgui
# Commandline app
rosemcl
```

Make sure rosetta and phenix executables are in the PATH. If not you need to specify them manually in the GUI settings or use respective flags in the command line app.

Tested on Linux Ubuntu 18.x and MacOS BigSur

### Installation (Virtualenv)

Dependencies
Python>=3.10
Qt5

```
cd /some/folder
git clone https://github.com/fmi-basel/RosEM.git
python3 -m venv rosem-env
source rosem-env/bin/activate
pip install --upgrade pip
cd RosEM
python3 -m pip install .

```
## Usage

GUI Application
```
rosemgui.py
```

When launching the GUI for the first time, you  will be prompted to create a project. Choose a folder where job output should be saved.

When the main GUI has started, hovering over input fields will show context help.

Minimum input requirement is:
* A model file [.pdb]
* A map file [.mrc]
* Effective resolution

![image](https://user-images.githubusercontent.com/29370094/125800628-f74b92e7-4e3e-4be0-8b4d-c2d17d294266.png)

Command line
```
mkdir some_jobname
cd some_jobname
rosemcl --help
```

Minimum input:
```
rosemcl map.mrc model.pdb -r 3.0
```

By default the pipeline will generate 5 models and select the best one based on FSC correlation.

Expected output:

```
<JOBID>_<JOBNAME>/
    best_model_w<weight>.pdb
    (run.sh)
    job_w<weight>
    (validation)
    <JOBID>_<JOBNAME>.log
    (submit_script)
```

* `best_model_w<weight>.pdb` - The best model for a specified density weight based on FSC
* `run.sh` - The command used by GUI to run the pipeline
* `job_w<weight>` - Folder containing rosetta_scripts instructions (*.xml), individual models (*.pdb), rosetta command line scripts (*.sh), and rosetta logfiles (*.pdb)
* `validation` - If validation was requested, the folder contains output from molprobity
* `<JOBID>_<JOBNAME>.log` - Logfile from the pipeline

## Licenses

RosEM is licensed under the Apache License, Version 2.0.

Icons are from the GTK framework, licensed under [GPL](https://gitlab.gnome.org/GNOME/gtk/-/blob/main/COPYING).

Third-party software and libraries may be governed by separate terms and conditions or license provisions. Your use of the third-party software, libraries or code is subject to any such terms and you should check that you can comply with any applicable restrictions or terms and conditions before use.

## Acknowledgments

The density-guided FastRelax and B-factor refinement protocols are adapted from a [tutorial](https://faculty.washington.edu/dimaio/files/rosetta_density_tutorial_aug18_1.pdf) by Frank DiMaio et al. 

## Citations

### Relevant citations for the adapted protocols
[Wang et al., 2016: Automated structure refinement of macromolecular assemblies from cryo-EM maps using Rosetta](https://doi.org/10.7554/eLife.17219)
