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
import pkg_resources
import datetime
import sys
import os
import re
import logging
import json
import socket
import rosem.rosemcl as relax
import sqlalchemy.orm.exc
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QTableWidget
import traceback
from shutil import copyfile, rmtree
import configparser
logger = logging.getLogger('RosEM')
#logger.setLevel(logging.DEBUG)

wildcard = "PDB (*.pdb)|*.pdb|" \
           "All files (*.*)|*.*"

ctrl_type_dict = {'dsb': QtWidgets.QDoubleSpinBox,
                  'sbo': QtWidgets.QSpinBox,
                  'lei': QtWidgets.QLineEdit,
                  'tbl': QtWidgets.QTableWidget,
                  'cmb': QtWidgets.QComboBox,
                  'pte': QtWidgets.QPlainTextEdit,
                  'chk': QtWidgets.QCheckBox}

install_path = os.path.dirname(os.path.realpath(sys.argv[0]))


class Variable:
    """Basic model for GUI controls and DB tables"""

    def __init__(self, var_name=None,
                 type=None,
                 db=True,
                 ctrl_type=None,
                 db_primary_key=False,
                 db_foreign_key=None,
                 db_relationship=None,
                 db_backref=None,
                 cmb_dict=None):
        self.var_name = var_name
        self.value = None
        self.type = type
        self.ctrl_type = ctrl_type
        self.ctrl = None
        self.db = db
        self.db_relationship = db_relationship
        self.db_backref = db_backref
        self.db_foreign_key = db_foreign_key
        self.db_primary_key = db_primary_key
        self.cmb_dict = cmb_dict
        self.selected_item = None

    def set_ctrl_type(self):
        try:
            self.ctrl_type = self.ctrl.__class__.__name__
        except Exception:
            logger.warning("Cannot set control {}".format(self.ctrl.__class__.__name__), exc_info=True)

    def set_value(self, value):
        self.value = value

    def set_control(self, result_obj, result_var):
        if self.ctrl_type == 'dsb':
            self.ctrl.setValue(float(result_obj))
        elif self.ctrl_type == 'lei':
            self.ctrl.setText(str(result_obj))
        elif self.ctrl_type == 'pte':
            self.ctrl.setPlainText(str(result_obj))
        elif self.ctrl_type == 'sbo':
            self.ctrl.setValue(int(result_obj))
        elif self.ctrl_type == 'cmb':
            for k, v in self.cmb_dict.items():
                if result_obj == v:
                    index = self.ctrl.findText(str(k), QtCore.Qt.MatchFixedString)
                    if index >= 0:
                        self.ctrl.setCurrentIndex(index)
        elif self.ctrl_type == 'chk':
            self.ctrl.setChecked(bool(result_obj))
        else:
            logger.error("Control type {} not found for control {}!".format(self.ctrl_type, result_var))

    def is_set(self):
        if not self.value is None:
            return True
        else:
            return False

    def update_from_self(self):
        if not self.value is None and not self.ctrl is None:
            self.set_control(self.value, self.var_name)



    def update_from_db(self, db_result):
        """ Set/update variable values from DB """
        logger.debug("Update from DB")
        if not db_result is None and not db_result == []:
            for result_var in vars(db_result):
                #logger.debug("DB var: {}\nClass var: {}".format(result_var, self.var_name))
                if result_var == self.var_name:
                    result_obj = getattr(db_result, result_var)
                    self.value = result_obj
                    logger.debug("Variable name: {}\nValue: {}".format(result_var, result_obj))
                    if not self.ctrl is None:
                        if not result_obj in ['tbl', None]:
                            self.set_control(result_obj, result_var)
        else:
            logger.warning("DB result empty. Nothing to update.")

    def update_from_gui(self):
        """ Set/update attribute values (self.value) from GUI controls """
        if not self.ctrl is None:
            if self.ctrl_type in ['sbo', 'dsb']:
                    self.value = self.ctrl.value()
            elif self.ctrl_type == 'lei':
                self.value = self.ctrl.text()
            elif self.ctrl_type == 'pte':
                self.value = self.ctrl.toPlainText()
            elif self.ctrl_type == 'chk':
                self.value = self.ctrl.isChecked()
            elif self.ctrl_type == 'cmb':  # and not self.selected_item is None:
                self.value = self.ctrl.currentText()
            #if self.value == "":
            #    self.value = None
        else:
            logger.debug(f"ctrl of {self.var_name} is not bound.")

    def reset_ctrl(self):
        """ Clear variable values and GUI controls """
        logger.debug("Resetting GUI controls ")
        if not self.ctrl is None:
            logger.debug(f"resetting {self.var_name}")
            if not self.ctrl_type in ['chk', 'tbl']:
                self.ctrl.clear()
                self.value = None

            elif self.ctrl_type == 'chk':  # and not self.selected_item is None:
                self.ctrl.setChecked(False)
                self.value = False

            elif self.ctrl_type == 'tbl':
                while self.ctrl.rowCount() > 0:
                    self.ctrl.removeRow(0);
        else:
            logger.debug(f"ctrl of {self.var_name} is not bound.")


class File(Variable):
    """Model for files loaded as parameters"""
    def __init__(self, var_name=None, type=None, db=True, ctrl_type=None, db_primary_key=False, db_foreign_key=None,
                 file_ext=None, unique=False, file_type=None):
        super().__init__(var_name, type, db, ctrl_type, db_primary_key, db_foreign_key)
        self.file_ext = file_ext
        self.unique = unique
        self.file_type = file_type

    def is_unique(self):
        """Check if file is set to unique"""
        if self.unique:
            return True
        else:
            return False


class TblCtrlJobs(Variable):
    """GUI list control which shows jobs for project"""
    def __init__(self, var_name=None, type=None, db=True, ctrl_type=None, db_primary_key=False, db_foreign_key=None):
        super().__init__(var_name, type, db, ctrl_type, db_primary_key, db_foreign_key)
        self.selected_item = None


class TblCtrlReport(Variable):
    """GUI list control which shows validation report"""
    def __init__(self, var_name=None, type=None, db=True, ctrl_type=None, db_primary_key=False, db_foreign_key=None):
        super().__init__(var_name, type, db, ctrl_type, db_primary_key, db_foreign_key)
        self.report_dict = {}

    def register(self, parameter):
        self.report_dict[parameter.var_name] = parameter


class TblCtrlFiles(Variable):
    """GUI list control which shows loaded files"""
    def __init__(self, var_name=None, type=None, db=True, ctrl_type=None, db_primary_key=False, db_foreign_key=None):
        super().__init__(var_name, type, db, ctrl_type, db_primary_key, db_foreign_key)
        self.file_dict = {}
        self.selected_item = None

    def register(self, file):
        """Pre-register possible file types in dictionary"""

        self.file_dict[file.var_name] = file


    def get_file_type(self, path):
        """Returns the file type based on the file extension in the path"""
        file_type = None
        ext = os.path.splitext(os.path.basename(path))[1]
        
        for key, value in self.file_dict.items():
            # If Model already set and another pdb file is given assign this as reference model
            if ext == '.pdb':
                if  self.file_dict['model_file'].is_set() and self.file_dict['reference_model'].is_set():
                    logger.error("Cannot add more pdb files.")
                elif self.file_dict['model_file'].is_set() and not self.file_dict['reference_model'].is_set():
                    logger.debug("Model file found. Assigning reference model.")
                    file_type = 'Reference Model'
                else:
                    file_type = 'Model'
            elif ext == '.mrc':
                if self.file_dict['map_file'].is_set() and self.file_dict['test_map_file'].is_set():
                    logger.error("Cannot add more map files.")
                elif self.file_dict['map_file'].is_set() and not self.file_dict['test_map_file'].is_set():
                    logger.debug("Map file found. Assigning test map.")
                    file_type = 'Test Map'
                else:
                    file_type = 'Map'
            else:
                if ext == value.file_ext:
                    file_type = value.file_type
        if file_type is None:
            logger.error("No file type")
        else:
            return file_type

    def get_var_name(self, file_type):
        var_name = None
        for k, v in self.file_dict.items():
            if v.file_type == file_type:
                var_name = k
        return var_name

    def set_value(self, file_type=None, value=None, selected_item=None):
        """
        :param file_type:
        :param value: path of the file
        :param selected_item:
        :return:
        """
        var_name = self.get_var_name(file_type)
        if self.file_dict[var_name].is_set() and self.file_dict[var_name].is_unique():
            return False
        # Add File to control
        elif self.file_dict[var_name].is_set():
            stored_value = self.file_dict[var_name].value
            if not stored_value is None:
                new_value = "{},{}".format(stored_value, value)
            else:
                new_value = value
            self.file_dict[var_name].value = new_value
            return True
        else:
            self.file_dict[var_name].value = value
            return True

    def update_from_db(self, db_result):
        """Update file variables from stored contents in DB. Overrides function from super class."""
        if not db_result is None and not db_result == []:
            #Reset table
            while self.ctrl.rowCount() > 0:
                self.ctrl.removeRow(0);
            var_names = self.file_dict.keys()
            file_list = []
            for result_var in vars(db_result):
                if result_var in var_names:
                    result_obj = getattr(db_result, result_var)
                    if not result_obj is None:
                        # If several files are stored
                        items = result_obj.split(",")
                        logger.debug("File items")
                        logger.debug(items)
                        for item in items:
                            file_list.append((item, result_var))
                        self.file_dict[result_var].value = result_obj

            self.ctrl.setColumnCount(2)
            self.ctrl.setRowCount(len(file_list))
            for i, item in enumerate(file_list):
                self.ctrl.setItem(i, 0, QtWidgets.QTableWidgetItem(item[0]))
                self.ctrl.setItem(i, 1, QtWidgets.QTableWidgetItem(self.file_dict[item[1]].file_type))
        else:
            logger.warning("DB result was empty. Nothing to update.")

    def set_from_gui(self):
        pass

    def modify_type_from_gui(self, file_type):
        """Modify file type from the GUI"""
        new_file_type = file_type
        row = self.ctrl.currentRow()
        value = self.ctrl.item(row, 0).text()
        old_file_type = self.ctrl.item(row, 1).text()
        logger.debug(f"Value: {value} Old file type: {old_file_type}")
        if self.set_value(file_type=new_file_type, value=value):
            self.ctrl.setItem(row, 1, QtWidgets.QTableWidgetItem(new_file_type))
            #Set old file type to None
            var_name = self.get_var_name(old_file_type)
            logger.debug(f"Old file type var name: {var_name}")
            self.file_dict[var_name].value = None
            return True
        else:
            return False


        # index = self.ctrl.InsertItem(selected_item, value)

    def add_from_gui(self, paths=[]):
        """Add new files to the list control from GUI"""
        for path in paths:
            file_type = self.get_file_type(path)
            status = self.set_value(file_type=file_type, value=path)
            if status:
                rows = self.ctrl.rowCount()
                self.ctrl.insertRow(rows)
                self.ctrl.setItem(rows, 0, QtWidgets.QTableWidgetItem(path))
                self.ctrl.setItem(rows, 1, QtWidgets.QTableWidgetItem(file_type))


    def remove_from_gui(self, row):
        """Remove item from dict"""
        file_type = self.ctrl.item(row, 1).text()
        logger.debug(file_type)
        logger.debug(self.file_dict)
        var_name = self.get_var_name(file_type)
        logger.debug(var_name)

        if var_name in self.file_dict:
            logger.debug(f"Remove {var_name}")
            #Set value to None
            self.file_dict[var_name].value = None
        else:
            logger.debug(f"{var_name} not found in dict")
            logger.debug(self.file_dict)
        logger.debug(self.file_dict)

    def remove_all(self):
        for k, v in self.file_dict.items():
            self.file_dict[k].value = None


class GUIVariables:
    """ Functions shared by GUI associated variables. Inherited by """
    def set_controls(self, ui, db_table):
        logger.debug("Setting controls")
        for var in vars(self):
            logger.debug(var)
            
            obj = getattr(self, var)
            logger.debug(obj)
            if hasattr(obj, 'ctrl_type') and not obj.ctrl_type is None:
                logger.debug(f"{obj.ctrl_type}_{db_table}_{obj.var_name}")
                #if obj.ctrl is None:
                ctrl = ui.findChild(ctrl_type_dict[obj.ctrl_type],
                                      '{}_{}_{}'.format(obj.ctrl_type, db_table, obj.var_name))
                logger.debug(ctrl)
                if not ctrl is None:
                    obj.ctrl = ctrl
                    logger.debug(obj.ctrl)
                else:
                    logger.debug("ctrl not found in res")

    def delete_controls(self, var_obj):
        logger.debug("Deleting controls")
        for var in vars(self):
            logger.debug(var)

            obj = getattr(self, var)
            if hasattr(obj, 'var_name'):
                logger.debug(f"self object {obj.var_name}")
            for var_ in vars(var_obj):
                logger.debug(f"db object {var_}")
                if hasattr(obj, 'ctrl'):
                    if obj.var_name == var_:
                        logger.debug(f"Deleting {obj.var_name}")
                        obj.ctrl = None

    def update_from_self(self):
        for var in vars(self):
            obj = getattr(self, var)
            if hasattr(obj, 'ctrl') and hasattr(obj, 'value'):
                obj.update_from_self()

    # Read values from gui controls and update variables
    def update_from_gui(self):
        logger.debug("Update from GUI")
        for var in vars(self):
            logger.debug(f"Update {var}")
            obj = getattr(self, var)
            logger.debug(obj)
            if hasattr(obj, 'ctrl'):
                obj.update_from_gui()

    def reset_ctrls(self):
        logger.debug("Reset ctrls")
        for var in vars(self):
            obj = getattr(self, var)
            if hasattr(obj, 'ctrl'):
                obj.reset_ctrl()

    # Get values from DB for respective job and update gui controls
    def update_from_db(self, db_result, other=None):
        logger.debug("========>>> Update from DB")
        if not db_result is None and not db_result == []:
            for var in vars(self):
                obj = getattr(self, var)
                if hasattr(obj, 'ctrl'):
                    #Update only if var is in other
                    if not other is None:
                        logger.debug("Updating only variables in \"other\" object")
                        for var_ in vars(other):
                            logger.debug(f"params var {var}, other var {var_}")
                            if var_ == var:
                                obj.update_from_db(db_result)
                    else:
                        obj.update_from_db(db_result)
        else:
            logger.warning("DB result empty. Nothing to update.")

    def update_from_default(self, default_values):
        logger.debug("========>>> Update from Default")
        if not default_values is None and not default_values == []:
            for var in vars(self):
                obj = getattr(self, var)
                if hasattr(obj, 'ctrl'):
                    obj.update_from_db(default_values)
        else:
            logger.warning("Default values empty. Nothing to update.")

    def get_dict_run_job(self):
        job_dict = {}
        for var in vars(self):
            obj = getattr(self, var)
            if hasattr(obj, 'db') and (hasattr(obj, 'ctrl') or hasattr(obj, 'file_type')):
                if obj.value == '':
                    obj.value = None
                job_dict[obj.var_name] = obj.value
        return job_dict

    def get_dict_db_insert(self, foreign_obj=None):
        insert_dict = {}
        for var in vars(self):
            obj = getattr(self, var)
            if hasattr(obj, 'db'):
                if obj.db is True and obj.db_primary_key is False and obj.db_foreign_key is None and obj.db_relationship is None:
                    logger.debug(f"dict db insert var {var} value {obj.value}")
                    if obj.is_set():
                        insert_dict[obj.var_name] = obj.value
                elif not obj.db_relationship is None:
                    if not foreign_obj is None:
                        insert_dict[obj.var_name] = foreign_obj
        return [insert_dict]


class Validation(GUIVariables):
    def __init__(self):
        self.db = None
        self.db_table = 'validation'
        self.id = Variable('id', 'int', db_primary_key=True)
        self.job_id = Variable('job_id', 'int', db_foreign_key='job.id')
        self.reports = TblCtrlReport('report',
                                     None,
                                     db=False,
                                     ctrl_type='tbl')
        self.weight = Variable('weight', 'int')
        self.reports.register(self.weight)
        self.bonds = Variable('bonds', 'float')
        self.reports.register(self.bonds)
        self.angles = Variable('angles', 'float')
        self.reports.register(self.angles)
        self.planarity = Variable('planarity', 'float')
        self.reports.register(self.planarity)
        self.dihedral = Variable('dihedral', 'float')
        self.reports.register(self.dihedral)
        self.min_distance = Variable('min_distance', 'float')
        self.reports.register(self.min_distance)
        self.clashscore = Variable('clashscore', 'float')
        self.reports.register(self.clashscore)
        self.ramas = Variable('ramas', 'float')
        self.reports.register(self.ramas)
        self.rotamers = Variable('rotamers', 'float')
        self.reports.register(self.rotamers)
        self.cbeta = Variable('cbeta', 'float')
        self.reports.register(self.cbeta)
        self.cis_proline = Variable('cis_proline', 'float')
        self.reports.register(self.cis_proline)
        self.cis_general = Variable('cis_general', 'float')
        self.reports.register(self.cis_general)
        self.twisted_proline = Variable('twisted_proline', 'float')
        self.reports.register(self.twisted_proline)
        self.twisted_general = Variable('twisted_general', 'float')
        self.reports.register(self.twisted_general)
        self.fsc_resolution = Variable('fsc_resolution', 'str')
        self.reports.register(self.fsc_resolution)
        self.fsc_mask = Variable('fsc_mask', 'float')
        self.reports.register(self.fsc_mask)
        self.fsc = Variable('fsc', 'float')
        self.reports.register(self.fsc)
        self.fsc_test = Variable('fsc_test', 'float')
        self.reports.register(self.fsc_test)
        # self.cc_mask = Variable('cc_mask', 'float')
        # self.reports.register(self.cc_mask)
        # self.cc_volume = Variable('cc_volume', 'float')
        # self.reports.register(self.cc_volume)
        # self.cc_peaks = Variable('cc_peaks', 'float')
        # self.reports.register(self.cc_peaks)
        # self.cc_box = Variable('cc_box', 'float')
        # self.reports.register(self.cc_box)

    def set_db(self, db):
        self.db = db

    def get_report_by_job_id(self, job_id, sess):
        
        
        result = sess.query(self.db.Validation).filter_by(job_id=job_id).all()
        return result

    def check_exists(self, job_id, sess):
        result = sess.query(self.db.Validation).filter_by(job_id=job_id).all()
        
        if result == [] or result == None:
            return False
        else:
            return True

    def get_dict_db_insert(self, validation_report_path):
        results_list = []
        if os.path.exists(validation_report_path):
            with open(validation_report_path, 'r') as f:
                results_list = json.load(f)
                
        else:
            for var in vars(self):
                
                obj = getattr(self, var)
                if hasattr(obj, 'db'):
                    if obj.db is True and obj.db_primary_key is False and obj.db_foreign_key is None:
                        for row in results_list:
                            row[obj.var_name] = 0.0
        
        return results_list

    def generate_db_object(self, data):
        if isinstance(data, list):
            return [self.db.Validation(**row) for row in data]
        else:
            return [self.db.Validation(**data)]

    def init_gui(self, gui_params, sess=None):
        if not gui_params['job_id'] is None:
            
            
            # Get Validation report for job_id
            reports = self.get_report_by_job_id(gui_params['job_id'], sess)
            
            
            if not isinstance(reports, list):
                reports = [reports]
            # Create rows


            self.reports.reset_ctrl()
            self.reports.ctrl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.reports.ctrl.setColumnCount(len(reports))
            self.reports.ctrl.setRowCount(len(list(self.reports.report_dict.keys())))
            #self.reports.ctrl.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
            #self.reports.ctrl.setSelectionMode(QtWidgets.QTableView.SingleSelection)
            self.reports.ctrl.setHorizontalHeaderLabels(tuple(['Best model' for x in range(len(reports))]))
            row_labels = tuple(self.reports.report_dict.keys())
            self.reports.ctrl.setVerticalHeaderLabels(row_labels)

            logger.debug("Row Labels")
            logger.debug(row_labels)

            #self.reports.ctrl.setColumnWidth(0, 400)
            #self.reports.ctrl.setColumnWidth(1, 200)

            
            # grid.InsertRows(pos=0, numRows=len(self.reports.report_dict.keys()))
            
            #Set row labels

            # Create Columns
            logger.debug("Report:")
            logger.debug(reports)
            if not reports is None and not reports == []:
                #Get columns
                for i, row in enumerate(reports):
                    #Get rows
                    for o, item in enumerate(self.reports.report_dict.keys()):

                        for var in vars(row):
                            #Check if db variable is a report variable
                            if item == var:
                                var_obj = getattr(row, var)
                                logger.debug(f"Row {o} Column {i} Value {var_obj}")
                                self.reports.ctrl.setItem(o, i, QtWidgets.QTableWidgetItem(str(var_obj)))

        return gui_params


class FastRelaxParams(GUIVariables):
    def __init__(self):
        self.db = None
        self.db_table = 'fastrelaxparams'
        self.id = Variable('id', 'int', db_primary_key=True)
        self.job_id = Variable('job_id', 'int', db_foreign_key='job.id')
        #self.job = Variable('job', None, db_relationship='Job')
        self.name = Variable('name', 'str')
        self.resolution = Variable('resolution', 'int', ctrl_type='dsb')
        self.weight = Variable('weight', 'int', ctrl_type='lei')
        self.num_models = Variable('num_models', 'int', ctrl_type='sbo')
        self.num_cycles = Variable('num_cycles', 'int', ctrl_type='sbo')
        self.nproc = Variable('nproc', 'int', ctrl_type='sbo')
        self.selection = Variable('selection', 'str', ctrl_type='pte')
        self.validation = Variable('validation', 'bool', ctrl_type='chk')
        self.bfactor = Variable('bfactor', 'bool', ctrl_type='chk')
        self.fastrelax = Variable('fastrelax', 'bool', ctrl_type='chk')
        self.norepack = Variable('norepack', 'bool', ctrl_type='chk')
        self.dihedral_cst_weight = Variable('dihedral_cst_weight', 'float', ctrl_type='dsb')
        self.distance_cst_weight = Variable('distance_cst_weight', 'float', ctrl_type='dsb')
        self.bond_cst_weight = Variable('bond_cst_weight', 'float', ctrl_type='dsb')
        self.angle_cst_weight = Variable('angle_cst_weight', 'float', ctrl_type='dsb')
        self.ramachandran_cst_weight = Variable('ramachandran_cst_weight', 'float', ctrl_type='dsb')
        self.sc_weights = Variable('sc_weights', 'str', ctrl_type='pte')
        self.space_dict = {0: 'Cartesian',
                           1: 'Torsional'}
        self.space = Variable('space', 'int', ctrl_type='cmb', cmb_dict=self.space_dict)
        self.self_restraints = Variable('self_restraints', 'bool', ctrl_type='chk')
        self.files = TblCtrlFiles('files',
                                  None,
                                  db=False,
                                  ctrl_type='tbl')
        self.model_file = File(var_name='model_file',
                               type='str',
                               file_ext='.pdb',
                               unique=True,
                               file_type='Model',
                               ctrl_type=None)
        self.files.register(self.model_file)
        self.map_file = File(var_name='map_file',
                             type='str',
                             file_ext='.mrc',
                             unique=True,
                             file_type='Map',
                             ctrl_type=None)
        self.files.register(self.map_file)
        self.test_map_file = File(var_name='test_map_file',
                                  type='str',
                                  file_ext='.mrc',
                                  unique=True,
                                  file_type='Test Map',
                                  ctrl_type=None)
        self.files.register(self.test_map_file)
        self.symm_file = File(var_name='symm_file',
                              type='str',
                              file_ext='.symm',
                              unique=False,
                              file_type='Symmetry Definition',
                              ctrl_type=None)
        self.files.register(self.symm_file)
        self.params_files = File(var_name='params_files',
                                type='str',
                                file_ext='.params',
                                unique=False,
                                file_type='Params',
                                ctrl_type=None)
        self.files.register(self.params_files)
        self.cst_file = File(var_name='cst_file',
                             type='str',
                             file_ext='.cst',
                             unique=False,
                             file_type='Constraints',
                             ctrl_type=None)
        self.files.register(self.cst_file)
        self.reference_model = File(var_name='reference_model',
                                    type='str',
                                    file_ext='.pdb',
                                    unique=True,
                                    file_type='Reference Model',
                                    ctrl_type=None)
        self.files.register(self.reference_model)
        self.name.set_value("FastRelaxDens")

    def set_db(self, db):
        self.db = db

    def db_insert_params(self, sess, data=None):
        assert isinstance(data, list)
        rows = [self.db.Fastrelaxparams(**row) for row in data]
        for row in rows:
            sess.merge(row)
        sess.commit()

    def generate_db_object(self, data=None):
        assert isinstance(data, list)
        return [self.db.Fastrelaxparams(**row) for row in data]

    def get_params_by_job_id(self, job_id, sess):
        logger.debug(f"get result for job id {job_id}")
        result = sess.query(self.db.Fastrelaxparams).filter_by(job_id=job_id).one()
        return result

    def get_name_by_job_id(self, job_id, sess):
        result = sess.query(self.db.Fastrelaxparams.name).filter_by(job_id=job_id).one()
        logger.debug(result[0])
        logger.debug(result)
        return result[0]

    # Init GUI elements
    def init_gui(self, gui_params, sess=None):
        # Fill space combo and select first entry
        self.space.reset_ctrl()
        space_lst = self.space_dict.values()
        for item in space_lst:
            self.space.ctrl.addItem(item)
        self.space.ctrl.setCurrentIndex(0)

        # Fill file list control
        self.files.reset_ctrl()
        #Table not editable
        self.files.ctrl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.files.ctrl.setColumnCount(2)
        self.files.ctrl.verticalHeader().setVisible(False)
        #Select complete row
        self.files.ctrl.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.files.ctrl.setSelectionMode(QtWidgets.QTableView.SingleSelection)
        self.files.ctrl.setHorizontalHeaderLabels(('Path','Type'))
        self.files.ctrl.setColumnWidth(0, 400)
        self.files.ctrl.setColumnWidth(1, 200)

        # self.file_list.SetColumnWidth(0, 300)
        # self.file_list.SetColumnWidth(1, 200)
        return gui_params


class Project(GUIVariables):
    def __init__(self):
        self.db = None
        self.db_table = 'project'
        self.id = Variable('id', 'int', db_primary_key=True)
        self.jobs = Variable('jobs', None, db_relationship='Job')
        self.name = Variable('name', 'str', ctrl_type='lei')
        self.path = Variable('path', 'str', ctrl_type='lei')
        self.list = Variable('list', None, db=False, ctrl_type='cmb')

        self.active = Variable('active', 'bool', ctrl_type=None)

    def set_db(self, db):
        self.db = db

    def insert_project(self, data, sess):
        assert isinstance(data, list)
        rows = [self.db.Project(**row) for row in data]
        for row in rows:
            sess.merge(row)
        sess.commit()

    def check_if_exists(self, project_name, sess):
        exists = False
        result = self.get_projects(sess)
        for row in result:
            if project_name == row.name:
                exists = True
        return exists

    def delete_project(self, project_id, sess):
        sess.query(self.db.Project).filter(self.db.Project.id == project_id).delete()
        #Cascading delete not yet working
        job_ids = sess.query(self.db.Job.id).filter_by(project_id=project_id).all()
        sess.query(self.db.Job).filter(self.db.Job.job_project_id == project_id).delete()
        logger.debug("Job IDs to delete")
        logger.debug(job_ids)
        for job_id in job_ids:
            job_id = job_id[0]
            sess.query(self.db.Fastrelaxparams).filter(self.db.Fastrelaxparams.job_id == job_id).delete()
            sess.query(self.db.Validation).filter(self.db.Validation.job_id == job_id).delete()
        sess.commit()

    def is_empty(self, sess):
        if sess.query(self.db.Project).all() == []:
            return True
        else:
            return False

    def get_project_by_id(self, project_id, sess):
        return sess.query(self.db.Project).get(project_id)

    def get_active_project(self, sess):
        try:
            project_name, project_id = sess.query(self.db.Project.name, self.db.Project.id).filter_by(
                active=True).one()
        except sqlalchemy.orm.exc.NoResultFound:
            project_name, project_id = None, None
        return project_name, project_id

    def get_projects(self, sess):
        result = sess.query(self.db.Project).all()
        return result

    def update_project(self, project_id, data, sess,):
        assert isinstance(data, list)
        result = sess.query(self.db.Project).get(project_id)
        for k, v in data[0].items():
            setattr(result, k, v)
        sess.commit()

    def change_active_project(self, new_project, sess, new_active_id=None):
        """
        Change ative project in DB
        :param new_project:
        :return:
        """

        try:
            last_active = sess.query(self.db.Project).filter_by(active=True).one()
            last_active_id = int(last_active.id)
        except:
            last_active_id = -1

        all = sess.query(self.db.Project).all()

        if new_active_id is None:
            new_active = sess.query(self.db.Project).filter_by(name=new_project).one()
            new_active_id = int(new_active.id)
        
        if not last_active_id == new_active_id:
            # if not last_active_id == -1:
            #    last_active.active = False
            for row in all:
                row.active = False
            new_active.active = True
        sess.commit()

        #result = sess.query(self.db.Project).all()

        return new_active_id

    def get_path_by_project_id(self, project_id, sess):
        result = sess.query(self.db.Project).filter_by(id=project_id).first()
        return result.path

    def init_gui(self, gui_params, sess=None):
        logger.debug("=== Init Projects ===")
        projects = self.get_projects(sess)
        # if projects == []:
        #     base_project = [{'name': 'base', 'path': os.getcwd(), 'active': True}]
        #     self.insert_project(base_project)
        #     projects = self.get_projects()
        # logger.debug("Projects")
        # logger.debug(projects)
        if not projects == []:
            self.list.reset_ctrl()
            for item in projects:
                if self.list.ctrl.findText(item.name) == -1:
                    self.list.ctrl.addItem(item.name)
                else:
                    logger.warning("{} not found.".format(item.name))
            name, id = self.get_active_project(sess)
            logger.debug(f"Active project {name}")
            #Handle case when active project was deleted
            if not name is None:
                gui_params['project_path'] = self.get_path_by_project_id(id, sess)
                projects = self.get_projects(sess)
                # name = projects[0].name
                # id = projects[0].id
                index = self.list.ctrl.findText(name, QtCore.Qt.MatchFixedString)
                logger.debug(f"currently selected project index {index}")
                if index >= 0:
                    self.list.ctrl.setCurrentIndex(index)
                gui_params['project_id'] = id
            return gui_params
        else:
            gui_params['project_id'] = None
            return gui_params
            logger.debug("No project found.")



class Job(GUIVariables):
    def __init__(self):
        self.db = None
        self.db_table = 'job'
        self.id = Variable('id', 'int', db_primary_key=True)
        self.project_id = Variable('project_id', 'int', db_foreign_key='project.id')
        self.fastrelaxparams = Variable('fastrelaxparams', None, db_relationship='Fastrelaxparams', db_backref="Job")
        self.validation = Variable('validation', None, db_relationship='Validation', db_backref="Job")
        # self.params = Variable('params', 'int', db_relationship='Params')
        # self.name = Variable('name', 'str')
        self.job_project_id = Variable('job_project_id', 'int', db=True)
        self.list = TblCtrlJobs('list', None, db=False, ctrl_type='tbl')
        self.timestamp = Variable('timestamp', 'str')
        self.log = Variable('log', 'str', db=False, ctrl_type='pte')
        self.log_file = Variable('log_file', 'str', db=True)
        self.status = Variable('status', 'str', db=True)
        self.pid = Variable('pid', 'str', db=True)
        self.host = Variable('host', 'str', db=True)
        self.path = Variable('path', 'str', db=True)

    def set_db(self, db):
        self.db = db

    def get_status(self, job_id, sess):
        result = sess.query(self.db.Job).get(job_id)
        return result.status

    def update_status(self, status, job_id, sess):
        result = sess.query(self.db.Job).get(job_id)
        result.status = status
        sess.commit()

    def get_job_project_id(self, job_id, project_id, sess):
        result = sess.query(self.db.Job).filter_by(id=job_id, project_id=project_id).first()
        if result is None:
            return None
        else:
            return result.job_project_id

    def get_max_job_project_id(self, project_id, sess):
        result = sess.query(self.db.Job).filter_by(project_id=project_id).order_by(self.db.Job.job_project_id.desc()).first()
        if result is None:
            return None
        else:
            return result.job_project_id


    def get_next_job_project_id(self, project_id, sess):
        max_id = self.get_max_job_project_id(project_id, sess)
        if max_id is None:
            logger.debug("No job_project_id found.")
            max_id = 0
        return max_id + 1

    def set_next_job_project_id(self, project_id, sess):
        job_project_id = self.get_next_job_project_id(project_id, sess)
        self.job_project_id.value = job_project_id
        logger.debug(f"job_project_id is {job_project_id}")

    def get_job_id_by_job_project_id(self, job_project_id, project_id, sess):
        result = sess.query(self.db.Job).filter_by(project_id=project_id, job_project_id=job_project_id).first()
        return result.id

    def get_pid(self, job_id, sess):
        result = sess.query(self.db.Job).get(job_id)
        return result.pid

    def get_host(self, job_id, sess):
        result = sess.query(self.db.Job).get(job_id)
        return result.host

    def update_pid(self, pid, job_id, sess):
        result = sess.query(self.db.Job).get(job_id)
        result.pid = pid
        sess.commit()

    # def convert_protocol(self, cmd_dict):
    #     conversion = {"FastRelax": "1",
    #                   "Backbone Minimization": "2",
    #                   "Allatom Minimization": "3",
    #                   "Automatic rebuilding": "4",
    #                   "Ramachandran-based rebuilding": "5",
    #                   "Only B-factor refinement": "6"}
    #     cmd_dict['protocol'] = conversion[cmd_dict['protocol']]

    def convert_space(self, cmd_dict):
        conversion = {"Cartesian": "cartesian",
                      "Torsional": "torsional"}
        cmd_dict['space'] = conversion[cmd_dict['space']]

    def prepare_cmd(self, job_params):
        cmd_dict = job_params.copy()
        #self.convert_protocol(cmd_dict)
        self.convert_space(cmd_dict)
        del cmd_dict['id']
        del cmd_dict['job_id']
        excluded_args = ['model_file', 'map_file', 'symm_file', 'cst_file', 'files']
        #put selection in parantheses
        for k, v in cmd_dict.items():
            if k == 'selection':
                if not v is None:
                    cmd_dict[k] = f"\"{v}\""
        cmd_dict = {k: v for k, v in cmd_dict.items() if not v is None}
        logger.debug(cmd_dict)
        job_args = ['--{} {}'.format(k, v) if not k in excluded_args else v for k, v in cmd_dict.items()]
        logger.debug(job_args)
        job_args = [re.sub(r'\sTrue', '', x) for x in job_args if not x is None if not re.search(r'\sFalse', x)]
        cmd = ['rosemcl.py'] + job_args
        logger.debug("Job command\n{}".format(cmd))
        return cmd

    def insert_validation(self, _validation, job_params, sess):
        if not _validation.check_exists(job_params['job_id'], sess):
            job_obj = self.get_job_by_id(job_params['job_id'], sess)
            
            
            validation_report_path = os.path.join(job_params['job_path'],
                                                  "validation",
                                                  "validation.json")
            if os.path.exists(validation_report_path):
                validation_dict_db = _validation.get_dict_db_insert(validation_report_path)
                
                validation_obj = _validation.generate_db_object(validation_dict_db)
                job_obj.validation_collection.extend(validation_obj)
                
                sess.commit()
                

                return True

                # except:
                #    os.chdir(basedir)
                # finally:
                #    os.chdir(basedir)
            else:
                return False
        else:
            return True

    def get_exit_code_from_log(self, log_file):
        exit_code = None
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            for line in lines:
                pattern = re.compile(r'Job finished with exit code (\d+)')
                if re.search(pattern, line):
                    exit_code = int(re.search(pattern, line).group(1))
        except Exception:
            logger.debug(traceback.print_exc())
            pass


        return exit_code

    def db_insert_job(self, sess=None, data=None):
        assert isinstance(data, list)
        rows = [self.db.Job(**row) for row in data]
        for row in rows:
            sess.merge(row)
        sess.commit()

    def delete_job(self, job_id, sess):
        sess.query(self.db.Job).filter_by(id=job_id).delete()
        #Cascading delete not yet working
        sess.query(self.db.Fastrelaxparams).filter_by(job_id=job_id).delete()
        sess.query(self.db.Validation).filter_by(job_id=job_id).delete()
        sess.commit()

    def delete_job_files(self, job_id, path, sess):
        self.delete_job(job_id, sess)
        rmtree(path)


    def set_project_id(self, project_id):
        self.project_id.value = project_id

    def set_timestamp(self):
        self.timestamp.value = datetime.datetime.now()

    def set_host(self):
        self.host.value = socket.gethostname()

    def get_jobs_by_project_id(self, project_id, sess):
        result = sess.query(self.db.Job).filter_by(project_id=project_id)
        return result

    def generate_db_object(self, data=None):
        assert isinstance(data, list)
        return [self.db.Job(**row) for row in data]

    def get_job_by_id(self, job_id, sess):
        result = sess.query(self.db.Job).filter_by(id=job_id).one()
        return result

    def read_log(self, log_file):
        lines = []
        with open(log_file, 'r') as log:
            lines = log.readlines()
        return lines

    def update_log(self, gui_params):
        if 'log_file' in gui_params:
            logger.debug(f"Log file: {gui_params['log_file']}")
            if os.path.exists(gui_params['log_file']):
                self.log.reset_ctrl()
                lines = self.read_log(gui_params['log_file'])
                for line in lines:
                    self.log.ctrl.appendPlainText(line)

    def get_path_by_project_id(self, project_id, sess):
        result = sess.query(self.db.Project.path).filter_by(id=project_id).first()
        return result[0]

    def get_job_dir(self, job_project_id, job_name):
        job_dir = f"{job_project_id}_{job_name}"
        return job_dir

    def get_job_path(self, project_path, job_dir):
        job_path = os.path.join(project_path, job_dir)
        return job_path

    def get_log_file(self, project_path, job_project_id, job_name):
        job_dir = self.get_job_dir(job_project_id, job_name)
        job_path = self.get_job_path(project_path, job_dir)
        log_file = os.path.join(job_path, f"{job_project_id}_{job_name}.log")
        return log_file

    def set_log_file(self, log_file):
        self.log_file.value = log_file

    def set_status(self, status):
        self.status.value = status

    def check_pid(self, pid):
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False

    def reconnect_jobs(self, sess):
    #     max_runtime = 60 * 60 * 24 * 2
        jobs_running = []
        result = sess.query(self.db.Job).filter_by(status="running")
        for job in result:
            jobs_running.append({'job_id': job.id, 'job_path': job.path, 'log_file': job.log_file, 'pid': job.pid})
    #
    #     for job in result:
    #         if not job.log_file is None:
    #             if not os.path.exists(job.log_file):
    #                 self.update_status("error", job.id)
    #             else:
    #                 exit_code = self.get_exit_code_from_log(job.log_file)
    #                 # runtime = (datetime.datetime.now() - job.timestamp).total_seconds()
    #                 if exit_code is None:
    #                     if self.check_pid(job.pid):
    #                         jobs_running.append({'id': job.id, 'log_file': job.log_file})
    #                     else:
    #                         self.update_status("error", job.id)
    #
    #                 elif int(exit_code) == 1:
    #                     self.update_status("error", job.id)
    #                 elif int(exit_code) == 0:
    #                     self.update_status("finished", job.id)
    #         else:
    #             try:
    #                 self.update_status("error", job.id)
    #             except:
    #                 pass
    #
        return jobs_running

    def init_gui(self, gui_params, sess=None):
        logger.debug("=== Init Job list ===")
        # Clear Lists
        self.list.reset_ctrl()
        self.log.reset_ctrl()
        logger.debug("reset end")
        # Fill job list
        project_id = gui_params['project_id']
        self.list.ctrl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.list.ctrl.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.list.ctrl.setColumnCount(3)
        self.list.ctrl.verticalHeader().setVisible(False)
        self.list.ctrl.setHorizontalHeaderLabels(('ID', 'Name', 'Status'))
        self.list.ctrl.setColumnWidth(0, 50)
        if not project_id is None:
            gui_params['project_path'] = self.get_path_by_project_id(project_id, sess)
            jobs = self.get_jobs_by_project_id(project_id, sess)
            
            column = 0
            # ids = []
            # for row in range(self.list.ctrl.rowCount()):
            #     _item = self.list.ctrl.item(row, 0)
            #     if _item:
            #         ids.append(int(self.list.ctrl.item(row, 0).text()))
            
            for job in jobs:
                status = self.get_status(job.id, sess)
                if status is None:
                    status = "unknown"
                

                rows = self.list.ctrl.rowCount()
                self.list.ctrl.insertRow(rows)
                logger.debug(f"Insert job project id {job.job_project_id}")
                self.list.ctrl.setItem(rows , 0, QtWidgets.QTableWidgetItem(str(job.job_project_id)))
                self.list.ctrl.setItem(rows , 1, QtWidgets.QTableWidgetItem("FastRelaxDens"))
                self.list.ctrl.setItem(rows , 2, QtWidgets.QTableWidgetItem(status))
        # Fill log
        #self.update_log(gui_params)
        return gui_params


class Settings(GUIVariables):
    def __init__(self):
        self.db = None
        self.db_table = 'settings'
        self.id = Variable('id', 'int', db_primary_key=True)
        self.rosetta_path = Variable('rosetta_path', 'str', ctrl_type='lei')
        self.phenix_path = Variable('phenix_path', 'str', ctrl_type='lei')
        self.global_config = Variable('global_config', 'bool', ctrl_type='chk')

    def set_db(self, db):
        self.db = db

    def init_gui(self, gui_params, sess):
        return gui_params

    def get_from_db(self, sess):
        result = sess.query(self.db.Settings).get(1)
        return result

    def update_path(self, path, program, sess):
        logger.debug("Update path")
        settings = sess.query(self.db.Settings).get(1)
        if program == 'phenix':
            settings.phenix_path = path
        elif program == 'rosetta':
            settings.rosetta_path = path
        sess.commit()

    def update_from_global_config(self, sess):
        if sess.query(self.db.Settings).get(1).global_config is True:
            logger.debug("update from global config")
            config_file = pkg_resources.resource_filename('rosem.config', 'global.conf')
            if os.path.exists(config_file):
                config = configparser.ConfigParser()
                config.read(config_file)
                for key in config['GLOBAL']:
                    for var in vars(self):
                        if key == var:
                            setattr(self, key, config['GLOBAL'][key])
            else:
                logger.error("Config file not found.")
        else:
            logger.debug("global config option not set.")

    def get_rosetta_path(self, sess):
        result = self.get_from_db(sess)
        return result.rosetta_path

    def get_phenix_path(self, sess):
        result = self.get_from_db(sess)
        return result.phenix_path

    def check_executables(self, sess):
        messages = []
        settings = self.get_from_db(sess)
        self.path = relax.ExecPath(logger)
        if not settings is None:
            if not settings.phenix_path == '':
                self.path.register('phenix', settings.phenix_path)
            else:
                self.path.register('phenix', None)
            if not settings.rosetta_path == '':
                self.path.register('rosetta', settings.rosetta_path)
            else:
                self.path.register('rosetta', None)
        else:
            self.path.register('phenix', None)
            self.path.register('rosetta', None)
        try:
            logger.debug("check phenix")
            self.path.set_exec('phenix', 'phenix.validation_cryoem')
            logger.debug("check phenix")
        except FileNotFoundError:
            messages.append("Phenix executables not found. Check path in settings!")
        try:
            self.path.set_exec('phenix', 'phenix.real_space_refine')
        except FileNotFoundError:
            messages.append("Phenix executables not found. Check path in settings!")
            pass
        except NotADirectoryError:
            messages.append("Phenix executables could not be set because the given path is not a directory.")
            pass
        except SystemExit:
            pass
        try:
            self.path.set_exec('rosetta', 'rosetta_scripts', 'python|mpi')
        except FileNotFoundError:
            messages.append("Rosetta executables not found. Check path in settings!")
            pass
        except NotADirectoryError:
            messages.append("Rosetta executables could not be set because the given path is not a directory.")
            pass
        except SystemExit:
            pass



        exec_dict = {}
        #result = {'exists': False, 'executable': False}


        results = {}
        if self.path.get('phenix') is None:
            messages.append("Path to phenix executables not set. Check in settings!")
        else:
            results['phenix_path'] = self.path.get('phenix')
            self.update_path(self.path.get('phenix'), 'phenix', sess)
        if self.path.get('rosetta') is None:
            messages.append("Path to rosetta executables not set. Check in settings!")
        else:
            results['rosetta_path'] = self.path.get('rosetta')
            self.update_path(self.path.get('rosetta'), 'rosetta', sess)

        #     else:
        #         results['rosetta_path'] = rosetta
        #     self.update_settings([results])
        #     settings = self.get_from_db()
        #
        # exec_dict['rosetta'] = settings.rosetta_path
        #
        # for exec_ in ['phenix.real_space_refine', 'phenix.validation_cryoem']:
        #     exec_dict[exec_] = (os.path.join(settings.phenix_path, exec_))
        #
        # for program, exec_ in exec_dict.items():
        #     if not os.path.isfile(exec_):
        #         #result['exists'] = True
        #         messages.append("{} not found. Check the phenix path in settings and that the executable exists!".format(exec_))
        #     elif not os.access(os.path.join(settings.phenix_path, exec_), os.X_OK):
        #             #result['executable'] = True
        #             messages.append("{} exists but is not executable. Check the file permissions!".format(exec_))
        return messages

    def add_blank_entry(self, sess):
        settings = self.get_from_db(sess)
        if settings is None:
            logger.debug("Adding frist entry to settings")
            self.db_insert_settings([{'rosetta_path': '',
                                     'phenix_path': '',
                                     'global_config': False}], sess)


    def db_insert_settings(self, data, sess):
        logger.debug("Insert settings into DB")
        logger.debug(data)
        assert isinstance(data, list)
        rows = [self.db.Settings(**row) for row in data]
        for row in rows:
            sess.merge(row)
        sess.commit()

    def update_settings(self, insert_dict, sess):
        logger.debug("Update settings")
        settings = self.get_from_db(sess)
        if settings is None:
            self.db_insert_settings(insert_dict, sess)
        else:
            for key, value in insert_dict[0].items():
                setattr(settings, key, value)
            sess.commit()

class DefaultValues:
    def __init__(self):
        self.weight = "35,50"
        self.num_models = "5"
        self.num_cycles = "5"
        self.nproc = "1"
        self.fastrelax = "True"
        self.space = "Cartesian"
        self.dihedral_cst_weight = "2.0"
        self.distance_cst_weight = "2.0"
        self.angle_cst_weight = "2.0"
        self.bond_cst_weight = "2.0"
        self.ramachandran_cst_weight = "1.0"
