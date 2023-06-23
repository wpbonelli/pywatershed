import pathlib as pl
from typing import Literal

from ..base import meta
from ..base.adapter import Adapter
from ..base.budget import Budget
from ..parameters import Parameters
from ..utils.netcdf_utils import NetCdfWrite
from .control import Control
from .process import Process


class ConservativeProcess(Process):

    """ConservativeProcess base class

    ConservativeProcess is a base class for mass and energy conservation. This
    class extends the Process class with a budget on mass (energy in the
    future).

    It has budgets that can optionally be established for mass an energy and
    these can be enforced or simply diagnosed with the model run.

    Conventions are adopted through the use of the following
    properties/methods:

        mass_budget_terms/get_mass_budget_terms():
            These terms must all in in the same units across all components of
            the budget (inputs, outputs, storage_changes). Diagnostic variables
            should not appear in the budget terms, only prognostic variables
            should.

        _calculate():
            This method is to be overridden by the subclass. Near the end of
            the method, the subclass should calculate its changes in mass and
            energy storage in an obvious way. As commented for
            mass_budget_terms, storage changes should only be tracked for
            prognostic variables. (For example is snow_water_equiv = snow_ice +
            snow_liquid, then storage changes for snow_ice and snow_liquid
            should be tracked and not for snow_water_equiv).

    """

    def __init__(
        self,
        control: Control,
        discretization: Parameters,
        parameters: Parameters,
        verbose: bool,
        load_n_time_batches: int = 1,
        metadata_patches: dict[dict] = None,
        metadata_patch_conflicts: Literal["ignore", "warn", "error"] = "error",
    ):
        super().__init__(
            control=control,
            discretization=discretization,
            parameters=parameters,
            verbose=verbose,
            load_n_time_batches=load_n_time_batches,
            metadata_patches=metadata_patches,
            metadata_patch_conflicts=metadata_patch_conflicts,
        )

        self.name = "ConservativeProcess"
        return

    def output(self) -> None:
        """Output data to previously initialized output types.

        Writes output for initalized output types.

        Returns:
            None

        """
        super().output()
        if self.budget is not None:
            self.budget.output()

        return

    def finalize(self) -> None:
        """Finalize Process

        Finalizes the object, including output methods.

        Returns:
            None

        """
        super().finalize()
        if self.budget is not None:
            self.budget._finalize_netcdf()
        return

    @classmethod
    def get_mass_budget_terms(cls) -> dict:
        """Get a dictionary of variable names for mass budget terms."""
        mass_budget_terms = {
            "inputs": list(
                meta.filter_vars(
                    cls.get_inputs(), "var_category", "mass flux"
                ).keys()
            ),
            "outputs": list(
                meta.filter_vars(
                    cls.get_variables(), "var_category", "mass flux"
                ).keys()
            ),
            "storage_changes": list(
                meta.filter_vars(
                    cls.get_variables(), "var_category", "mass storage change"
                ).keys()
            ),
        }
        return mass_budget_terms

    @property
    def mass_budget_terms(self) -> dict:
        """A dictionary of variable names for the mass budget terms."""
        return self.get_mass_budget_terms()

    @classmethod
    def description(cls) -> dict:
        """A description (all metadata) for all variables in inputs, variables,
        and parameters."""
        desc = super().description()
        desc = desc | {"mass_budget_terms": cls.get_mass_budget_terms()}
        return desc

    def set_input_to_adapter(self, input_variable_name: str, adapter: Adapter):
        super().set_input_to_adapter(
            self, input_variable_name=input_variable_name, adapter=adapter
        )
        # Notes from the super()
        # can NOT use [:] on the LHS as we are relying on pointers between
        # boxes. [:] on the LHS here means it's not a pointer and then
        # requires that the calculation of the input happens before the
        # advance of this storage unit. But that gives the incorrect budget
        # for et.

        # Using a pointer between boxes means that the same pointer has to
        # be used for the budget, so there's no way to have a preestablished
        # pointer between Process and its budget. So this stuff...
        if self.budget is not None:
            for comp in self.budget.components:
                if input_variable_name in self.budget[comp].keys():
                    # can not use [:] on the LHS?
                    self.budget[comp][input_variable_name] = self[
                        input_variable_name
                    ]

        return

    def _set_budget(self, basis: str = "unit"):
        if self._budget_type is None:
            self.budget = None
        elif self._budget_type in ["error", "warn"]:
            self.budget = Budget.from_storage_unit(
                self,
                time_unit="D",
                description=self.name,
                imbalance_fatal=(self._budget_type == "error"),
                basis=basis,
            )
        else:
            raise ValueError(f"Illegal behavior: {self._budget_type}")

        return

    def calculate(self, time_length: float, **kwargs) -> None:
        """Calculate Process terms for a time step

        Args:
            simulation_time: current simulation time

        Returns:
            None
        """
        super().calculate(time_length=time_length)

        # move to a timestep finalization method at some future date.
        if self.budget is not None:
            self.budget.advance()
            self.budget.calculate()

        return

    def initialize_netcdf(
        self,
        output_dir: [str, pl.Path],
        separate_files: bool = True,
        budget_args: dict = None,
        output_vars: list = None,
    ) -> None:
        """Initialize NetCDF output.

        Args:
            output_dir: base directory path or NetCDF file path if
                separate_files is True
            separate_files: boolean indicating if storage component output
                variables should be written to a separate file for each
                variable
            budget_args: a dict of argument key: values to pass to
                initialize_netcdf on this storage unit's budget. see budget
                object for options.

        Returns:
            None

        """
        super().initialize_netcdf(
            output_dir=output_dir,
            separate_files=separate_files,
            output_vars=output_vars,
        )

        if self.budget is not None:
            if budget_args is None:
                budget_args = {}
            budget_args["output_dir"] = output_dir
            budget_args["params"] = self.params

            self.budget.initialize_netcdf(**budget_args)

        return

    def _finalize_netcdf(self) -> None:
        """Finalize NetCDF output to disk.

        Returns:
            None
        """
        super()._finalize_netcdf()

        if self._do_output_netcdf:
            self.budget._finalize_netcdf()

        return
