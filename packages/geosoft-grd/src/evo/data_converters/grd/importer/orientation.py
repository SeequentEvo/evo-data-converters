from .ipj_orient_type import IPJ_ORIENT_TYPE

class Orientation:
    def __init__(self):
        self.eType = 0
        self.dXo = 0.0
        self.dYo = 0.0
        self.dZo = 0.0
        self.pdParms = [0.0] * 8
