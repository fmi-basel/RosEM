#Copyright 2021 Georg Kempf, Friedrich Miescher Institute for Biomedical Research
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.
import os
import re
from subprocess import Popen, PIPE
import rosem.utils as utils
import json
import logging

logger = logging.getLogger("RosEM")

def get_fsc(model):
    with open(model, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if re.search("REMARK\s*1\s*FSC", line):
                groups = re.match(".*\[mask=(.*)\]\((.*):(.*)\)\s*=\s*(\d+.\d+).*", line)
                fsc_mask = groups.group(1)
                fsc_resolution_low = groups.group(2)
                fsc_resolution_high = groups.group(3)
                fsc = groups.group(4)
        return fsc, fsc_resolution_low, fsc_resolution_high, fsc_mask

def get_fsc_test(model):
    fsc = 0.0
    with open(model, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if re.search("REMARK\s*1\s*FSC", line):
                try:
                    fsc = re.match(".*\)\s*=\s*.*\/\s+(\d+.\d+).*", line).group(1)
                except:
                    pass
        return fsc

def _get_validation_results(file):
    with open(file, 'r') as f:
        lines = f.readlines()
    m = re.match(".*_w(\d+).*", file)
    weight = m.group(1)
    stats_section = False
    for line in lines:
        if re.search("Molprobity validation", line):
            stats_section = True
        elif stats_section:
            #print(line)
            if re.search("\s+Bond\s+", line):
                bond_rmsd = line.split()[2]
            elif re.search("Angle", line):
                angle_rmsd = line.split()[2]
            elif re.search("Planarity", line):
                planarity_rmsd = line.split()[2]
            elif re.search("Dihedral", line):
                dihedral_rmsd = line.split()[2]
            elif re.search("Min Nonbonded Distance", line):
                min_distance = line.split()[4]
            elif re.search("All-atom Clashscore", line):
                clashscore = line.split()[3]
            elif re.search("\s*\s{2}Outliers\s+", line):
                ramas = line.split()[2]
            elif re.search("Rotamer Outliers", line):
                rotamers = line.split()[3]
            elif re.search("Cbeta Deviations", line):
                cbeta = line.split()[3]
            elif re.search("Cis-proline", line):
                cis_proline = line.split()[2]
            elif re.search("Cis-general", line):
                cis_general = line.split()[2]
            elif re.search("Twisted Proline", line):
                twisted_proline = line.split()[3]
            elif re.search("Twisted General\s+:", line):
                twisted_general = line.split()[3]
            # elif re.search("CC_mask", line):
            #     cc_mask = line.split()[2]
            # elif re.search("CC_volume", line):
            #     cc_volume = line.split()[1]
            # elif re.search("CC_peaks", line):
            #     cc_peaks = line.split()[2]
            # elif re.search("CC_box", line):
            #     cc_box = line.split()[2]

    if stats_section is False:
        logger.debug("Error reading file.")
    else:
        stats = {
            'weight': weight,
            'bonds': bond_rmsd,
            'angles': angle_rmsd,
            'planarity': planarity_rmsd,
            'dihedral': dihedral_rmsd,
            'min_distance': min_distance,
            'clashscore': clashscore,
            'ramas': ramas,
            'rotamers': rotamers,
            'cbeta': cbeta,
            'cis_proline': cis_proline,
            'cis_general': cis_general,
            'twisted_proline': cis_proline,
            'twisted_general': twisted_general,

            # 'cc_mask': cc_mask,
            # 'cc_volume': cc_volume,
            # 'cc_peaks': cc_peaks,
            # 'cc_box': cc_box,
        }
        return stats

def run_validation(model, exec_path, stage='post-ref'):
    cmd = [exec_path,
           model,
           #map,
           #'resolution={}'.format(resolution),
           #'output.file_name=phenix_validation_{}_{}'.format(utils.get_filename(model), stage)
           ]
    logger.debug(cmd)
    validation_log = 'phenix_validation_{}_{}.log'.format(utils.get_filename(model), stage)
    with open(validation_log, 'w') as f:
        p = Popen(' '.join(cmd), shell=True, stdin=PIPE, stdout=f)
        p.communicate()
    if os.path.exists(validation_log):
        stats = _get_validation_results(validation_log)
        fsc, fsc_resolution_low, fsc_resolution_high, fsc_mask =  get_fsc(model)
        fsc_test = get_fsc_test(model)
        stats['fsc_resolution'] = f"{fsc_resolution_high}-{fsc_resolution_low}"
        stats['fsc_mask'] = fsc_mask
        stats['fsc'] = fsc
        stats['fsc_test'] = fsc_test
        return stats
    else:
        logger.debug("No validation output found.")
