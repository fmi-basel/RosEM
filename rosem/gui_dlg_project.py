import pkg_resources
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtGui import QIcon
import logging
from rosem.gui_dialogs import message_dlg

logger = logging.getLogger("RosEM")

class ProjectDlg(QtWidgets.QDialog):
    def __init__(self, _parent, mode):
        super(ProjectDlg, self).__init__()
        self.sess = _parent.sess
        self.prj = _parent.prj
        self.job = _parent.job
        self.mode = mode
        self.gui_params = _parent.gui_params
        uic.loadUi(pkg_resources.resource_filename('rosem', 'project.ui'), self)
        self.btn_choose_path = self.findChild(QtWidgets.QToolButton, 'btn_prj_choose_folder')
        self.prj.set_controls(self, self.prj.db_table)
        self.bind_event_handlers()

        if self.mode == 'add':
            self.init_add()
        elif self.mode == 'update':
            self.init_update()



    def init_update(self):
        _, prj_id = self.prj.get_active_project(self.sess)


        prj = self.prj.get_project_by_id(prj_id, self.sess)


        self.prj.update_from_db(prj)
        self.prj_id = prj_id
        self.mode = 'update'

    def init_add(self):
        self.mode = 'add'



    def bind_event_handlers(self):
        self.btn_choose_path.clicked.connect(self.OnBtnChooseFolder)
        self.accepted.connect(self.OnBtnOK)


    def OnBtnChooseFolder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder')


        self.prj.path.set_value(path)
        self.prj.path.ctrl.setText(path)


    def OnBtnOK(self):

        #utils.update_var_values(self.prj)
        self.prj.update_from_gui()
        if self.prj.name.value == "":
            message_dlg('Error', 'No Project name given!')
        elif self.prj.path.value == "":
            message_dlg('Error', 'No Project path given!')
        else:

            if self.prj.check_if_exists(self.prj.name.value, self.sess):
                message_dlg('Error', 'Project name already exists!')
            else:
                if self.mode == 'add':
                    logger.debug("Adding project.")
                    self.prj.insert_project(self.prj.get_dict_db_insert(), self.sess)
                elif self.mode == 'update':
                    logger.debug("Updating project.")
                    self.prj.update_project(self.prj_id, self.prj.get_dict_db_insert(), self.sess)
                project_id = self.prj.change_active_project(self.prj.name.value, self.sess)
                prj_name, prj_id = self.prj.get_active_project(self.sess)


                self.gui_params['project_id'] = project_id
                logger.debug("init project from dialog")
                self.gui_params = self.prj.init_gui(self.gui_params, self.sess)

                index = self.prj.list.ctrl.findText(prj_name, QtCore.Qt.MatchFixedString)
                logger.debug(f"index in project combo is {index}, project name is {prj_name}")
                if index >= 0:
                    self.prj.list.ctrl.setCurrentIndex(index)
                self.gui_params = self.job.init_gui(self.gui_params, self.sess)

