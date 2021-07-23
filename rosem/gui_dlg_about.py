import pkg_resources
from PyQt5 import QtWidgets, uic

class AboutDlg(QtWidgets.QDialog):
    def __init__(self, _parent):
        super(AboutDlg, self).__init__()
        uic.loadUi(pkg_resources.resource_filename('rosem', 'about.ui'), self)