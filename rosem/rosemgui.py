#!/usr/bin/env python3
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
from rosem import gui_threads
from rosem.gui_dialogs import message_dlg
from rosem.gui_dlg_settings import SettingsDlg
from rosem.gui_dlg_project import ProjectDlg
from rosem.gui_dlg_modtype import ModTypeDlg
from rosem.gui_dlg_about import AboutDlg
from rosem.gui_dlg_fastrelax_othersettings import FastRelaxOtherSettingsDlg
import signal
import socket
from subprocess import Popen
import pkg_resources
import sys
import os
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
import logging
from rosem.db_helper import DBHelper
from sqlalchemy import create_engine
import traceback
from rosem.gui_classes import Job, Settings, FastRelaxParams, Project, Validation, DefaultValues
import argparse


parser = argparse.ArgumentParser(description="Pipeline for running rosetta fast_relax protocol with density"
                                             "scoring.")
parser.add_argument('--debug', '-r',
                    help='Debug log.',
                    action='store_true')
args, unknown = parser.parse_known_args()

install_path = os.path.dirname(os.path.realpath(sys.argv[0]))
logger = logging.getLogger('RosEM')
formatter = logging.Formatter("[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s")
if not args.debug:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error("Error in GUI!:")
    logger.error("Traceback:\n", tb)

def main():
    shared_objects = [Project(),  FastRelaxParams(), Job(), Validation(), Settings()]
    db = DBHelper(shared_objects)
    upgrade_db()
    with db.session_scope() as sess:
        db.set_session(sess)
    for obj in shared_objects:
        obj.set_db(db)

    sys.excepthook = excepthook
    app = QtWidgets.QApplication(sys.argv)
    mainframe = MainFrame(shared_objects, DefaultValues(), db, sess, install_path)
    app.exec_()

def upgrade_db():
    logger.debug("Upgrading DB")
    db_path = os.path.join(os.path.expanduser("~"), '.rosem.db')
    engine = create_engine('sqlite:///{}'.format(db_path), connect_args={'check_same_thread': False})
    stmts = ['ALTER TABLE fastrelaxparams DROP COLUMN sc_weights',
            'ALTER TABLE fastrelaxparams ADD sc_weights VARCHAR DEFAULT \'R:0.76,K:0.76,E:0.76,'
             'D:0.76,M:0.76,C:0.81,Q:0.81,H:0.81,N:0.81,T:0.81,S:0.81,Y:0.88,'
             'W:0.88,A:0.88,F:0.88,P:0.88,I:0.88,L:0.88,V:0.88\'']
    with engine.connect() as conn:
        for stmt in stmts:
            try:
                rs = conn.execute(stmt)
            except Exception as e:
                logger.debug(e)
                #traceback.print_exc()

class NoProjectSelected(Exception):
    pass

class ModelRequired(Exception):
    pass

class MapRequired(Exception):
    pass

class DirectoryExists(Exception):
    pass

class DirectoryNotCreated(Exception):
    pass

class SelfRestraintsReferenceModelCombinationNotAllowed(Exception):
    pass

class ExecutablesNotFound(Exception):
    pass

class MainFrame(QtWidgets.QMainWindow):
    def __init__(self, shared_objects, default_values, db, sess, install_path):
        super(MainFrame, self).__init__() # Call the inherited classes __init__ method
        uic.loadUi(pkg_resources.resource_filename('rosem', 'gui.ui'), self) # Load the .ui file


        self.install_path = install_path
        self.prj, self.fastrelaxparams, self.job, self.validation, self.settings = self.shared_objects = shared_objects
        #self.fastrelaxparams = params_vars


        self.gui_params = {}
        self.files_selected_item = None
        self.gui_params['project_id'] = None
        self.gui_params['job_id'] = None
        self.gui_params['queue_job_id'] = None
        self.gui_params['job_project_id'] = None
        self.gui_params['job_name'] = "FastRelaxDens"
        self.gui_params['other_settings_changed'] = False
        self.default_values = default_values
        self.db = db
        self.sess = sess
        self.init_frame()
        #self.init_dialogs()

        self.init_menubar()
        self.init_toolbar()
        self.bind_event_handlers()
        self.init_gui()
        self.init_settings()
        self.check_project_exists()

       # self.check_executables()
        self.currentDirectory = os.getcwd()
        self.threads = []

        self.reconnect_jobs()
        self.show() # Show the GUI


    def init_frame(self):
        logger.debug("=== Initializing main frame ===")
        self.setWindowTitle("Rosetta cryoEM GUI")
        self.notebook = self.findChild(QtWidgets.QTabWidget, 'MainNotebook')
        self.notebook.setTabEnabled(2, False)
        self.panel = self.findChild(QtWidgets.QPushButton, 'InputPanel')
        #self.panel.SetScrollRate(20,20)
        self.log_panel = self.findChild(QtWidgets.QPushButton, 'LogPanel')
        #self.validation_panel = self.findChild(QtWidgets.QPushButton, 'ValidationPanel')


        #logger.debug("NOTEBOOK PAGE {} {}".format(self.notebook.GetSelection(), self.notebook.GetRowCount()))


        self.btn_load_file = self.findChild(QtWidgets.QPushButton, 'btn_load_file')
        self.btn_load_file.setToolTip("LoadFile")
        self.btn_modify_type = self.findChild(QtWidgets.QPushButton, 'btn_modify_type')
        self.btn_remove_file = self.findChild(QtWidgets.QPushButton, 'btn_remove_file')
        self.btn_params_other_settings = self.findChild(QtWidgets.QPushButton, 'btn_fastrelaxparams_other_settings')
        self.btn_prj_add = self.findChild(QtWidgets.QToolButton, 'btn_prj_add')
        self.btn_prj_add.setIcon(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-add.png')))
        

        self.btn_prj_remove = self.findChild(QtWidgets.QToolButton, 'btn_prj_remove')
        self.btn_prj_remove.setIcon(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-remove.png')))

        self.btn_prj_update = self.findChild(QtWidgets.QToolButton, 'btn_prj_update')
        self.btn_prj_update.setIcon(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-edit.png')))

        for obj in self.shared_objects:
            obj.set_controls(self, obj.db_table)



        #self.show_validation_placeholder()


    # def show_validation_placeholder(self):
    #     #self.validation.reports.ctrl.Hide()
    #     if not 'validation_placeholder' in vars(self):
    #         self.validation_placeholder = wx.StaticText(self.validation_panel, size=(500,500), label="No validation available.", pos=(20, 20))

    def init_menubar(self):
        logger.debug("=== Initializing MenuBar ===")

        self.menubar = self.menuBar()
        self.file_menu = QtWidgets.QMenu("&File", self)
        self.menubar.addMenu(self.file_menu)
        self.project_menu = QtWidgets.QMenu("&Project", self)
        self.menubar.addMenu(self.project_menu)
        self.help_menu = QtWidgets.QMenu("&Help", self)
        self.menubar.addMenu(self.help_menu)

        self.exit_action = QtWidgets.QAction("Quit", self)
        self.add_prj_action = QtWidgets.QAction("Add Project", self)
        self.delete_prj_action = QtWidgets.QAction("Delete Project", self)
        self.change_prj_action = QtWidgets.QAction("Change Project", self)
        self.about_action = QtWidgets.QAction("About", self)

        self.exit_action.setShortcut('Ctrl+Q')
        self.exit_action.setStatusTip('Exit application')

        self.file_menu.addAction(self.exit_action)
        self.project_menu.addAction(self.add_prj_action)
        self.project_menu.addAction(self.delete_prj_action)
        self.project_menu.addAction(self.change_prj_action)
        self.help_menu.addAction(self.about_action)



    def init_toolbar(self):
        logger.debug("=== Initializing ToolBar ===")   # Using a title
        self.tb = self.addToolBar("Toolbar")
        self.tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        self.tb_run = QtWidgets.QAction(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-go-forward-ltr.png')),"Run",self)
        self.tb.addAction(self.tb_run)

        self.tb_cancel = QtWidgets.QAction(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-stop.png')),"Cancel",self)
        self.tb.addAction(self.tb_cancel)

        self.tb_settings = QtWidgets.QAction(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-preferences.png')),"Settings",self)
        self.tb.addAction(self.tb_settings)

        self.tb_clear = QtWidgets.QAction(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-clear.png')),"Clear",self)
        self.tb.addAction(self.tb_clear)


    def init_gui(self):
        logger.debug("=== Initializing GUI ===")
        for obj in self.shared_objects:
            logger.debug(f"Initializing  {obj}")
            self.gui_params = obj.init_gui(self.gui_params, self.sess)
            logger.debug(self.gui_params)
        self.fastrelaxparams.update_from_default(self.default_values)

    def init_settings(self):
        logger.debug("=== Initializing Settings ===")
        self.settings.add_blank_entry(self.sess)
        self.settings.update_from_global_config(self.sess)
        exec_messages = self.settings.check_executables(self.sess)
        if not exec_messages == []:
            for message in exec_messages:
                message_dlg('Error', message)

    def create_monitor_thread(self, job_params):
        self.monitor_thread = QThread()
        self.monitor_worker = gui_threads.MonitorJob(self, job_params)
        self.monitor_worker.moveToThread(self.monitor_thread)
        self.monitor_thread.started.connect(self.monitor_worker.run)
        self.monitor_worker.finished.connect(self.monitor_thread.quit)
        self.monitor_worker.finished.connect(self.monitor_worker.deleteLater)
        self.monitor_thread.finished.connect(self.monitor_thread.deleteLater)
        self.monitor_worker.update_log.connect(self.OnUpdateLog)
        self.monitor_worker.clear_log.connect(self.OnClearLog)
        self.monitor_worker.job_status.connect(self.OnJobStatus)
        self.monitor_thread.start()
        self.threads.append(self.monitor_thread)

    def check_project_exists(self):
        if self.prj.is_empty(self.sess):
            dlg = ProjectDlg(self, "add")
            if dlg.exec_():
                self.gui_params = self.prj.init_gui(self.gui_params, self.sess)
        if self.prj.is_empty(self.sess):
            logger.error("Cannot start GUI without initial project.")
            raise SystemExit


    def reconnect_jobs(self):
        jobs = self.job.reconnect_jobs(self.sess)
        logger.debug("Jobs to reconnect")
        logger.debug(jobs)
        if not jobs == []:
            for job_params in jobs:
                self.create_monitor_thread(job_params)

    def bind_event_handlers(self):
        logger.debug("=== Bind Event Handlers ===")
        #Menubar
        self.exit_action.triggered.connect(self.close)
        self.add_prj_action.triggered.connect(self.OnBtnPrjAdd)
        self.delete_prj_action.triggered.connect(self.OnBtnPrjRemove)
        self.change_prj_action.triggered.connect(self.OnBtnPrjUpdate)
        self.about_action.triggered.connect(self.OnAbout)
        #Toolbar
        self.tb.actionTriggered[QtWidgets.QAction].connect(self.ToolbarSelected)

        #Buttons
        self.btn_prj_add.clicked.connect(self.OnBtnPrjAdd)
        self.btn_prj_update.clicked.connect(self.OnBtnPrjUpdate)
        self.btn_prj_remove.clicked.connect(self.OnBtnPrjRemove)
        self.btn_params_other_settings.clicked.connect(self.OnBtnFastRelaxOtherSettings)
        self.btn_load_file.clicked.connect(self.OnBtnLoadFile)
        self.btn_modify_type.clicked.connect(self.OnBtnModifyType)
        self.btn_remove_file.clicked.connect(self.OnBtnRemoveFile)
        self.job.list.ctrl.cellClicked.connect(self.OnLstJobSelected)
        self.fastrelaxparams.files.ctrl.cellClicked.connect(self.OnLstFilesSelected)
        #Combos
        self.prj.list.ctrl.activated.connect(self.OnCmbProjects)
        #self.fastrelaxparams.space.ctrl.currentIndexChanged.connect(self.OnCmbSpace)
        #ContextMenu
        self.job.list.ctrl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.job.list.ctrl.customContextMenuRequested.connect(self.OnJobContextMenu)

    def ToolbarSelected(self, s):
        selected = s.text()
        if selected == 'Run':
            self.OnBtnRun()
        elif selected == 'Cancel':
            self.OnBtnCancel()
        elif selected == 'Settings':
            self.OnBtnSettings()
        elif selected == 'Clear':
            self.OnBtnClear()

    def OnBtnFastRelax(self, evt):
        pass


    def OnJobStatus(self, job_params):
        logger.debug("OnJobStatus")
        self.job_params = job_params
        if job_params['status'] == "aborted":
            self.job.update_status("aborted", job_params['job_id'], self.sess)
        elif job_params['status'] == "running":
            self.job.update_status("running", job_params['job_id'], self.sess)
            self.job.update_pid(job_params['pid'], job_params['job_id'], self.sess)
        elif job_params['status'] == "finished":
            self.job.update_status("finished", job_params['job_id'], self.sess)

            validation = self.job.insert_validation(self.validation, job_params, self.sess)
            if validation:
                if not self.gui_params['job_id'] is None:
                    if int(self.gui_params['job_id']) == int(job_params['job_id']):
                        self.notebook.setTabEnabled(2, True)
                        self.validation.init_gui(self.gui_params, self.sess)
            else:
                self.notebook.setTabEnabled(2, False)
                logger.debug("No validation report found!")
        elif job_params['status'] == "error":
            self.job.update_status("error", job_params['job_id'], self.sess)
        self.gui_params = self.job.init_gui(self.gui_params, self.sess)
        self.job.update_log(job_params)

    def OnUpdateLog(self, log):
        lines, job_id = log
        page = self.notebook.currentWidget().objectName()
        logger.debug("Notebook page {} id {} {}".format(page, self.gui_params['job_id'], job_id))
        if not self.gui_params['job_id'] is None:
            if int(self.gui_params['job_id']) == int(job_id) and page == "LogTab":
                for line in lines:
                    logger.debug(line)
                    self.job.log.ctrl.appendPlainText(line)
            else:
                logger.debug("job id or page not matching")
        else:
            logger.debug("no job selected")

    def OnAbout(self):
        dlg = AboutDlg(self)
        dlg.exec_()

    def OnBtnLoadFile(self):
        dlg = QtWidgets.QFileDialog()
        dlg.setDirectory(self.gui_params['project_path'])
        if dlg.exec_():
            paths = dlg.selectedFiles()
            self.fastrelaxparams.files.add_from_gui(paths)

    def OnBtnModifyType(self):
        file_type = None
        dlg = ModTypeDlg(self)
        if dlg.exec():
            file_type = dlg.get_type()
        if file_type is None:
            message_dlg('Error', 'No file selected!')
        else:
            if self.fastrelaxparams.files.modify_type_from_gui(file_type=file_type) is False:
                message_dlg('Error', 'The selected file type can only be assigned once!')

        # else:
        #     dlg = wx.SingleChoiceDialog(None,
        #                                 "Choose...",
        #                                 "Type",
        #                                 ["Model", "Map", "Test Map", "Params", "Constraints", "Reference Model", "Symmetry Definition"],
        #                                 wx.CHOICEDLG_STYLE)
        #     if dlg.ShowModal() == wx.ID_OK:
        #         file_type = dlg.GetStringSelection()
        #         self.fastrelaxparams.files.modify_type_from_gui(file_type=file_type)
        #     dlg.Destroy()

    def OnBtnRemoveFile(self):
        logger.debug("On btn remove")
        row = self.fastrelaxparams.files.ctrl.currentRow()
        if row == -1:
            message_dlg('Error', 'No file selected!')
        else:
            self.fastrelaxparams.files.remove_from_gui(row)
            self.fastrelaxparams.files.ctrl.removeRow(row)
            self.fastrelaxparams.files.selected_item = None



    def OnBtnRun(self):
        try:
            # Prepare Job
            self.fastrelaxparams.update_from_gui()
            exec_messages = self.settings.check_executables(self.sess)
            logger.debug("EXEC messages")
            logger.debug(exec_messages)
            logger.debug(self.gui_params['project_id'])
            #Check if Project exists
            if self.prj.is_empty(self.sess):
                message_dlg('Error', 'Before starting a job, a project must be created!')
            elif not exec_messages == []:
                for message in exec_messages:
                    message_dlg('Error', message)
            elif self.gui_params['project_id'] is None:
                message_dlg('Error', 'No Project selected!')
            elif self.fastrelaxparams.model_file.value is None:
                message_dlg('Error', 'Model required!')
            elif self.fastrelaxparams.resolution.value is None:
                message_dlg('Error','Resolution required!')
            elif self.fastrelaxparams.self_restraints.value is True and not self.fastrelaxparams.reference_model.value is None:
                message_dlg('Error', 'Self-restraints and reference model cannot be combined!')
            else:
                #Collect params from GUI and return as dict
                job_params = self.fastrelaxparams.get_dict_run_job()

                #Prepare objects for DB insert
                params_dict_db = self.fastrelaxparams.get_dict_db_insert()
                params_obj_list = self.fastrelaxparams.generate_db_object(params_dict_db)
                project_obj = self.prj.get_project_by_id(self.gui_params['project_id'], self.sess)
                self.job.set_timestamp()
                self.job.set_next_job_project_id(self.gui_params['project_id'], self.sess)
                self.job.set_host()
                self.job.set_status("starting")
                job_params['job_project_id'] = self.job.job_project_id.value
                job_params['job_dir'] = self.job.get_job_dir(job_params['job_project_id'],
                                                                self.gui_params['job_name'])
                job_params['job_path'] = self.job.get_job_path(self.gui_params['project_path'],
                                                            job_params['job_dir'])
                job_params['log_file'] = self.job.get_log_file(self.gui_params['project_path'],
                                                            job_params['job_project_id'],
                                                            self.gui_params['job_name'])
                self.job.log_file.set_value(job_params['log_file'])
                self.job.path.set_value(job_params['job_path'])

                #self.job.set_log_file()
                jobs_dict_db = self.job.get_dict_db_insert()
                logger.debug(jobs_dict_db)
                jobs_obj_list = self.job.generate_db_object(jobs_dict_db)
                jobs_obj_list[0].fastrelaxparams_collection.append(params_obj_list[0])
                project_obj.job_collection.append(jobs_obj_list[0])

                #DB insert
                self.sess.add(project_obj)
                self.sess.commit()

                #Get job params
                job_id = jobs_obj_list[0].id
                logger.debug(f"Job project id: {job_params['job_project_id']}")



                #Update job params
                settings = self.settings.get_from_db(self.sess)
                job_params['id'] = job_id
                job_params['job_id'] = job_id
                #gui_params['log_file'] = job_params['log_file']
                #job_params['job_path'] = job_path
                job_params['phenix_path'] = settings.phenix_path
                job_params['rosetta_path'] = settings.rosetta_path
                job_params['queue_template'] = settings.queue_template
                job_params['queue_submit'] = settings.queue_submit
                self.gui_params['job_id'] = job_id

                #Start thread
                if not os.path.exists(job_params['job_path']):
                    try:
                        os.mkdir(job_params['job_path'])
                    except:
                        message_dlg('Error', f"Could not create job directory in {job_params['job_path']}!")
                        logger.debug("Could not create job directory!")
                        raise DirectoryNotCreated


                    #thread.daemon = True

                    logger.debug("Job IDs before notebook: {}".format(self.gui_params['job_id']))
                    self.job_params = job_params
                    self.process_thread = QThread()
                    self.process_worker = gui_threads.RunProcessThread(self, self.job_params)
                    self.process_worker.moveToThread(self.process_thread)
                    self.process_thread.started.connect(self.process_worker.run)
                    self.process_worker.finished.connect(self.process_thread.quit)
                    self.process_worker.finished.connect(self.process_worker.deleteLater)
                    self.process_thread.finished.connect(self.process_thread.deleteLater)
                    self.process_worker.job_status.connect(self.OnJobStatus)
                    self.process_worker.change_tab.connect(self.OnChangeTab)
                    self.process_thread.start()
                    self.threads.append(self.process_thread)

                    self.create_monitor_thread(self.job_params)

                else:
                    message_dlg('Error', 'Directory with the same name already exists in the project folder!')
                    logger.debug("Job directory already exists.")
        except DirectoryNotCreated:
            pass
        except Exception:
            pass

    def OnChangeTab(self):
        self.notebook.setCurrentIndex(1)
        self.gui_params = self.job.init_gui(self.gui_params, self.sess)

    def OnBtnCancel(self):
        if self.gui_params['job_id'] is None:
            message_dlg('Error', 'No Job selected!', 'Error')
        elif not self.gui_params['queue_job_id'] is None:
            settings = self.settings.get_from_db(self.sess)
            queue_cancel = settings.queue_cancel
            host = self.job.get_host(self.gui_params['job_id'], self.sess)
            current_host = socket.gethostname()
            if host == current_host:
                if not queue_cancel == "" and not queue_cancel is None:
                    queue_job_id = self.gui_params['queue_job_id']
                    cmd = [queue_cancel, queue_job_id]
                    try:
                        Popen(cmd)
                    except:
                        cmd = ' '.join(cmd)
                        message_dlg('Error', f'Cannot cancel job. The command was {cmd}!')
                else:
                    message_dlg('Error', 'No cancel command for queue submission method defined!')
            else:
                message_dlg('Error', f'Cannot cancel this job because it was started on a different host ({host})'
                              f' and current host is {current_host}!')
        else:
            pid = self.job.get_pid(self.gui_params['job_id'], self.sess)
            host = self.job.get_host(self.gui_params['job_id'], self.sess)
            current_host = socket.gethostname()
            if host == current_host:
                try:
                    logger.debug("PID is {}".format(pid))
                    os.killpg(int(pid), signal.SIGINT)
                    #self.job.init_gui(self.gui_params)
                except TypeError:
                    message_dlg('Error', 'No process ID found for this job!')
                except Exception as e:
                    logger.debug(e)
                    traceback.print_exc()
                    message_dlg('Error', 'Cannot cancel this job!', 'Error')
            else:
                message_dlg('Error', f'Cannot cancel this job because it was started on a different host ({host})'
                              f' and current host is {current_host}!')

    def OnCmbProjects(self):
        logger.debug("OnCmbProjects")
        project_name = str(self.prj.list.ctrl.currentText())
        if not project_name is None and not project_name == "":
            logger.debug(f"Current project {project_name}")
            new_project_id = self.prj.change_active_project(project_name, self.sess)
            logger.debug(f"New project ID {new_project_id}")
            self.gui_params['project_id'] = new_project_id
            self.gui_params['project_path'] = self.prj.get_path_by_project_id(new_project_id, self.sess)
            self.gui_params['other_settings_changed'] = False
            self.gui_params = self.job.init_gui(self.gui_params, self.sess)

    # def OnCmbProtocol(self, event):
    #     self.protocol = self.fastrelaxparams.protocol.ctrl.GetCurrentSelection()

    # def OnCmbConstraints(self, event):
    #     self.constraints = self.fastrelaxparams.constraints.ctrl.GetCurrentSelection()

    # def OnCmbSpace(self):
    #     self.space = self.fastrelaxparams.space.ctrl.GetCurrentSelection()

    def OnLstJobSelected(self):
        index = self.job.list.ctrl.currentRow()
        logger.debug(f"OnLstJobSelected index {index}")
        self.gui_params['job_project_id'] = self.job.list.ctrl.item(index, 0).text()
        logger.debug(f"Job project id {self.gui_params['job_project_id']} project id {self.gui_params['project_id']}")
        self.gui_params['job_id'] = self.job.get_job_id_by_job_project_id(self.gui_params['job_project_id'],
                                                                                          self.gui_params['project_id'],
                                                                                          self.sess)
        logger.debug(f"{self.gui_params['job_id']}")
        self.gui_params['job_name'] = self.fastrelaxparams.get_name_by_job_id(self.gui_params['job_id'],
                                                                              self.sess)
        self.gui_params['job_dir'] = self.job.get_job_dir(self.gui_params['job_project_id'],
                                                          self.gui_params['job_name'])
        self.gui_params['job_path'] = self.job.get_job_path(self.gui_params['project_path'],
                                                            self.gui_params['job_dir'])
        self.gui_params['log_file'] = self.job.get_log_file(self.gui_params['project_path'],
                                                self.gui_params['job_project_id'],
                                                self.gui_params['job_name'])
        self.gui_params['other_settings_changed'] = False
        logger.debug(f"====================>> job project id: {self.gui_params['job_project_id']}")
        logger.debug(f"Job ID: {self.gui_params['job_id']}")
        result = self.fastrelaxparams.get_params_by_job_id(self.gui_params['job_id'], self.sess)
        logger.debug(f"job id {result.job_id}")
        self.fastrelaxparams.update_from_db(result)
        self.job.update_log(self.gui_params)
        self.job.insert_validation(self.validation, self.gui_params, self.sess)
        if self.validation.check_exists(self.gui_params['job_id'], self.sess):
            self.notebook.setTabEnabled(2, True)
            self.validation.init_gui(self.gui_params, self.sess)
        else:
            self.notebook.setTabEnabled(2, False)
            logger.debug("No validation found for this job")

    def OnJobContextMenu(self, pos):
        item = self.job.list.ctrl.itemAt(pos)
        if not item is None:
            menu = QtWidgets.QMenu()
            job_project_id = self.job.list.ctrl.item(item.row(), 0).text()

            job_name = self.job.list.ctrl.item(item.row(), 1).text()

            job_id = self.job.get_job_id_by_job_project_id(job_project_id, self.gui_params['project_id'], self.sess)
            job_dir = self.job.get_job_dir(job_project_id, job_name)
            project_path = self.prj.get_path_by_project_id(self.gui_params['project_id'], self.sess)
            job_path = self.job.get_job_path(project_path, job_dir)
            logger.debug(f"job project id {job_project_id} job name {job_name} job id {job_id}")
            self.delete_job_action = QtWidgets.QAction("Delete Job", self)
            self.delete_jobfiles_action = QtWidgets.QAction("Delete Job+Files", self)
            self.set_finished_action = QtWidgets.QAction("Set to finished", self)
            self.set_running_action = QtWidgets.QAction("Set to running", self)
            menu.addAction(self.delete_job_action)
            menu.addAction(self.delete_jobfiles_action)
            menu.addAction(self.set_finished_action)
            menu.addAction(self.set_running_action)
            self.delete_job_action.triggered.connect(lambda state, x=job_id: self.OnDeleteEntry(x))
            self.delete_jobfiles_action.triggered.connect(lambda state, x=job_id, y=job_path: self.OnDeleteEntryFiles(x, y))
            self.set_finished_action.triggered.connect(lambda state, x=job_id: self.OnStatusFinished(x))
            self.set_running_action.triggered.connect(lambda state, x=job_id: self.OnStatusRunning(x))
            menu.exec_(self.job.list.ctrl.mapToGlobal(pos))



    def OnDeleteEntry(self, job_id):
        logger.debug(f"OnDeleteEntry. Job id {job_id}")
        self.job.delete_job(job_id, self.sess)
        self.gui_params = self.job.init_gui(self.gui_params, self.sess)

    def OnDeleteEntryFiles(self, job_id, job_path):
        self.job.delete_job_files(job_id, job_path, self.sess)
        self.gui_params = self.job.init_gui(self.gui_params, self.sess)

    def OnStatusRunning(self, job_id):
        self.job.update_status("running", job_id, self.sess)
        self.gui_params = self.job.init_gui(self.gui_params, self.sess)

    def OnStatusFinished(self, job_id):
        self.job.update_status("finished", job_id, self.sess)
        self.gui_params = self.job.init_gui(self.gui_params, self.sess)


    def OnBtnPrjAdd(self):
        dlg = ProjectDlg(self, "add")
        dlg.exec()
        self.gui_params = self.prj.init_gui(self.gui_params, self.sess)
        logger.debug("PrjAdd button pressed")

    def OnBtnFastRelaxOtherSettings(self):
        self.fastrelaxparams.update_from_gui()
        dlg = FastRelaxOtherSettingsDlg(self)
        dlg.exec()

    def OnBtnPrjRemove(self):
        logger.debug("PrjRemove button pressed")
        prj_name, prj_id = self.prj.get_active_project(self.sess)

        dlg = message_dlg('Error', "Remove project {} and all associated jobs?".format(prj_name))
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        val = dlg.exec_()
        if val == QtWidgets.QMessageBox.Ok:
            self.prj.delete_project(prj_id, self.sess)
        self.gui_params = self.prj.init_gui(self.gui_params, self.sess)

    def OnBtnPrjUpdate(self):
        dlg = ProjectDlg(self, "update")
        dlg.exec()
        self.gui_params = self.prj.init_gui(self.gui_params, self.sess)
        logger.debug("PrjUpdate button pressed")

    def OnBtnSettings(self):
        dlg = SettingsDlg(self)
        dlg.exec()

    def OnLstFilesSelected(self):
        self.fastrelaxparams.files.selected_item = self.fastrelaxparams.files.ctrl.currentRow()

    def OnLstFilesDeselected(self):
        self.fastrelaxparams.files.selected_item = None

    def OnClearLog(self):
        logger.debug("clear log")
        self.job.log.reset_ctrl()

    def OnBtnClear(self):
        logger.debug("Clear Btn pressed")
        self.fastrelaxparams.reset_ctrls()
        self.fastrelaxparams.files.remove_all()
        self.fastrelaxparams.update_from_default(self.default_values)
        self.gui_params['job_id'] = None
        self.gui_params['job_project_id'] = None
        self.gui_params['other_settings_changed'] = False
        self.fastrelaxparams.init_gui(self.gui_params)




if __name__ == "__main__":
    main()
