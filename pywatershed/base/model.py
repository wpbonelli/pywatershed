import math
import pathlib as pl
from copy import deepcopy
from pprint import pprint
from typing import Union

from ..base.adapter import adapter_factory
from ..base.control import Control
from ..constants import fileish
from ..parameters import Parameters, PrmsParameters

process_order_nhm = [
    "PRMSSolarGeometry",
    "PRMSAtmosphere",
    "PRMSCanopy",
    "PRMSSnow",
    "PRMSRunoff",
    "PRMSSoilzone",
    "PRMSEt",
    "PRMSGroundwater",
    "PRMSChannel",
]


class Model:
    """pywatershed model builder class.

    Build a model from process classes. Model wires the inputs and outputs,
    searching for unavailable inputs from file (input_dir).

    Args:
        process_list_or_model_dict:
          TODO: Document old-style vs new-style inputs
        control: Control object.
        input_dir: A directory to search for input files.
        budget_type: None, "warn", or "error".
        verbose: Boolean.
        calc_method: Choice of available computational backend (where
          available): None and "numpy" are default, "numba" gives numba (env
          variables can control its behavior), and "fortran" uses compiled
          fortran if available.
        find_input_files: Search/find input file on __init__ or delay until run
           or advance of the model. Delaying (False) allows ModelGraph of the
           specified model without the need for input files.
        load_n_time_batches: integer number of times the input data should
           be loaded from file. Deafult is 1 or just once. If input data are
           large in space, time, or total number of variables then increasing
           this number can help reduce memory usage at the expense of reduced
           performance due to more frequent IO.

    """

    def __init__(
        self,
        process_list_or_model_dict,
        control: Control = None,
        discretization_dict: dict[Parameters] = None,
        parameters: Union[Parameters, dict[Parameters]] = None,
        input_dir: str = None,
        budget_type: str = "error",  # todo: also pass dict
        calc_method: str = "numpy",
        verbose: bool = False,
        find_input_files: bool = True,
        load_n_time_batches: int = 1,
    ):
        self.control = control
        self.discretization_dict = discretization_dict
        self.parameters = parameters
        self.input_dir = input_dir
        self.budget_type = budget_type
        self.calc_method = calc_method
        self.verbose = verbose
        self._load_n_time_batches = load_n_time_batches

        # This is for backwards compatibility
        msg = "Inputs are inconsistent"
        if isinstance(process_list_or_model_dict, list):
            # take the old-school-style inputs and convert to new-school inputs
            assert control is not None, msg
            assert discretization_dict is None, msg
            assert isinstance(parameters, PrmsParameters), msg

            # eventually handle a file for parameters?
            # proc_param_file = domain["dir"] / f"parameters_{proc_name}.nc"
            # proc["parameters"] = PrmsParameters.from_netcdf(
            #     proc_param_file
            # )

            self.model_dict = {}
            model_dict = self.model_dict
            model_dict["control"] = self.control
            for process in process_list_or_model_dict:
                proc_name = process.__name__
                model_dict[proc_name] = {}
                model_dict[proc_name]["class"] = process
                model_dict[proc_name]["parameters"] = parameters

            model_dict["model_order"] = [
                key for key in process_order_nhm if key in model_dict.keys()
            ]

        elif isinstance(process_list_or_model_dict, dict):
            assert control is None, msg
            assert discretization_dict is None, msg
            assert parameters is None, msg
            self.model_dict = process_list_or_model_dict

        else:
            raise ValueError("Invalid type of process_list_or_model_dict")

        self._categorize_model_dict()
        self._validate_model_dict()
        self._solve_inputs()
        self._init_procs()
        self._connect_procs()

        self._found_input_files = False
        if find_input_files:
            self._find_input_files()

        return

    def _categorize_model_dict(self):
        """Categorize model_dict entries

        Categorize entries into [control, dis, order, process, exchange]
        categories based on types and attributes
        """
        # TODO: add exchanges
        category_type_dict = {
            "dis": Parameters,
            "control": Control,
            "order": list,
            "process": dict,
            # "exchange": exchange class?
        }
        category_key_dict = {}
        for cat, typ in category_type_dict.items():
            category_key_dict[cat] = [
                kk for kk, vv in self.model_dict.items() if isinstance(vv, typ)
            ]

        self._category_key_dict = category_key_dict

        return

    def _validate_model_dict(self):
        cat_key_dict = self._category_key_dict
        # * a single control object
        assert len(cat_key_dict["control"]) == 1
        cat_key_dict["control"] = cat_key_dict["control"][0]
        self._control_name = cat_key_dict["control"]
        if self.control is None:
            self.control = self.model_dict[self._control_name]
        # * a single order list
        assert len(cat_key_dict["order"]) == 1
        cat_key_dict["order"] = cat_key_dict["order"][0]
        self._order_name = cat_key_dict["order"]
        self.process_order = self.model_dict[self._order_name]
        # * all processes are in order and vice-versa
        assert set(cat_key_dict["process"]) == set(
            self.model_dict[cat_key_dict["order"]]
        )
        # * all required proc dis are present
        # * all required proc in exchanges are present

        return

    def _solve_inputs(self):
        """What processes supply inputs to others, what files are needed?

        TODO: this does not currently take order into account, which could
              be important and is now possible with order specified.
        """
        proc_dict = {
            proc_name: self.model_dict[proc_name]["class"]
            for proc_name in self._category_key_dict["process"]
        }

        proc_inputs = {kk: vv.get_inputs() for kk, vv in proc_dict.items()}
        proc_vars = {kk: vv.get_variables() for kk, vv in proc_dict.items()}

        # Solve where inputs come from
        inputs_from = {}
        for comp in proc_dict.keys():
            inputs = deepcopy(proc_inputs)
            vars = deepcopy(proc_vars)
            c_inputs = inputs.pop(comp)
            _ = vars.pop(comp)

            inputs_from[comp] = {}
            for input in c_inputs:
                inputs_ptr = inputs_from
                inputs_ptr[comp][input] = []  # could use None
                for other in inputs.keys():
                    if input in vars[other]:
                        inputs_ptr[comp][input] += [other]
                        # this should be a list of length one
                        # check?

        # If inputs dont come from other processes, assume they come from
        # file in input_dir. Exception is that PRMSAtmosphere requires its
        # files on init, so dont adapt these
        file_input_names = set([])
        for k0, v0 in inputs_from.items():
            for k1, v1 in v0.items():
                if not v1:
                    file_input_names = file_input_names.union([k1])

        # initiate the file inputs here rather than in the processes
        file_inputs = {}
        # Use dummy names for now
        for name in file_input_names:
            file_inputs[name] = pl.Path(name)

        self._proc_dict = proc_dict
        self._inputs_from = inputs_from
        self._file_inputs = file_inputs
        self._file_input_names = file_input_names
        return

    def _init_procs(self):
        # instantiate processes: instance dict
        self.processes = {}
        for proc_name in self.model_dict[self._order_name]:
            # establish the args for init
            proc_specs = self.model_dict[proc_name]

            dis = None
            if "dis" in proc_specs:
                dis = self.model_dict[proc_specs["dis"]]

            process_inputs = {
                input: None
                for input in self._proc_dict[proc_name].get_inputs()
            }

            args = {
                "control": self.control,
                "discretization": dis,
                "parameters": proc_specs["parameters"],
                **process_inputs,
                "load_n_time_batches": self._load_n_time_batches,
            }

            if proc_name not in ["PRMSSolarGeometry"]:
                args["budget_type"] = self.budget_type
            if proc_name not in ["PRMSSolarGeometry", "PRMSAtmosphere"]:
                args["calc_method"] = self.calc_method

            # init the process classes with the args
            self.processes[proc_name] = self._proc_dict[proc_name](**args)

        # <
        return

    def _connect_procs(self):
        self.process_input_from = {}
        for process in self.process_order:
            self.process_input_from[process] = {}
            for input, frm in self._inputs_from[process].items():
                if not frm:
                    self.process_input_from[process][
                        input
                    ] = self._file_inputs[input]
                else:
                    self.process_input_from[process][input] = frm[0]
                    self.processes[process].set_input_to_adapter(
                        input,
                        adapter_factory(
                            self.processes[frm[0]][input],
                            control=self.control,
                            load_n_time_batches=self._load_n_time_batches,
                        ),  # drop list above
                    )
        #   <   <   <
        return

    def _find_input_files(self):
        file_inputs = {}
        for name in self._file_input_names:
            nc_path = self.input_dir / f"{name}.nc"
            file_inputs[name] = adapter_factory(
                nc_path,
                name,
                control=self.control,
                load_n_time_batches=self._load_n_time_batches,
            )
        for process in self.process_order:
            for input, frm in self._inputs_from[process].items():
                if not frm:
                    fname = file_inputs[input]._fname
                    self.process_input_from[process][input] = fname
                    self.processes[process].set_input_to_adapter(
                        input, file_inputs[input]
                    )

        self._found_input_files = True
        return

    def initialize_netcdf(
        self,
        output_dir: str,
        separate_files: bool = True,
        budget_args: dict = None,
        output_vars: list = None,
    ):
        """Initialize NetCDF output files for model (all processes)."""
        if not self._found_input_files:
            self._find_input_files()

        self._netcdf_dir = output_dir
        for cls in self.process_order:
            self.processes[cls].initialize_netcdf(
                output_dir=output_dir,
                separate_files=separate_files,
                budget_args=budget_args,
                output_vars=output_vars,
            )
        return

    def run(
        self,
        netcdf_dir: fileish = None,
        finalize: bool = True,
        n_time_steps: int = None,
        output_vars: list = None,
    ):
        """Run the model.

        Running the model wraps:
            * initializing netcdf output (optional on netcdf_dir argument)
            * full time loop (from control object) with progress reports
                * advance
                * calculate
                * output (optional on output methods requested)
            * finalize (optional)

        Args:
            netcdf_dir: optional directory to netcdf output files (initializes
               netcdf and outputs at each timestep).
            finalize: option to not finalize at the end of the time loop.
               Default is to finalize.
            n_time_steps: the number of timesteps to run
            output_vars: the vars to output to the netcdf_dir
        """
        if not self._found_input_files:
            self._find_input_files()

        if netcdf_dir:
            print("model.run(): initializing NetCDF output")
            self.initialize_netcdf(netcdf_dir, output_vars=output_vars)

        last_pct_comp = 0
        print(f"model.run(): {last_pct_comp} % complete")

        if not n_time_steps:
            n_time_steps = self.control.n_times
        for istep in range(n_time_steps):
            # progress for the impatient
            pct_complete = math.floor((istep + 1) / n_time_steps * 100)
            if not (pct_complete % 10) and pct_complete != last_pct_comp:
                last_pct_comp = pct_complete
                print(f"model.run(): {pct_complete} % complete")

            self.advance()
            self.calculate()
            self.output()

        if finalize:
            print("model.run(): finalizing")
            self.finalize()

        return

    def advance(self):
        """Advance the model in time."""
        if not self._found_input_files:
            self._find_input_files()

        self.control.advance()
        for cls in self.process_order:
            self.processes[cls].advance()
        return

    def calculate(self):
        """Calculate the model."""
        for cls in self.process_order:
            self.processes[cls].calculate(1.0)
        return

    def output(self):
        """Output the model at the current time."""
        for cls in self.process_order:
            self.processes[cls].output()
        return

    def finalize(self):
        """Finalize the model."""
        for cls in self.process_order:
            self.processes[cls].finalize()
        return
