import numpy as np

from pynhm import CsvFile, Soltab
from pynhm import PrmsParameters

import xarray as xr


def test_csv_to_netcdf(csv_files):
    nc_path = csv_files.with_suffix(".nc")
    CsvFile(csv_files).to_netcdf(nc_path)
    assert nc_path.exists()


def test_csv_to_previous_netcdf(csv_files_prev):
    nc_name = csv_files_prev.with_suffix("").name + "_prev.nc"
    nc_path = csv_files_prev.parent / nc_name
    csv = CsvFile({nc_path.stem: csv_files_prev})
    csv._get_data()  # why so private?
    orig_dates = csv._data["date"].copy()
    csv._data = np.roll(csv._data, 1, axis=0)
    csv._data["date"] = orig_dates
    # Here we will eventually want to supply the desired initial conditions
    for hh in range(len(csv._data[0])):
        if hh == 0:
            continue
        csv._data[0][hh] = np.zeros([1])[0]
    csv.to_netcdf(nc_path)
    assert nc_path.exists()


def test_misc_netcdf(misc_nc_files_input):

    if misc_nc_files_input.name == "infil":
        domain_dir = misc_nc_files_input.parent.parent
        params = PrmsParameters.load(domain_dir / "myparam.param").parameters
        imperv_frac = params["hru_percent_imperv"]
        dprst_frac = params["dprst_frac"]
        perv_frac = 1.0 - imperv_frac - dprst_frac
        ds = xr.open_dataset(misc_nc_files_input.with_suffix(".nc"))
        ds = ds.rename(infil="infil_hru")

        # not necessary
        # perv_frac = np.tile(perv_frac, (ds["infil_hru"].shape[0], 1))
        ds["infil_hru"] = ds["infil_hru"] * perv_frac

        ds.to_netcdf(misc_nc_files_input.parent / "infil_hru.nc")
        ds.close()

    assert True


def test_soltab_to_netcdf(soltab_file):

    # the nhm_ids are not available in the solta_debug file currently, so get
    # them from the domain parameters
    domain_dir = soltab_file.parent
    # this is a hack that should probably rely on the yaml if/when this fails
    params = PrmsParameters.load(domain_dir / "myparam.param")
    nhm_ids = params.parameters["nhm_id"]

    output_dir = domain_dir / "output"
    soltab = Soltab(soltab_file, output_dir=output_dir, nhm_ids=nhm_ids)

    for var in soltab.variables:
        assert (output_dir / f"{var}.nc").exists()
