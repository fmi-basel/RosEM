# RosEM - Pipeline and GUI for real-space refinement using rosetta and phenix

## Introduction

The GUI and command-line apps provide easy access to the rosetta cryoem refinement protocol by Frank DiMaio and co. The pipeline automates testing of different parameters, use of reference/starting model restraints (generation with phenix) and selections.

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
cd RosEM
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
cd /some/folder
git clone https://github.com/fmi-basel/RosEM.git
python3 -m venv rosem-env
source rosem-env/bin/activate
pip install --upgrade pip
pip install -r RosEM/requirements.txt
cd RosEM
python3 setup.py install
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
relax.py --help
```

Minimum input:
```
relax.py map.mrc model.pdb -r 3.0
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
* `submit_script` - If queue submission was used from the GUI, this file contains the submission commands
