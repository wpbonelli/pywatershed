import numpy as np

class dotdict(dict):
    """dot.notation access to dictionary attributes."""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class PrmsParameters:
    """PRMS parameter class

    parameter_file: str
        path to PRMS parameter file
    """

    def __init__(self, parameter_file):
        (
            self._dimensions,
            self._parameter_data,
            self._parameter_dimensions,
            self._parameter_types,
        ) = _load_prms_parameters(parameter_file)

        self._dimension_keys = list(self._dimensions.keys())
        self._parameter_keys = list(self._parameter_data.keys())

        parameters = self._parameter_data.copy()
        for key, value in self._dimensions.items():
            parameters[key] = value
        self.parameters = dotdict(parameters)
        print(self.parameters)

    def __getattr__(self, item):
        if isinstance(item, dict):
            
    def __getitem__(self, name: str):
        if isinstance()
        return self._parameter_data.get(name, None)

    def __setattr__(self, key, value):(self, name: str) -> dict:
        return self._parameter_data.get(name, None)

    def __delitem__(self, name: str):
        self._parameter_data.pop(name, None)

    @property
    def get_dimensions(self):
        return self._dimensions

    @property
    def get_parameter_data(self):
        return self._parameter_data

    @property
    def get_parameter_dimensions(self):
        return self._parameter_dimensions

    @property
    def get_parameter_types(self):
        return self._parameter_types

    def get_parameters(self, keys):
        """
        Get a subset of keys in the parameter dictionary

        Parameters
        ----------
        keys : str list or tuple
            parameters to extract from the full parameter dictionary

        Returns
        -------
        subset : dict
            Subset of full parameter dictionary with the passed parameter
            keys. Passed keys that do not exist in the full parameter
            dictionary are set to None

        """
        if isinstance(keys, str):
            keys = [keys]

        return {key: self._parameter_data.get(key, None) for key in keys}


def _load_prms_parameters(parameter_file):
    """Read a PRMS parameter file

    :param parameter_file:
    :return:
    """
    line_num = 0
    vals = {}
    dims = {}
    param_dims = {}
    param_type = {}

    with open(parameter_file) as f:
        reading_dims = False
        for line in f:
            try:
                line = line.rstrip()  # remove '\n' at end of line
                line_num += 1
                if line == "** Dimensions **":
                    reading_dims = True
                    line = f.readline().rstrip()
                    line_num += 1

                if line == "** Parameters **":
                    reading_dims = False
                    break

                if reading_dims:
                    line = f.readline().rstrip()
                    line_num += 1
                    dim_name = line

                    line = f.readline().rstrip()
                    line_num += 1
                    size = line

                    if dim_name in dims.keys():
                        pass
                    else:
                        dims[dim_name] = int(size)
            except:
                msg = (
                    f"read parameters exception line = {line}\n"
                    + f"read parameters exception line_num = {str(line_num)}\n"
                )
                raise ValueError(msg)

        #        read params
        for line in f:
            try:
                line = line.rstrip()  # remove '\n' at end of line
                line_num += 1

                if line == "####":
                    line = f.readline().rstrip()
                    line = line.split(" ", 1)[
                        0
                    ]  # old format parameter files have a blank (' ') and then a width format value. Strip this off.
                    param_name = line
                    line_num += 1

                    line = f.readline().rstrip()
                    line_num += 1
                    num_dims = int(line)
                    pd = [None] * num_dims
                    for ii in range(num_dims):
                        line = f.readline().rstrip()
                        pd[ii] = line
                        line_num += 1

                    param_dims[param_name] = pd

                    line = f.readline().rstrip()
                    line_num += 1
                    num_vals = int(line)
                    line = f.readline().rstrip()
                    line_num += 1
                    tp = int(line)
                    param_type[param_name] = tp

                    if tp == 2:
                        vs = np.zeros(num_vals, dtype=float)
                        for jj in range(num_vals):
                            line = f.readline().rstrip()
                            line_num += 1
                            vs[jj] = float(line)

                    elif tp == 1:
                        vs = np.zeros(num_vals, dtype=int)
                        for jj in range(num_vals):
                            line = f.readline().rstrip()
                            line_num += 1
                            vs[jj] = int(line)

                    else:
                        vs = np.zeros(num_vals, dtype=np.chararray)
                        for jj in range(num_vals):
                            line = f.readline().rstrip()
                            line_num += 1
                            vs[jj] = line

                    if num_dims == 2:
                        vs.shape = (dims[pd[1]], dims[pd[0]])

                    if param_name in vals.keys():
                        print(
                            "parameter ",
                            param_name,
                            " is already in ",
                            parameter_file,
                        )
                    else:
                        vals[param_name] = vs

            except:
                raise ValueError(
                    f"read parameters exception line_num = {line_num}"
                )

    return dims, vals, param_dims, param_type
