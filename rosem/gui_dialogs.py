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


def error_dialog(error_message):
    dlg = QtWidgets.QMessageBox()
    dlg.setIcon(QtWidgets.QMessageBox.Critical)
    dlg.resize(800, 400)
    dlg.setWindowTitle("Error")
    dlg.setText("A error occurred.")
    dlg.setText("Click 'Show Details' for more information.")
    dlg.setDetailedText(error_message)
    dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
    dlg.exec_()

