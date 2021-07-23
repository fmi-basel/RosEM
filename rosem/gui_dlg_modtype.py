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

class ModTypeDlg(QtWidgets.QDialog):
    def __init__(self, _parent):
        super(ModTypeDlg, self).__init__()
        self.sess = _parent.sess
        self.fastrelaxparams = _parent.fastrelaxparams
        uic.loadUi(pkg_resources.resource_filename('rosem', 'modtype.ui'), self)
        self.lst_types = self.findChild(QtWidgets.QListWidget, 'lst_files_typelist')
        self.lst_types.addItems(["Model", "Map", "Test Map", "Params",
                                 "Constraints", "Reference Model", "Symmetry Definition"])
        self.accepted.connect(self.OnBtnOk)
        self.type = None

    def get_type(self):
        return self.type

    def OnBtnOk(self):
        try:
            self.type = self.lst_types.currentItem().text()
        except AttributeError:
            self.type = None

