import pathlib as pl

import yaml


def pytest_sessionstart(session):
    test_version_file = pl.Path("../test_data/.test_data_made_by_version.txt")
    if not test_version_file.exists():
        msg = (
            "Test data in test_data/ do not appear to have been generated.\n"
            "Please see DEVELOPER.md for information on generating test data."
        )
        raise ValueError(msg)

    repo_version_file = pl.Path("../version.txt")

    with open(test_version_file) as ff:
        test_version = ff.read()
    with open(repo_version_file) as ff:
        repo_version = ff.read()

    if not test_version == repo_version:
        msg = (
            "Test data in test_data/ do not appear to have been generated by\n"
            "the current version of the pywatershed repository. Please see\n"
            "DEVELOPER.md for information on generating test data."
        )
        raise ValueError(msg)

    return None


def pytest_addoption(parser):
    parser.addoption(
        "--domain_yaml",
        required=False,
        action="append",
        default=[],
        help=(
            "YAML file(s) for indiv domain tests. You can pass multiples of "
            "this argument. Default value (not shown here) is "
            "--domain_yaml=../test_data/drb_2yr/drb_2yr.yaml"
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
        help=("Run all test domains"),
    )


def pytest_generate_tests(metafunc):
    if "domain" in metafunc.fixturenames:
        # Put --print_ans in the domain fixture as it applies only to the
        # domain tests. It is a run time attribute, not actually an attribute
        # of the domain however, so the "domain" fixture is more like a
        # "domain_test" fixture (domain + runtime test options)
        # Not sure I love this, maybe have a domain_opts fixture later?
        print_ans = metafunc.config.getoption("print_ans")

        if metafunc.config.getoption("all_domains"):
            domain_file_list = [
                "../test_data/hru_1/hru_1.yaml",
                "../test_data/drb_2yr/drb_2yr.yaml",
                "../test_data/ucb_2yr/ucb_2yr.yaml",
            ]
        else:
            domain_file_list = metafunc.config.getoption("domain_yaml")
            if len(domain_file_list) == 0:
                domain_file_list = ["../test_data/drb_2yr/drb_2yr.yaml"]

        # open and read in the yaml and
        domain_ids = [pl.Path(ff).stem for ff in domain_file_list]
        domain_list = []
        for dd in domain_file_list:
            dd_file = pl.Path(dd)
            with dd_file.open("r") as yaml_file:
                domain_dict = yaml.safe_load(yaml_file)

            # Runtime test options here
            domain_dict["print_ans"] = print_ans

            # Construct/derive some convenience quantities
            domain_dict["file"] = dd_file
            domain_dict["dir"] = dd_file.parent

            # Transform all relative paths in the yaml (relative to the yaml
            # file) using the rel path to the file - spare the tester from
            # doing this.
            for ff in [
                "param_file",
                "control_file",
                "cbh_nc",
                "prms_run_dir",
                "prms_output_dir",
            ]:
                domain_dict[ff] = pl.Path(domain_dict[ff])
                if not domain_dict[ff].is_absolute():
                    domain_dict[ff] = domain_dict["dir"] / domain_dict[ff]

            for fd_key in ["cbh_inputs"]:
                domain_dict[fd_key] = {
                    key: (
                        pl.Path(val)
                        if pl.Path(val).is_absolute()
                        else domain_dict["dir"] / val
                    )
                    for key, val in domain_dict[fd_key].items()
                }

            # Construct a dictionary that gets used in CBH
            # JLM: move to a helper function in test_preprocess_cbh.py?
            domain_dict["input_files_dict"] = {
                key: val for key, val in domain_dict["cbh_inputs"].items()
            }

            # append to the list of all domains
            domain_list += [domain_dict]

        metafunc.parametrize("domain", domain_list, ids=domain_ids)
