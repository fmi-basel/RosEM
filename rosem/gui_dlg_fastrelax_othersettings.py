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
import logging

logger = logging.getLogger("RosEM")

class DefaultValues:
    def __init__(self):
        self.dihedral_cst_weight = "2.0"
        self.distance_cst_weight = "2.0"
        self.angle_cst_weight = "1.0"
        self.bond_cst_weight = "1.0"
        self.ramachandran_cst_weight = "1.0"
        self.sc_weights = "R:0.76,K:0.76,E:0.76,D:0.76,M:0.76,C:0.81,"\
                          "Q:0.81,H:0.81,N:0.81,T:0.81,S:0.81,Y:0.88,"\
                          "W:0.88,A:0.88,F:0.88,P:0.88,I:0.88,L:0.88,V:0.88"

class FastRelaxOtherSettingsDlg(QtWidgets.QDialog):
    def __init__(self, _parent):
        super(FastRelaxOtherSettingsDlg, self).__init__()
        self.sess = _parent.sess
        self.fastrelaxparams = _parent.fastrelaxparams
        self.gui_params = _parent.gui_params
        uic.loadUi(pkg_resources.resource_filename('rosem', 'fastrelax_othersettings.ui'), self)
        self.fastrelaxparams.set_controls(self, self.fastrelaxparams.db_table)
        self.accepted.connect(self.OnBtnOk)
        self.init()

    def __del__(self):
        self.fastrelaxparams.delete_controls(DefaultValues())

    def init(self):
        default_values = DefaultValues()
        if not self.gui_params['job_id'] is None:
            if not self.gui_params['other_settings_changed']:
                logger.debug("Other params not changed. Getting params from DB.")
                params = self.fastrelaxparams.get_params_by_job_id(self.gui_params['job_id'], self.sess)
                logger.debug(params)
                self.fastrelaxparams.update_from_db(params, default_values)
            else:
                self.fastrelaxparams.update_from_self()
        else:
            self.fastrelaxparams.update_from_default(default_values)

    def OnBtnOk(self):
        self.fastrelaxparams.update_from_gui()
        self.gui_params['other_settings_changed'] = True