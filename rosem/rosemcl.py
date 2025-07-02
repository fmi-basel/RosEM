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
from __future__ import absolute_import
import argparse
import xml.etree.ElementTree as ET
import os
from subprocess import Popen, PIPE
import pandas as pd
from rosem import utils, validation, convert_restraints, selection_parser
from rosem.selection_parser import ResidueSelection
import rosem.validation as validation
import logging
from multiprocessing import Pool
from shutil import copyfile
import sys
import re
import traceback
import signal
from contextlib import closing
from xml.dom import minidom
import json


logger = logging.getLogger("RosEM")

class ExecPath:
    def __init__(self, logger):
        self.path_dict = {}
        self.exec_path_dict = {}

    def register(self, program, path):
        self.path_dict[program] = path

    def get(self, program):
        return self.path_dict[program]

    def get_exec(self, exec_name):
        return self.exec_path_dict[exec_name]

    def find(self, program):
        found = False
        path = os.environ['PATH'].split(':')
        for p in path:
            logger.debug(p)
            if re.search('{}.*/bin'.format(program), p):
                self.path_dict[program] = p
                found = True
        return found

    def set_exec(self, program, exec_name, exclude=None):
        if self.get(program) is None:
            if not self.find(program):
                logger.error(
                    "{a} not found in the path. Add {a} binary directory to system path or specify with --{b}_path.".format(a=exec_name, b=program))
                raise SystemExit
        if not exclude is None:
            exec_ = [f for f in os.listdir(self.get(program)) if re.search(exec_name, f) and not re.search(exclude, f)]
        else:
            exec_ = [f for f in os.listdir(self.get(program)) if re.search(exec_name, f)]
        if len(exec_) > 0:
            exec_ = os.path.join(self.get(program), exec_[0])
            self.exec_path_dict[exec_name] = exec_
            if not os.access(exec_, os.X_OK):
                logger.error("Check if execute permission for {} is set.".format(self.get(program)))
                raise SystemExit
        else:
            logger.error("Could not find {} executable in {}!".format(exec_name, self.get(program)))
            raise SystemExit


class FastRelaxDensity:
    '''
    Pipeline for the rosetta fast_relax protocol using density scoring.
    '''
    def __init__(self,
                 map_file=None,
                 model_file=None,
                 cst_file=None,
                 symm_file=None,
                 params_files=[],
                 reference_model=None,
                 test_map=None,
                 cst_weight=None,
                 resolution=None,
                 weight=[],
                 space="cartesian",
                 fastrelax=True,
                 norepack=False,
                 constrain_side_chains=False,
                 exclude_dna=False,
                 self_restraints=False,
                 ramachandran=False,
                 bb_h=False,
                 native_coords=None,
                 num_models=1,
                 num_cycles=1,
                 bfactor=False,
                 nproc=1,
                 ranking_method='fsc',
                 selection=None,
                 validation=False,
                 logging_mode='standard',
                 log_file='rosetta_relax_density_pipeline.log',
                 dihedral_cst_weight=2.0,
                 distance_cst_weight=2.0,
                 bond_cst_weight=1.0,
                 angle_cst_weight=1.0,
                 ramachandran_cst_weight=0.5,
                 sc_weights=None,
                 phenix_path=None,
                 rosetta_path=None,
                 **kwargs):
        """

        """

        #####################
        # Define attributes #
        #####################

        #User defined
        if not map_file is None:
            self.map_file = os.path.abspath(map_file)
        else:
            self.map_file = None
        self.pdb_file = os.path.abspath(model_file)
        logger.debug("params fields before abspath")
        logger.debug(params_files)
        self.params_files = [os.path.abspath(x) for x in params_files]
        logger.debug("params after abspath")
        logger.debug(self.params_files)
        if not cst_file is None:
            self.cst_file = os.path.abspath(cst_file)
        else:
            self.cst_file = None
        if not reference_model is None:
            self.reference_model = os.path.abspath(reference_model)
        else:
            self.reference_model = None
        if not symm_file is None:
            self.symm_file = os.path.abspath(symm_file)
        else:
            self.symm_file = None
        if not test_map is None:
            self.test_map = os.path.abspath(test_map)
        else:
            self.test_map = None
        if not native_coords is None:
            self.native_coords = os.path.abspath(native_coords)
        else:
            self.native_coords = None
        self.cst_weight = cst_weight
        self.dihedral_cst_weight = dihedral_cst_weight
        self.distance_cst_weight = distance_cst_weight
        self.angle_cst_weight = angle_cst_weight
        self.bond_cst_weight = bond_cst_weight
        if not self.cst_weight is None:
            self.dihedral_cst_weight = self.cst_weight
            self.distance_cst_weight = self.distance_cst_weight
        self.resolution = resolution
        if not self.map_file is None:
            self.weights = weight.split(',')
        else:
            self.weights = ["nodens"]
        self.b_factor = bfactor
        self.constrain_side_chains = constrain_side_chains
        self.self_restraints = self_restraints
        self.num_models = num_models
        self.cartesian = False
        self.torsional = False
        self.bb_min = False
        self.allatom_min = False
        self.fastrelax = fastrelax
        self.norepack = norepack
        self.bond_weight = 2.0
        self.angle_weight = 2.0
        self.torsion_weight = 2.0

        self.ramachandran = ramachandran
        self.ramachandran_cst_weight = ramachandran_cst_weight
        if self.ramachandran:
            self.ramachandran_cst_weight = 2.0
        if not sc_weights is None and not sc_weights == "":
            self.sc_weights = sc_weights
        else:
            self.sc_weights = "R:0.76,K:0.76,E:0.76,D:0.76,M:0.76,C:0.81," \
                              "Q:0.81,H:0.81,N:0.81,T:0.81,S:0.81,Y:0.88," \
                              "W:0.88,A:0.88,F:0.88,P:0.88,I:0.88,L:0.88,V:0.88"
        self.space = space.lower()
        self.num_cycles = num_cycles
        self.exclude_dna = exclude_dna
        self.nproc = nproc
        self.bb_h = bb_h
        self.ranking_method = ranking_method
        self.logging_mode = logging_mode
        if not self.map_file is None:
            self.run_validation = validation
        else:
            self.run_validation = False
        self.selection_str = selection
        self._space_parser()
        #Static
        self.base_dir = os.getcwd()
        self.path = ExecPath(logger)
        self.path.register('phenix', phenix_path)
        self.path.register('rosetta', rosetta_path)
        self.path.set_exec('phenix', 'phenix.molprobity')
        self.path.set_exec('phenix', 'phenix.real_space_refine')
        self.path.set_exec('rosetta', 'rosetta_scripts', 'python|mpi|multistage')
        if not self.logging_mode == 'file':
            ch = logging.StreamHandler()
            logger.addHandler(ch)
        fh = logging.FileHandler(log_file)
        logger.addHandler(fh)

        self.run()

    def run(self):
        logger.info("*** Starting pipeline ***")
        self.pipeline()

    def print_variables(self):
        for var in vars(self):
            logger.debug("{}: {}".format(var, getattr(self, var)))

    def get_xml_filename(self, wt):
        return "job_w{}.xml".format(wt)

    def _get_res_low(self, resolution):
        return str(float(resolution) + 10.0)

    def _space_parser(self):
        if self.space == "cartesian":
            self.cartesian = True
        elif self.space == "torsional":
            self.torsional = True

    def _generate_xml(self, wt):
        '''
        Generates the input xml for rosetta_scripts based on variables.
        '''
        rosetta = ET.Element("ROSETTASCRIPTS")
        ###########
        #Scorefxns#
        ###########
        scorefxns = ET.SubElement(rosetta, "SCOREFXNS")

        if self.torsional:
            score_function = ET.SubElement(scorefxns, "ScoreFunction", name="dens", weights="beta")
        else:
            score_function = ET.SubElement(scorefxns, "ScoreFunction", name="dens", weights="beta_cart")
        if not self.symm_file is None:
            score_function.set("symmetric", "1")

        if not self.map_file is None:
            ET.SubElement(score_function, "Reweight", scoretype="elec_dens_fast", weight=str(wt))
            ET.SubElement(score_function, "Set",
                  scale_sc_dens_byres=self.sc_weights)
        else:
            score_function.set("name", "nodens")
        #Reweight constraints
        ET.SubElement(score_function, "Reweight", scoretype="atom_pair_constraint", weight=str(self.distance_cst_weight))
        ET.SubElement(score_function, "Reweight", scoretype="dihedral_constraint", weight=str(self.dihedral_cst_weight))
        ET.SubElement(score_function, "Reweight", scoretype="angle_constraint", weight=str(self.angle_cst_weight))

        #Reweight cartesian bonds and angles to get lower rmsd.
        ET.SubElement(score_function, "Reweight", scoretype="cart_bonded_length", weight=str(self.bond_weight))
        ET.SubElement(score_function, "Reweight", scoretype="cart_bonded_angle", weight=str(self.angle_weight))
        ET.SubElement(score_function, "Reweight", scoretype="cart_bonded_torsion", weight=str(self.torsion_weight))
        ET.SubElement(score_function, "Reweight", scoretype="rama_prepro", weight=str(self.ramachandran_cst_weight))

        ###################
        #Residue Selection#
        ###################

        if not self.selection_str is None:
            logger.debug("Running selection parser...")
            converted_selections_lst = ResidueSelection(self.selection_str).get_list()
            logger.debug("Parsed selection string:")
            logger.debug(converted_selections_lst)
            residue_selectors = ET.SubElement(rosetta, "RESIDUE_SELECTORS")
            move_map_factories = ET.SubElement(rosetta, "MOVE_MAP_FACTORIES")
            move_map_factory = ET.SubElement(move_map_factories,
                                             "MoveMapFactory", name="fr_mm_factory",
                                             bb = "0", chi = "0", jumps="0")
            types = [x[0] for x in converted_selections_lst]
            root_len = min([len(x[1]) for x in converted_selections_lst])
            for type, name, values, invert in converted_selections_lst:
                if type in ['And', 'Or']:
                    ET.SubElement(residue_selectors, type, name=name, selectors=values)
                    if len(name) == root_len:
                        ET.SubElement(move_map_factory, "Backbone", residue_selector=name)
                        ET.SubElement(move_map_factory, "Chi", residue_selector=name)
                else:
                    logger.debug(type)
                    if invert:
                        not_selector = ET.SubElement(residue_selectors, "Not", name=name)
                    if type == 'Chain':
                        if invert:
                            ET.SubElement(not_selector, type, chains=values)
                        else:
                            ET.SubElement(residue_selectors, type, name=name, chains=values)
                    elif type == 'Index':
                        if invert:
                            ET.SubElement(not_selector, type, resnums=values)
                        else:
                            ET.SubElement(residue_selectors, type, name=name, resnums=values)
                    elif type == 'ResidueName':
                        if invert:
                            ET.SubElement(not_selector, type, residue_names=values)
                        else:
                            ET.SubElement(residue_selectors, type, name=name, residue_names=values)
                if not 'And' in types and not 'Or' in types:
                    ET.SubElement(move_map_factory, "Backbone", residue_selector=name)
                    ET.SubElement(move_map_factory, "Chi", residue_selector=name)


        ########
        #MOVERS#
        ########
        movers = ET.SubElement(rosetta, "MOVERS")
        if not self.map_file is None:
            if not self.symm_file is None:
                setup_for_symmetry_scoring = ET.SubElement(movers,
                                                           "SetupForSymmetry",
                                                           name="setupsymm",
                                                           definition=self.symm_file)
            else:
                setup_for_density_scoring = ET.SubElement(movers,
                                                          "SetupForDensityScoring",
                                                          name="setupdens")
            load_density_map = ET.SubElement(movers,
                                             "LoadDensityMap",
                                             name="loaddens",
                                             mapfile=self.map_file)
            bfactor_fitting = ET.SubElement(movers,
                                            "BfactorFitting",
                                            name="fit_bs",
                                            max_iter="50",
                                            wt_adp="0.0005",
                                            init="1",
                                            exact="1")

        if self.fastrelax:
            fast_relax = ET.SubElement(movers,
                                       "FastRelax",
                                       name="relaxcart",
                                       bondangle="1",
                                       bondlength="1",
                                       ramp_down_constraints="0",
                                       scorefxn="dens",
                                       repeats=str(self.num_cycles),
                                       cartesian="1")
            if self.map_file is None:
                fast_relax.set("scorefxn", "nodens")
            #Load cst file if available.
            if not self.cst_file is None:
                fast_relax.set("cst_file", self.cst_file)
            if not self.selection_str is None:
                fast_relax.set("movemap_factory", "fr_mm_factory")
            # If torsional refinement requested set cartesian to 0.
            if self.torsional:
                fast_relax.set("cartesian", "0")
                fast_relax.set("bondangle", "0")
                fast_relax.set("bondlength", "0")


        protocols = ET.SubElement(rosetta, "PROTOCOLS")
        if not self.map_file is None:
            res_low = self._get_res_low(self.resolution)
            report_fsc = ET.SubElement(movers, "ReportFSC", name="report_fsc", res_low=res_low, res_high=self.resolution)
            if not self.symm_file is None:
                setupsymm = ET.SubElement(protocols, "Add", mover="setupsymm")
            else:
                setupdens = ET.SubElement(protocols, "Add", mover="setupdens")
            loaddens = ET.SubElement(protocols, "Add", mover="loaddens")
            if not self.test_map is None:
                report_fsc.set("testmap", self.test_map)
        if self.fastrelax:
            fast_relax = ET.SubElement(protocols, "Add", mover="relaxcart")
        if self.b_factor and not self.map_file is None:
            bfactor = ET.SubElement(protocols, "Add", mover="fit_bs")
        if not self.map_file is None:
            ET.SubElement(protocols, "Add", mover="report_fsc")
        tree = ET.ElementTree(rosetta)
        xmlstr = minidom.parseString(ET.tostring(rosetta)).toprettyxml(indent="   ")
        xml_file = self.get_xml_filename(wt)
        with open(xml_file, 'w') as xml:
            xml.write(xmlstr)
        logger.info(f"XML Input script for weight {wt} written to {xml_file}.")

    def _remove_hetatms(self, model):
        logger.debug("Temporarily removing HETATMS for {}".format(model))
        with open(model, 'r') as f:
            lines = f.readlines()
        lines_to_write = []
        for line in lines:
            if line.startswith("HETATM") or line.startswith("HET ") or line.startswith("LINK"):
                continue
            else:
                lines_to_write.append(line)
        if not lines_to_write == []:
            filename = '{}_cleaned.pdb'.format(utils.get_filename(model))
            with open(filename, 'w') as f:
                f.writelines(lines_to_write)
            return filename
        else:
            return None
                             
    def _get_geo_file(self):
        geo_file_old = "{}_cleaned_initial.geo".format(utils.get_filename(self.pdb_file))
        geo_file_new = "{}_cleaned_real_space_refined_000_initial.geo".format(utils.get_filename(self.pdb_file))
        if os.path.exists(geo_file_old):
            geo_file = geo_file_old
        elif os.path.exists(geo_file_new):
            geo_file = geo_file_new
        else:
            geo_file = None
        return geo_file

    def _generate_reference_model_restraints(self):
        geo_file = self._get_geo_file()
        if geo_file is None:
            logger.info("Generating reference model restraints.")
            pdb_file = self._remove_hetatms(self.pdb_file)
            reference_model = self._remove_hetatms(self.reference_model)
            if pdb_file is None or reference_model is None:
                logger.error("Failed to remove HETATMS from models.")
                raise SystemExit
            cmd = [self.path.get_exec('phenix.real_space_refine'),
                   pdb_file,
                   self.map_file,
                   "resolution={}".format(self.resolution),
                   "cycles=0",
                   "ignore_symmetry_conflicts=True",
                   "reference_model.enabled=True",
                   "reference_model.file={}".format(reference_model),
                   "run_validation=False"]
            cmd = ' '.join(cmd)
            logger.info(f"Command: {cmd}")
            try:
                with open('reference_model.log', 'w') as f:
                    p = Popen(cmd, shell=True, stdin=PIPE, stdout=f)
                    p.communicate()
            except (KeyboardInterrupt, Exception) as e:
                logger.error("Could not generate reference model restraints. Check reference_model.log for errors.", exc_info=True)
                traceback.print_exc()
                raise Exception
        
        else:
            logger.info("Reference restraints file already exists...skipping.")
        geo_file = self._get_geo_file()
        if not geo_file is None:
            convert_restraints.PhenixToRosetta(geo_file)
            reference_model_cst = "reference_model_restraints.cst"
            if os.path.exists(reference_model_cst):
                reference_model_cst = os.path.abspath(reference_model_cst)
            else:
                logger.error("Could not find restraints file.")
        else:
            logger.error("Could not find output from phenix. Check reference_model.log for errors.")
        if self.cst_file is None:
            self.cst_file = reference_model_cst
        else:
            with open(self.cst_file, 'r') as f1,\
                open(reference_model_cst, 'r') as f2,\
                open("restraints_combined.cst", "w") as out:
                combined = f1.read() + '\n' + f2.read()#
                out.write(combined)
            if os.path.exists("restraints_combined.cst"):
                self.cst_file = os.path.abspath("restraints_combined.cst")
            else:
                logger.error("Could not find combined restraints file.")

    def _get_job_dir(self, wt):
        return 'job_w{}'.format(wt)

    def _run_relax(self, mdl, wt):
        '''
        Build the rosetta_scripts command based on variables and start a subprocess in a dedicated directory.
        '''

        job_dir = self._get_job_dir(wt)
        os.chdir(job_dir)

        #Generate command script
        cmd_rosetta = [self.path.get_exec('rosetta_scripts'),
               "-in:file:s {}".format(self.pdb_file),
               "-in::use_truncated_termini true",
               "-parser:protocol {}/{}".format(os.getcwd(),
                                               self.get_xml_filename(wt)),
               "-beta",
               "-ignore_unrecognized_res",
               "-score_symm_complex false",
               "-default_max_cycles 200",
               "-ignore_zero_occupancy false",
               "-dna true",
               "-out::suffix _refined_{}".format(mdl),
               "-overwrite"]
        if not self.map_file is None:
            cmd_rosetta.extend(["-edensity::cryoem_scatterers",
                                "-crystal_refine",
                                "-edensity::mapreso {}".format(self.resolution)])
        if self.exclude_dna:
            cmd_rosetta.append("-dna_move false")
        else:
            cmd_rosetta.append("-dna_move true")
        if not self.params_files == []:
            cmd_rosetta.append("-chemical:exclude_patches SidechainConjugation -extra_res_fa")
            for params in self.params_files:
                cmd_rosetta.append(params)
        if self.norepack:
            cmd_rosetta.append("-prevent_repacking true")
        cmd_rosetta_file = " \\\n".join(cmd_rosetta)

        with open(f"job_w{wt}_{mdl}.sh", 'w') as f:
            f.write(cmd_rosetta_file)
        cmd_logger = '\n'.join(cmd_rosetta)
        cmd_rosetta = ' '.join(cmd_rosetta)
        logger.info(f"Starting task \"Density weight {wt}, Model {mdl}\".")
        logger.info(f"Command line:\n{cmd_logger}")
        try:
            with open('job_w{}_m{}.log'.format(wt, mdl), 'w') as f:
                p = Popen(cmd_rosetta, shell=True, stdout=f, stderr=f, preexec_fn=os.setsid)
                p.communicate()
                logger.info(f"Task finished: \"Density weight {wt}, Model {mdl}\".")
        except KeyboardInterrupt:
            logger.error("{} interrupted.".format(job_dir))
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            raise KeyboardInterrupt
        except Exception as e:
            logger.error(f"Could not start task \"Density weight {wt}, Model {mdl}\".", exc_info=True)
            traceback.print_exc()

        os.chdir(self.base_dir)

    def _select_best_model(self):
        """REMARK
        1
        FSC[mask = 4.45657](10:3) = 0.590966 / 0.591017"""
        wts = []
        best_model = None
        for dir in os.listdir(self.base_dir):
            if re.match('job_w\d+', dir):
                m = re.match('job_w(\d+)', dir)
                wt = m.group(1)
                if not wt in wts:
                    wts.append(wt)
                    logger.debug("Found job folder.")
        if not wts == []:
            for wt in wts:
                fsc_vals = []
                for dir in [x for x in os.listdir(self.base_dir) if os.path.isdir(x)]:
                    #Collect all folders with same weight
                    if dir.startswith("job_w{}".format(wt)):
                        if self.ranking_method == "fsc":
                            #There should be one model in each folder
                            models = [x for x in os.listdir(
                                os.path.join(self.base_dir, dir)) if x.endswith('.pdb')]
                            if not models == []:
                                fsc_vals = {}
                                for model in models:
                                    model_path = os.path.join(dir, models[0])
                                    fsc, _, _, _ = validation.get_fsc(model_path)
                                    if not model_path in fsc_vals:
                                        fsc_vals[model] = float(fsc)
                                best_model = max(fsc_vals, key=fsc_vals.get)
                            else:
                                logger.error("Could not find models in job dir. Check log files for possible errors.")
                                raise SystemExit
                                traceback.print_exc()
                                #raise Exception
                        elif self.ranking_method == "energy":
                            sc_file = [x for x in os.listdir(os.path.join(self.base_dir, dir)) if x.endswith('.sc')][0]
                            energy = self.validation.get_energy(os.path.join(dir, sc_file))
                            energy_vals.append({model: float(energy)})
                            best_model = max(energy_vals, key=energy_vals.get)
                        logger.debug("Best model {}".format(best_model))
                        try:
                            copyfile(os.path.join(dir, best_model), "best_model_w{}.pdb".format(wt))
                            traceback.print_exc()
                        except (KeyboardInterrupt, Exception) as e:
                            logger.error("Could not copy best model.")
                            logger.debug(e, exc_info=True)
                            traceback.print_exc()
                            raise SystemExit
            if best_model is None:
                logger.error("Collecting best model: No job directory found.")
                raise SystemExit
        else:
            logger.error("Collecting weight: No job directory found.")
            raise SystemExit


    def pipeline(self):
        '''
        Parallelize jobs to test different weights or generate multiple models.
        '''
        if not self.reference_model is None:
            self._generate_reference_model_restraints()
        if self.reference_model is None and self.self_restraints:
            self.reference_model = self.pdb_file
            self._generate_reference_model_restraints()
        relax_list = []
        logger.info("Preparing input for Rosetta.")
        for wt in self.weights:
            wt = wt.replace(" ","")
            #Create job directory.
            job_dir = self._get_job_dir(wt)
            if not os.path.exists(job_dir):
                os.mkdir(job_dir)
            else:
                logger.warning(f"Job directory for weight {wt} already exists. Overwriting content.")
            #Generate input xml
            os.chdir(job_dir)
            self._generate_xml(wt)
            os.chdir(self.base_dir)
            for i in range(int(self.num_models)):
                relax_list.append((i, wt))

        logger.debug("Input List")
        logger.debug(relax_list)

        with closing(Pool(self.nproc)) as pool:
            pool.starmap(self._run_relax, relax_list)
        try:
            self._select_best_model()
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception as e:
            raise SystemExit



        if self.run_validation:
            logger.info("Running validation with phenix.molprobity.")
            validation_list = []
            for file in os.listdir(self.base_dir):
                if file.startswith("best_model"):
                    validation_list.append((os.path.abspath(file),
                                          self.path.get_exec('phenix.molprobity')))
            if len(validation_list) > 0:
                try:
                    if not os.path.exists("validation"):
                        os.mkdir("validation")
                    os.chdir('validation')
                    with closing(Pool(self.nproc)) as pool:
                        result = pool.starmap_async(validation.run_validation, validation_list)
                    result = result.get()
                    logger.debug("Validation result:")
                    logger.debug(result)
                    if not result == [] and not result is None:
                        df = pd.DataFrame(result)
                        df.to_csv('validation_results.csv')
                        with open('validation.json', 'w') as f:
                            json.dump(result, f)
                    else:
                        logger.error("No validation results obtained.")
                    os.chdir(self.base_dir)
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except Exception as e:
                    logger.error(traceback.print_exc())
            else:
                logger.error("No models found for validation.")

def CheckExt(choices):
    class Action(argparse.Action):
        def __call__(self, parser, namespace, fname, option_string=None):
            ext = os.path.splitext(fname)[1][1:]
            if ext not in choices:
                option_string = '({})'.format(option_string) if option_string else ''
                parser.error("File doesn't end with one of {}{}".format(choices, option_string))
            else:
                setattr(namespace, self.dest, fname)
    return Action

def get_cli_args():
    '''
    Get user-defined arguments.
    '''
    parser = argparse.ArgumentParser(description="Pipeline for running rosetta fast_relax protocol with density"
                                                 "scoring.\n\n"
                                                 "Minimal requirements:\n"
                                                 "Rosetta and phenix must be in the PATH.\n"
                                                 "Map file (.mrc), PDB file (.pdb), resolution.")
    parser.add_argument('--resolution', '-r',
                        help='Effective resolution.')
    parser.add_argument('--test_map', '--test_map_file',
                        help='Map for validation (half map 2)',
                        action=CheckExt({'mrc'}))
    parser.add_argument('--params_files',
                        help="Comma separated list of params files (no spaces between commas).")
    parser.add_argument('--weight', '-w',
                        help='Density weight. To test multiple weights separate numbers with \',\' (w/o space). Default=35', default='35')
    parser.add_argument('--bfactor',
                        help='Run B-factor refinement after protocol',
                        action='store_true')
    parser.add_argument('--fastrelax',
                        help="Run the FastRelax protocol. If no other protocol is specified this is the default.",
                        action='store_true')
    parser.add_argument('--norepack',
                        help="Disable repacking of sidechains.",
                        default=False,
                        action='store_true')
    parser.add_argument('--space',
                        help='Choose refinement space "cartesian" or "torsional". Default = cartesian'
                             ' Cartesian = XYZ coordinates;'
                             ' Torsional = Refinement of dihedral angles (good to capture domain movements but can result in unfolding of structure)',
                        choices=['cartesian', 'torsional'],
                        default = 'cartesian')
    parser.add_argument('--num_models',
                        help='Number of models to generate. default=10',
                        default=10,
                        type=int)
    parser.add_argument('--ramachandran',
                        help='Restrain phi/psi angles.',
                        action='store_true')
    parser.add_argument('--self_restraints',
                        help='Generate torsional restraints with phenix.',
                        action="store_true")
    parser.add_argument('--dihedral_cst_weight',
                        help='Weight for restraints.',
                        type=float,
                        default=2.0)
    parser.add_argument('--distance_cst_weight',
                        help='Weight for restraints.',
                        type=float,
                        default=2.0)
    parser.add_argument('--bond_cst_weight',
                        help='Weight for restraints.',
                        type=float,
                        default=1.0)
    parser.add_argument('--angle_cst_weight',
                        help='Weight for restraints.',
                        type=float,
                        default=1.0)
    parser.add_argument('--ramachandran_cst_weight',
                        help='Weight for restraints.',
                        type=float,
                        default=0.5)
    parser.add_argument('--sc_weights',
                        help='Density weights for sidechains.',
                        type=str)
    parser.add_argument('--num_cycles',
                        help='Number of relax cycles. default=5',
                        default=5,
                        type=int)
    parser.add_argument('--exclude_dna',
                        help='Exclude DNA from refinement.',
                        action='store_true')
    parser.add_argument('--nproc', '-n',
                        help='Number of processors.',
                        default=1,
                        type=int)
    parser.add_argument('--selection',
                        help='Selection of residues and/or chains.')
    parser.add_argument('--reference_model',
                        help='Generates backbone and'
                             ' sidechain dihedral constraints'
                             ' from provided reference model using phenix.')
    parser.add_argument('--log_file', default="relax.log")
    parser.add_argument('--validation',
                        help="Run validation with molprobity",
                        action='store_true')
    parser.add_argument('--phenix_path',
                        help="Path to phenix bin directory.")
    parser.add_argument('--rosetta_path',
                        help="Path to rosetta_scripts executable.")
    parser.add_argument('--debug',
                        help="Enable debug mode.",
                        action='store_true')
    args, unknown = parser.parse_known_args()


    #Read in files.
    map_file, pdb_file, cst_file, params_files, symm_file = None, None, None, [], None
    for arg in unknown:
        if arg.endswith(".mrc"):
            map_file = arg
        elif arg.endswith(".pdb"):
            pdb_file = arg
        elif arg.endswith(".params"):
            args.params_files.append(arg)
        elif arg.endswith(".cst"):
            cst_file = arg
        elif arg.endswith(".symm"):
            symm_file = arg

    if not args.params_files is None:
        params_files_from_arg = args.params_files.split(',')
        for f in params_files_from_arg:
            params_files.append(f)
        logger.debug("Params files")
        logger.debug(params_files)
    args.params_files = params_files

    if map_file is None:
        logger.info("No map file supplied. This will run FastRelax without density scoring.")
    if not map_file is None and args.resolution is None:
        logger.error("Resolution required.")
        raise SystemExit
    if pdb_file is None:
        logger.error("No pdb file supplied.")
        raise SystemExit




    return args, unknown, map_file, pdb_file, cst_file, symm_file

def fastrelax_main(args, unknown, map_file, pdb_file, cst_file, symm_file):
    try:
        FastRelaxDensity(map_file,
                         pdb_file,
                         cst_file,
                         symm_file,
                         **vars(args))
        if not args.log_file is None:
            with open(args.log_file, 'a') as f:
                f.write("\nJob finished with exit code 0")
    except KeyboardInterrupt:
        logger.error("Job was aborted.")
        if not args.log_file is None:
            with open(args.log_file, 'a') as f:
                f.write("\nJob finished with exit code 2")
        raise SystemExit
    except SystemExit as e:
        logger.error("Job finished with critical exceptions.")
        if not args.log_file is None:
            with open(args.log_file, 'a') as f:
                f.write("\nJob finished with exit code 1")
        traceback.print_exc()
        raise SystemExit
    except Exception as e:
        logger.info("Job finished with non critical exceptions.")
        if not args.log_file is None:
            with open(args.log_file, 'a') as f:
                f.write("\nJob finished with exit code 1")
            traceback.print_exc()

def main():
    __spec__ = None
    args = get_cli_args()

    #logger.setLevel(logging.DEBUG)
    print(args)
    if args[0].debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    fastrelax_main(*args)


if __name__ == '__main__':
    main()
