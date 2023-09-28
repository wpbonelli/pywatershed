import pathlib as pl

import numpy as np
import pytest

from pywatershed.base.adapter import adapter_factory
from pywatershed.base.control import Control
from pywatershed.hydrology.prms_soilzone import PRMSSoilzone
from pywatershed.parameters import Parameters, PrmsParameters

calc_methods = ("numpy", "numba")
params = ("params_sep", "params_one")


@pytest.fixture(scope="function")
def control(domain):
    return Control.load_prms(domain["control_file"], warn_unused_options=False)


@pytest.fixture(scope="function")
def discretization(domain):
    dis_hru_file = domain["dir"] / "parameters_dis_hru.nc"
    return Parameters.from_netcdf(dis_hru_file, encoding=False)


@pytest.fixture(scope="function", params=params)
def parameters(domain, request):
    if request.param == "params_one":
        params = PrmsParameters.load(domain["param_file"])
    else:
        param_file = domain["dir"] / "parameters_PRMSSoilzone.nc"
        params = PrmsParameters.from_netcdf(param_file)

    return params


@pytest.mark.parametrize("calc_method", calc_methods)
def test_compare_prms(
    domain, control, discretization, parameters, tmp_path, calc_method
):
    tmp_path = pl.Path(tmp_path)
    output_dir = domain["prms_output_dir"]

    # get the answer data
    comparison_var_names = [
        "cap_infil_tot",
        "hru_actet",
        "perv_actet",
        "potet_lower",
        "potet_rechr",
        "recharge",
        "slow_flow",
        "slow_stor",
        "soil_lower",
        # "soil_lower_ratio",
        "soil_moist",
        "soil_moist_prev",
        "soil_moist_tot",
        "soil_rechr",
        "soil_to_gw",
        "soil_to_ssr",
        "ssr_to_gw",
        "ssres_flow",
        "ssres_in",
        "ssres_stor",
        ### "unused_potet",
    ]

    ans = {}
    for key in comparison_var_names:
        nc_pth = output_dir / f"{key}.nc"
        ans[key] = adapter_factory(nc_pth, variable_name=key, control=control)

    # setup the soilzone
    input_variables = {}
    for key in PRMSSoilzone.get_inputs():
        nc_path = output_dir / f"{key}.nc"
        input_variables[key] = nc_path

    soil = PRMSSoilzone(
        control=control,
        discretization=discretization,
        parameters=parameters,
        **input_variables,
        budget_type="error",
        calc_method=calc_method,
    )
    all_success = True
    for istep in range(control.n_times):
        # for istep in range(10):

        control.advance()

        # print("\n")
        # print(control.current_time)

        soil.advance()
        soil.calculate(float(istep))

        # compare along the way
        atol = 1.0e-4
        for key, val in ans.items():
            val.advance()
        for key in ans.keys():
            a1 = ans[key].current.data
            a2 = soil[key]
            success = np.isclose(a1, a2, atol=atol).all()
            # if success:
            # print(f"SUCCESS output variable: {key}")
            if not success:
                all_success = False
                # asdf
                diff = a1 - a2
                diffmin = diff.min()
                diffmax = diff.max()
                # print(f"time step {istep}")
                print(f"fail output variable: {key}")
                print(f"prms   {a1.min()}    {a1.max()}")
                print(f"pywatershed  {a2.min()}    {a2.max()}")
                print(f"diff   {diffmin}  {diffmax}")

        # if istep == 15:
        #     asdf

    soil.finalize()

    if not all_success:
        raise Exception("pywatershed results do not match prms results")

    #   gw.output()

    # gw.finalize()

    # assert_error = False
    # for key, (base, compare) in output_compare.items():
    #     success, diff = NetCdfCompare(base, compare).compare()
    #     if not success:
    #         print(f"comparison for {key} failed: maximum error {diff}")
    #         assert_error = True
    # assert not assert_error, "comparison failed"

    return
