import argparse
from pprint import pprint


class CSVInputError(Exception):
    """ Exception raised for invalid csv input data """
    pass


def command_args() -> argparse.Namespace:
    """ define and parse command line arguments """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vpc_csv",
                        help="vpc csv file")
    parser.add_argument("--debug",
                        action="store_true",
                        help="enable debugging output")
    parser.add_argument("--diff",
                        action="store_true",
                        help="enable diff output")
    parser.add_argument("--dcnm",
                        required=True,
                        help="dcnm hostname or ip address")

    dryrun = parser.add_mutually_exclusive_group()
    dryrun.add_argument("--dryrun",
                        help="dryrun mode, do not deploy changes (default)",
                        action="store_true")
    dryrun.add_argument("--deploy",
                        help="deploy mode, deploys changes to dcnm",
                        action="store_const",
                        dest="dryrun",
                        const=False)
    dryrun.set_defaults(dryrun=True)

    return parser.parse_args()


def validate_csv_rows(CSV_REQUIRED_KEYS: list, csv_rows: list):
    """ Validate csv rows
        rows with a vpcId key have to have these keys:
            fabric, policy, mode, switchName, switchPort, vlan,
            hostName, hostSlot, hostPort
    """

    vpc_row = False
    for rownum, row in enumerate(csv_rows, start=1):
        if 'vpcId' not in row:
            continue
        vpc_row = True
        for key in CSV_REQUIRED_KEYS:
            if key not in row or not row[key]:
                raise CSVInputError("key missing in row %s" % rownum, key)

    if not vpc_row:
        raise CSVInputError("no vpc rows found in csv")


def _dbg(header: str, data):
    """ Output debugging data """

    print("=" * 40)
    print(header)
    print("=" * 40)
    pprint(data)




