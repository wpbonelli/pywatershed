from copy import deepcopy
import pathlib as pl
from typing import Union

from .cbh_utils import cbh_files_to_np_dict, cbh_adjust, cbh_check
from pynhm import PrmsParameters

fileish = Union[str, pl.PosixPath, dict]

# Notes:
# * Could/Should also take a file describing the HRUs by ID (to go in that dim in the netcdf)
# * CBH dosent have a precisesly defined state, so use a dictonary for state.
# * I've relegated the code to cbh_utils becase there is potential reuse by the
#   AtmForcings object in model.


class CBH:
    def __init__(
            self,
            files: fileish,
            adjust: PrmsParameters = None,
            units: dict = None,
            new_units: dict = None,
            output_vars: list = None,
            output_file: fileish = None,
            verbosity: bool = 0) -> None:

        self.files = files
        self.params = adjust
        self.units = units
        self.new_units = new_units
        self.state = None
        self.output_vars = output_vars
        self.output_file = output_file
        self.verbosity = verbosity

        self.set_state()
        self.check()

        if not self.new_units is None:
            self.convert_units()

        if not self.params is None:
            self.adjust(params)
            self.check()

        if self.output_file is not None:
            self.to_netcdf()

        return None

    def set_state(self):
        self.state = cbh_files_to_np_dict(self.files)
        return

    def convert_units(self):
        pass

    def adjust(self, parameters):
        _ = cbh_adjust(self.state, parameters)
        return

    def check(self):
        _ = cbh_check(self.state, verbosity=self.verbosity)
        return

    def to_netcdf(self, nc_file):
        pass
