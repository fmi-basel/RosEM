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

