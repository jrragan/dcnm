import argparse
import logging
from time import strftime, gmtime


def command_args() -> argparse.Namespace:
    """ define and parse command line arguments """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("descriptions_file",
                        help="descriptions xlsx file")
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Shortcut for setting screen and logfile levels to DEBUG')
    parser.add_argument('-s', '--screenloglevel', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help="Default is INFO.")
    parser.add_argument('-l', '--loglevel', default='NONE',
                        choices=['NONE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Default is NONE.")
    parser.add_argument('-f', "--dcnm",
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


def main():

    # parse cli args
    args = command_args()
    mode = "DRYRUN" if args.dryrun else "DEPLOY"

    #set up screen logging
    if args.debug:
        SCREENLOGLEVEL = logging.DEBUG
    else:
        SCREENLOGLEVEL = eval('logging.{}'.format(args.screenloglevel))

    print(SCREENLOGLEVEL)

    logging.basicConfig(level=SCREENLOGLEVEL,
                        format='%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    #set up file logging
    if args.loglevel is not None:
        LOGFILE = "dcnm_interfaces" + strftime("_%y%m%d%H%M%S", gmtime()) + ".log"
        logformat = logging.Formatter(
            '%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')
        if args.debug:
            FILELOGLEVEL = logging.DEBUG
        else:
            FILELOGLEVEL = eval('logging.{}'.format(args.loglevel))
        print(FILELOGLEVEL)
        # file handler
        ch = logging.FileHandler(LOGFILE)
        ch.setLevel(FILELOGLEVEL)
        ch.setFormatter(logformat)
        logging.getLogger('').addHandler(ch)

    logger = logging.getLogger('dcnm_interfaces')
    logger.critical("Started")

    print("args parsed -- Running in %s mode" % mode)