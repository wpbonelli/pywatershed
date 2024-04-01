import pathlib as pl

import pywatershed as pws

test_data_dir = pl.Path("../test_data")

# Subset this to speed up tests by eliminating some domains
all_domain_dirs = sorted(
    [path for path in test_data_dir.iterdir() if path.is_dir()]
)


def pytest_addoption(parser):
    parser.addoption(
        "--domain",
        required=False,
        action="append",
        default=[],
        help=(
            "Domain(s) to run (name of domain dir and NOT path to it). "
            "You can pass multiples of this argument. If not used, "
            "defaults to drb_2yr."
        ),
    )

    parser.addoption(
        "--control_pattern",
        required=False,
        action="append",
        default=[],
        help=(
            "Control file glob(s) (NOT path. Can drop '.control'). "
            "You can pass multiples of this argument. If not used, "
            "all control files in each domain will be run."
        ),
    )

    parser.addoption(
        "--print_ans",
        required=False,
        action="store_true",
        default=False,
        help=("Print results and assert False for all domain tests"),
    )

    parser.addoption(
        "--all_domains",
        required=False,
        action="store_true",
        default=False,
        help=(
            "Run all test domains hru1, drb_2yr, ucb_2yr. This option can"
            "be expanded but is hardwired."
        ),
    )


def collect_simulations(
    domain_list: list,
    control_pattern_list,
    verbose: bool = False,
):
    simulations = {}
    for dom_dir in all_domain_dirs:
        # ensure this is a self-contained run (all files in repo)

        if not (dom_dir / "prcp.cbh").exists():
            # this is kind of a silly check... until something better needed
            continue

        # filter selected domains
        if len(domain_list) and (dom_dir.name not in domain_list):
            continue

        control_file_candidates = sorted(dom_dir.glob("*.control"))

        # filter against control pattern
        control_files = []
        for control in control_file_candidates:
            if not len(control_pattern_list):
                control_files += [control]
            else:
                for gg in control_pattern_list:
                    if gg in control.name:
                        control_files += [control]

        for control in control_files:
            cid = f"{dom_dir.name}:{control.with_suffix('').name}"
            ctl = pws.Control.load_prms(control, warn_unused_options=False)
            output_dir = dom_dir / ctl.options["netcdf_output_dir"]
            simulations[cid] = {
                "name": cid,
                "dir": dom_dir,
                "control_file": control,
                "output_dir": output_dir,
                "testing_yaml": control.with_suffix(".yaml"),
            }

    # check that the test_data has been generated and is up-to-date
    # for each simulation
    for sim_key in simulations.keys():
        sim_tag = sim_key.replace(":", "_")
        test_data_version_file = pl.Path(
            f"../test_data/.test_data_version_{sim_tag}.txt"
        )
        if not test_data_version_file.exists():
            msg = (
                f"Test data for simulation {sim_tag} do not appear to have\n"
                "been generated. Please see DEVELOPER.md for information on\n"
                "generating test data.\n"
            )
            raise ValueError(msg)

        repo_version_file = pl.Path("../version.txt")

        with open(test_data_version_file) as ff:
            test_version = ff.read()
        with open(repo_version_file) as ff:
            repo_version = ff.read()

        if test_version != repo_version:
            msg = (
                f"Test data for domain {sim_tag} do not appear to\n"
                "have been generated by the current version of the\n"
                "pywatershed repository. Please see DEVELOPER.md for\n"
                "information on generating test data.\n"
            )
            raise ValueError(msg)

    return simulations


def pytest_generate_tests(metafunc):
    domain_list = metafunc.config.getoption("domain")
    all_domains_option = metafunc.config.getoption("all_domains")
    # reconcile the above
    if len(domain_list) and all_domains_option:
        raise ValueError("--domain arguments conflicts with --all_domains.")
    if all_domains_option:
        # This is somewhat arbitrary
        domain_list = ["hru_1", "drb_2yr", "ucb_2yr"]
    elif not all_domains_option and not len(domain_list):
        domain_list = ["drb_2yr"]

    control_pattern_list = metafunc.config.getoption("control_pattern")
    simulations = collect_simulations(domain_list, control_pattern_list)

    if "simulation" in metafunc.fixturenames:
        # Put --print_ans in the domain fixture as it applies only to the
        # domain tests. It is a run time attribute, not actually an attribute
        # of the domain however, so the "domain" fixture is more like a
        # "domain_test" fixture (domain + runtime test options)
        # Not sure I love this, maybe have a domain_opts fixture later?
        print_ans = metafunc.config.getoption("print_ans")

        for sk, sv in simulations.items():
            sv["print_ans"] = print_ans

        # open and read in the yaml and
        # domain_list = []
        # for sk, sv in simulations.items():
        #     dd_file = pl.Path(dd)
        #     with dd_file.open("r") as yaml_file:
        #         domain_dict = yaml.safe_load(yaml_file)

        #     # Runtime test options here
        #     domain_dict["print_ans"] = print_ans

        #     # Construct/derive some convenience quantities
        #     domain_dict["file"] = dd_file
        #     domain_dict["dir"] = dd_file.parent

        #     # Transform all relative paths in the yaml (relative to the yaml
        #     # file) using the rel path to the file - spare the tester from
        #     # doing this.
        #     for ff in [
        #         "param_file",
        #         "control_file",
        #         "cbh_nc",
        #         "prms_run_dir",
        #         "prms_output_dir",
        #     ]:
        #         domain_dict[ff] = pl.Path(domain_dict[ff])
        #         if not domain_dict[ff].is_absolute():
        #             domain_dict[ff] = domain_dict["dir"] / domain_dict[ff]

        #     for fd_key in ["cbh_inputs"]:
        #         domain_dict[fd_key] = {
        #             key: (
        #                 pl.Path(val)
        #                 if pl.Path(val).is_absolute()
        #                 else domain_dict["dir"] / val
        #             )
        #             for key, val in domain_dict[fd_key].items()
        #         }

        #     # Construct a dictionary that gets used in CBH
        #     # JLM: move to a helper function in test_preprocess_cbh.py?
        #     domain_dict["input_files_dict"] = {
        #         key: val for key, val in domain_dict["cbh_inputs"].items()
        #     }

        #     # append to the list of all domains
        #     domain_list += [domain_dict]

        metafunc.parametrize(
            "simulation", simulations.values(), ids=simulations.keys()
        )
