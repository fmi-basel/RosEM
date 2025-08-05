import logging
import pkg_resources
from PyQt5 import QtWidgets, uic
import os

logger = logging.getLogger("guifold")

class QueueSubmitDlg(QtWidgets.QDialog):
    def __init__(self, _parent):
        super(QueueSubmitDlg, self).__init__()
        self.sess = _parent.sess
        self.settings = _parent.settings
        self.job_params = _parent.job_params
        uic.loadUi(pkg_resources.resource_filename('rosem', 'queue_submit.ui'), self)
        self.submission_script_field = self.findChild(QtWidgets.QPlainTextEdit, 'pte_job_queue_submit')
        self.submission_script_path = self.job_params['submission_script_path']
        with open(self.submission_script_path, 'r') as f:
            text = f.read()
        self.submission_script_field.setPlainText(text)

    def accept(self):
        text = self.submission_script_field.toPlainText()
        logger.debug(f"Writing to file {self.submission_script_path}")
        with open(self.submission_script_path, 'w') as f:
            f.write(text)
        super().accept()

    def reject(self):
        super().reject()
