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
            params = self.fastrelaxparams.get_params_by_job_id(self.gui_params['job_id'], self.sess)
            self.fastrelaxparams.update_from_db(params)
            # print(f"Value: {self.fastrelaxparams.ramachandran_cst_weight.value}")
            # for var in vars(default_values):
            #     for var_ in vars(self.fastrelaxparams):
            #         if var == var_:
            #             obj = getattr(default_values, var)
            #             obj_ = getattr(self.fastrelaxparams, var_)
            #             print(f"default obj {obj} fastrelaxobj {obj_.value}")
            #             if obj_.value is None:
            #                 print("setting value")
            #                 obj_.value = obj
        else:
            self.fastrelaxparams.update_from_default(default_values)

    def OnBtnOk(self):
        self.fastrelaxparams.update_from_gui()