import getpass
import logging
import sys
import traceback
from collections import OrderedDict
from pprint import pprint

import requests
from requests import RequestException
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3 import Retry, disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from DCNM_errors import DCNMConnectionError, DCNMAuthenticationError, DCNMUnauthorizedError

logger = logging.getLogger(__name__)

disable_warnings(InsecureRequestWarning)

REQUESTS_EXCEPTIONS = OrderedDict(
    {requests.ConnectTimeout: "Timeout attempting to connect with method {} to URL {} on DCNM controller: {}",
     requests.ConnectionError: "Error on attempt to connect with method {} to URL {} on DCNM controller: {}",
     requests.HTTPError: "HTTP Error sending {} method to URL {} on DCNM controller: {}",
     requests.URLRequired: "URL Required Error sending {} method to URL {} on DCNM controller: {}",
     requests.exceptions.RequestException: "Requests Error sending {} method to URL {} DCNM controller: {}",
     DCNMAuthenticationError: None,
     DCNMConnectionError: None,
     Exception: "Unknown Error sending {} request to URL {} on DCNM: {}"
     })

URL_CHECK_EXCEPTIONS = OrderedDict(
    {requests.ConnectTimeout: "Timeout on attempt to connect to url {} on DCNM controller: {}",
     requests.ConnectionError: "Error on attempt to connect to url {} on DCNM controller: {}",

     requests.exceptions.RequestException: "Please verify that the DCNM controller HTTPS URL {} is valid and try again: error message {}",
     DCNMAuthenticationError: None,
     DCNMConnectionError: None,
     Exception: "Unknown Error checking URL {} on DCNM controller: {}",
     })


class DcnmRestApi:

    def __init__(self, device, *args, port=443, connection_timeout=30, read_timeout=60, verify=False,
                 total_retries=10, read_retries=3, connect_retries=3, status_retries=3, backoff_factor=0.3,
                 status_forcelist=(413, 429, 502, 503, 504), dryrun=False, **kwargs):
        self.headers = {
            'Content-Type': "application/json"
        }
        self.txt_headers = {
            'Content-Type': "text/plain"
        }
        self.device = device
        self.port = port
        self.physical = f"https://{device.strip()}:{port}"
        self.dcnm_url_prepend = f"{self.physical}/rest"

        self.retries = connect_retries
        self.total_retries = total_retries
        self.read_retries = read_retries
        self.connect_retries = connect_retries
        self.status_retries = status_retries
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist
        retry = Retry(total=total_retries, read=read_retries, connect=connect_retries, status=status_retries,
                      backoff_factor=backoff_factor, status_forcelist=status_forcelist)
        adapter = HTTPAdapter(max_retries=retry)

        self.connection = requests.Session()

        self.connection.mount("https://", adapter)

        self.login_expiration_time = 1000000000
        self._timeout = (connection_timeout, read_timeout)
        self.verify = verify
        self._auth = False
        logger.debug("dryrun set to : {}".format(dryrun))
        self.dryrun = dryrun

    def logon(self, username=None, password=None):
        """ DCNM Login Method.
        """

        path = "/logon"
        data = "{{'expirationTime': {}}}".format(self.login_expiration_time)

        try:
            for _ in range(self.retries):
                info = {}

                if username is None:
                    username = input("Enter username: ")
                    print(username)
                if password is None:
                    password = getpass.getpass(
                        prompt="Enter password for user {}: ".format(username))

                auth = HTTPBasicAuth(username, password)
                response = self.connection.post(self.dcnm_url_prepend + path, data, headers=self.headers, auth=auth,
                                                timeout=self.timeout, verify=self.verify)
                if response.status_code == 500:
                    print("Invalid credentials. Failed to perform logon.")
                    username = password = None
                    continue
                else:
                    break
            info = self._verify_response(response, "POST", [(400, "Invalid value supplied for expiration time"),
                                                            (500,
                                                             "Invalid credentials. Failed to perform logon.")])
        except requests.ConnectTimeout as e:
            msg = "Timeout on attempt to connect to DCNM controller: {}".format(e)
            data = self._simple_exception_handler(info, msg)
            raise DCNMConnectionError(self._return_info(None, "POST", path, msg, json_respond_data=data))
        except requests.ConnectionError as e:
            msg = "Error on attempt to connect and authenticate with DCNM controller: {}".format(e)
            data = self._simple_exception_handler(info, msg)
            raise DCNMConnectionError(self._return_info(None, "POST", path, msg, json_respond_data=data))
        except RequestException as e:
            logger.critical(
                "logon: response {}".format(info))
            msg = "Error on attempt to connect and authenticate with DCNM controller: {}".format(e)
            data = self._simple_exception_handler(info, msg)
            raise DCNMConnectionError(self._return_info(None, "POST", path, msg, json_respond_data=data))
        except DCNMAuthenticationError:
            raise
        self.headers["Dcnm-Token"] = info["DATA"]["Dcnm-Token"]
        self.txt_headers["Dcnm-Token"] = info["DATA"]["Dcnm-Token"]
        self._auth = True

    def logout(self):
        method = "POST"
        path = "/logout"

        info = {}
        try:
            response = self.connection.post(self.dcnm_url_prepend + path, headers=self.headers, timeout=self.timeout,
                                            verify=self.verify)
            info = self._verify_response(response, "POST", [(400, "Invalid value supplied for Dcnm-Token"),
                                                            (401, "Unauthorized access to API"),
                                                            (500,
                                                             "Invalid token. Failed to perform logout.")],
                                         skip_authcheck=True)
            logger.debug("logout: response: {}".format(info))
            if self._auth: del (self.headers["Dcnm-Token"])
        except requests.ConnectionError as e:
            msg = "Error on attempt to logout from DCNM controller: {}".format(e)
            data = self._simple_exception_handler(info, msg)
            raise DCNMConnectionError(self._return_info(None, "POST", path, msg, json_respond_data=data))
        except RequestException as e:
            logger.error(
                "logout error: response {}".format(info))
            msg = "Error on attempt to logout from DCNM controller: {}".format(e)
            data = self._simple_exception_handler(info, msg)
            raise DCNMConnectionError(self._return_info(None, method, path, msg, json_respond_data=data))
        except DCNMUnauthorizedError:
            raise
        except DCNMConnectionError:
            raise
        finally:
            # Clean up tokens
            self._auth = False
            del self.headers["Dcnm-Token"]
            del self.txt_headers["Dcnm-Token"]

    def check_url_connection(self, url, headers):
        # Verify HTTPS request URL for DCNM controller is accessible
        logger.debug("check_url for url {}".format(url))
        info = {}
        try:
            if not self._auth: raise DCNMAuthenticationError("You have not logged in and received a Token.")
            try:
                response = self.connection.head(url, headers=headers, verify=False, timeout=self.timeout)
                info = {}
                info = self._verify_response(response, "HEAD")
                logger.debug("check_url_connection: info: {}".format(info))
            except DCNMUnauthorizedError:
                if self._re_logon():
                    response = self.connection.head(self.physical, verify=False, timeout=self.timeout)
                    info = {}
                    info = self._verify_response(response, "HEAD")
                    logger.debug("check_url_connection: info: {}".format(info))
        except tuple(URL_CHECK_EXCEPTIONS.keys()) as e:
            data, msg = self._exception_handler(URL_CHECK_EXCEPTIONS, (url, e), info)
            raise DCNMConnectionError(self._return_info(None, "HEAD", url, msg, json_respond_data=data))

    def _re_logon(self):
        self._auth = False
        del self.headers["Dcnm-Token"]
        del self.txt_headers["Dcnm-Token"]
        logger.critical(
            "Unauthorized access to DCNM resource {}. Token no good. Attempting to re-login".format(self.physical))
        try:
            self.logon()
        except RequestException as e:
            msg = "Error on attempt to re-logon to DCNM controller: {}".format(e)
            raise DCNMConnectionError(self._return_info(None, "HEAD", self.physical, msg))
        except DCNMAuthenticationError as e:
            logger.critical("Error in attempting to re-logon to DCNM controller: {}".format(e))
            raise
        if not self.auth:
            raise DCNMAuthenticationError("Token is no longer good and attempt to re-logon failed./n")
        return True

    def get(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('get', path, headers=headers, data=data, errors=errors, data_type=data_type, **kwargs)
        return info

    def post(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('post', path, headers=headers, data=data, errors=errors, data_type=data_type, **kwargs)
        return info

    def put(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('put', path, headers=headers, data=data, errors=errors, data_type=data_type, **kwargs)
        return info

    def delete(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('delete', path, headers=headers, data=data, errors=errors, data_type=data_type,
                                 **kwargs)
        return info

    def send_request(self, method, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        """ This method handles all DCNM REST API requests other than logon """

        if data_type == "json" and data is None:
            data = {}
        elif data is None:
            data = ""

        if headers:
            local_headers = headers
            local_headers["Dcnm-Token"] = self.token
        else:
            if data_type == "json":
                local_headers = self.headers
            else:
                local_headers = self.txt_headers

        # Perform some very basic path input validation.
        path = str(path)
        if path[0] != "/":
            msg = "Value of <path> does not appear to be formatted properly"
            raise DCNMConnectionError(self._return_info(None, method, path, msg))

        url = self.dcnm_url_prepend + path
        logger.debug(
            "send_request: method {}: url: {}, headers: {}, kwargs: {}".format(method, url, local_headers, kwargs))
        if self.dryrun and method in {'post', 'put', 'delete'}:
            logger.debug("Dryrun enabled. Returning OK code for this send_request")
            return {"RETURN_CODE": 200}
        self.check_url_connection(url, local_headers)
        info = {}

        try:
            for _ in range(2):
                logger.debug("send_request: data: {}".format(data))
                try:
                    if data_type == "json":
                        response = self.connection.request(method, url, json=data,
                                                           headers=local_headers, timeout=self.timeout,
                                                           verify=self.verify,
                                                           **kwargs)
                    else:
                        response = self.connection.request(method, url, data=data,
                                                           headers=local_headers, timeout=self.timeout,
                                                           verify=self.verify,
                                                           **kwargs)
                    logger.debug("send_request: response: {}".format(response))
                    info = self._verify_response(response, method, errors)
                except DCNMUnauthorizedError:
                    if self._re_logon():
                        continue
            logger.debug("send_request: returning info {}".format(info))
        except tuple(REQUESTS_EXCEPTIONS.keys()) as e:
            data, msg = self._exception_handler(REQUESTS_EXCEPTIONS, (method, url, e), info)
            if e.args:
                eargs = e.args[0]
                logger.error("send_request: response {}".format(eargs))
                if isinstance(eargs, dict) and eargs.get("METHOD"):
                    return eargs
                data = eargs
            raise DCNMConnectionError(self._return_info(None, method, path, msg, json_respond_data=data))
        return info

    def _exception_handler(self, exception_table, msg_format_tuple, info):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        for request_exception, msg in exception_table.items():
            if isinstance(exc_value, request_exception):
                break
        if msg:
            msg = msg.format(*msg_format_tuple)
        else:
            raise
        data = self._simple_exception_handler(info, msg, exc_traceback=exc_traceback)
        return data, msg

    def _simple_exception_handler(self, info, msg, exc_traceback=None):
        logger.exception(msg, exc_info=sys.exc_info())
        if exc_traceback is None:
            exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.debug(traceback.extract_tb(exc_traceback))
        data = None
        if info:
            logger.debug(
                "Requests error or Send Error: response {}".format(info))
            data = info
        return data

    def _verify_response(self, response, method, path=None, msg=None, data=None,
                         errors=None, skip_authcheck=False):
        """ Process the return code and response object from DCNM """


        msg = response.text
        jrd = self._response_to_json(response)
        rc = response.status_code
        path = response.url

        if 200 <= rc <= 299:
            return self._return_info(rc, method, path, msg, jrd)
        if rc == 500:
            raise DCNMAuthenticationError(self._return_info(rc, "POST", path, msg))
        if rc >= 400:
            msg = "RETURN_CODE: {}".format(rc)
            if not skip_authcheck and rc == 401:
                msg = "Unauthorized Access to API"
                if self.auth:
                    raise DCNMUnauthorizedError(self._return_info(rc, method, path, msg, jrd))
            elif errors:
                for code, err_msg in errors:
                    if rc == code:
                        msg = err_msg
        else:
            msg = "RETURN_CODE: {}".format(rc)
        raise DCNMConnectionError(self._return_info(rc, method, path, msg, jrd))

    @staticmethod
    def _response_to_json(response):
        """ Convert response_text to json format """
        try:
            return response.json() if response.text else {}
        # JSONDecodeError only available on Python 3.5+
        except ValueError:
            return 'Invalid JSON response: {}'.format(response.text)

    @staticmethod
    def _return_info(rc, method, path, msg, json_respond_data=None):
        """ Format success/error data and return with consistent format """

        info = {'RETURN_CODE': rc, 'METHOD': method, 'REQUEST_PATH': path, 'MESSAGE': msg, 'DATA': json_respond_data}

        logger.debug("_return_info: {}".format(info))
        return info

    @property
    def auth(self):
        return self._auth

    @property
    def token(self):
        return self.headers.get('Dcnm-Token', None)

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, connection_timeout, read_timeout=None):
        if read_timeout is None:
            self._timeout = connection_timeout
        else:
            self._timeout = (connection_timeout, read_timeout)

    def __repr__(self):
        """self, device, *args, port=443, connection_timeout=30, read_timeout=60, verify=False,
                 total_retries=10, read_retries=3, connect_retries=3, status_retries=3, backoff_factor=0.3,
                 status_forcelist=(413, 429, 502, 503, 504), dryrun=False, **kwargs
        """
        return f'{type(self).__name__}({self.device!r}, ' \
               f'port={self.port!r}, ' \
               f'connection_timeout={self._timeout[0]!r}, ' \
               f'read_timeout={self._timeout[1]!r},' \
               f'verify={self.verify!r},' \
               f'total_retries={self.total_retries!r},' \
               f'read_retries={self.read_retries!r},' \
               f'connect_retries={self.connect_retries!r},' \
               f'status_retries={self.status_retries!r},' \
               f'backoff_factor={self.backoff_factor!r},' \
               f'status_forcelist={self.status_forcelist!r},' \
               f'dryrun={self.dryrun!r})'


if __name__ == '__main__':
    ADDRESS = '10.0.2.248'
    USERNAME = 'admin'
    PASSWORD = None
    SCREENLOGLEVEL = logging.DEBUG
    FILELOGLEVEL = logging.DEBUG
    logformat = logging.Formatter(
        '%(asctime)s: %(process)d - %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - message: %(message)s')

    logging.basicConfig(level=SCREENLOGLEVEL,
                        format='%(asctime)s: %(threadName)s - %(funcName)s - %(name)s - %(levelname)s - %(message)s')

    # screen handler
    # ch = logging.StreamHandler()
    # ch.setLevel(SCREENLOGLEVEL)
    # ch.setFormatter(logformat)
    #
    # logging.getLogger('').addHandler(ch)

    logger = logging.getLogger('dcnm')

    logger.critical("Started")
    # prompt stdin for username and password
    dcnm = DcnmRestApi(ADDRESS)
    print("++++++++++++++++++loging on+++++++++++++++++++")
    dcnm.logon(username=USERNAME, password=PASSWORD)
    print("++++++++++++++++getting inventory++++++++++++++++")
    info = dcnm.get("/control/fabrics/vxlan_cml_3/inventory")
    pprint(info)
