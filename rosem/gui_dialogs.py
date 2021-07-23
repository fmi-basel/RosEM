
import logging
import copy
import pkg_resources
from PyQt5 import QtWidgets, uic

logger = logging.getLogger('rosem')

def message_dlg(title, text):
    dlg = QtWidgets.QMessageBox()
    dlg.setIcon(QtWidgets.QMessageBox.Information)
    dlg.setText(text)
    dlg.setWindowTitle(title)
    dlg.exec()

    return dlg
