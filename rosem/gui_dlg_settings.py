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
import pkg_resources
from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QIcon
import logging
from rosem.gui_dialogs import message_dlg

logger = logging.getLogger("RosEM")

class SettingsDlg(QtWidgets.QDialog):
    def __init__(self, _parent):
        super(SettingsDlg, self).__init__()
        self.sess = _parent.sess
        self.settings = _parent.settings
        uic.loadUi(pkg_resources.resource_filename('rosem', 'settings.ui'), self)
        self.btn_rosetta = self.findChild(QtWidgets.QToolButton, 'btn_settings_choose_folder_rosetta')
        self.btn_phenix = self.findChild(QtWidgets.QToolButton, 'btn_settings_choose_folder_phenix')
        self.btn_template = self.findChild(QtWidgets.QToolButton, 'btn_settings_choose_template')
        self.btn_rosetta.setIcon(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-open.png')))
        self.btn_phenix.setIcon(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-open.png')))
        self.btn_template.setIcon(QIcon(pkg_resources.resource_filename('rosem.icons', 'gtk-open.png')))
        self.settings.set_controls(self, self.settings.db_table)
        self.bind_event_handlers()
        self.init()

    def bind_event_handlers(self):
        self.btn_rosetta.clicked.connect(self.OnBtnChooseFolderRosetta)
        self.btn_phenix.clicked.connect(self.OnBtnChooseFolderPhenix)
        self.btn_template.clicked.connect(self.OnBtnChooseFolderQueueTemplate)
        self.accepted.connect(self.OnBtnOk)

    def init(self):
        settings = self.settings.get_from_db(self.sess)
        logger.debug(settings.phenix_path)
        self.settings.update_from_db(settings)

    def OnBtnChooseFolderPhenix(self):
        logger.debug("OnBtnChooseFolderPhenix")
        dlg = QtWidgets.QFileDialog()
        if dlg.exec_():
            path = dlg.selectedFiles()[0]

            self.settings.phenix_path.set_value(path)
            self.settings.phenix_path.ctrl.setText(path)

    def OnBtnChooseFolderRosetta(self):
        logger.debug("OnBtnChooseFolderRosetta")
        dlg = QtWidgets.QFileDialog()
        if dlg.exec_():
            path = dlg.selectedFiles()[0]

            self.settings.rosetta_path.set_value(path)
            self.settings.rosetta_path.ctrl.setText(path)

    def OnBtnChooseFolderQueueTemplate(self):
        logger.debug("OnBtnChooseFolderQueueTemplate")
        dlg = QtWidgets.QFileDialog()
        if dlg.exec_():
            path = dlg.selectedFiles()[0]
            logger.debug(path)
            self.settings.queue_template.set_value(path)
            self.settings.queue_template.ctrl.setText(path)

    def OnBtnOk(self):
        #utils.update_var_values(self.prj)

        self.settings.update_from_gui()
        if self.settings.rosetta_path.value == "":
            message_dlg('Error', 'No rosetta path given!')
        elif self.settings.phenix_path.value == "":
            message_dlg('Error', 'No phenix path given!')
        else:
            self.settings.update_settings(self.settings.get_dict_db_insert(), self.sess)