import logging
import sys
import traceback
import getpass
from pprint import pprint

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3 import Retry

from dcnm_utils import iteritems

logger = logging.getLogger('dcnm_connect')

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

class ConnectionError(Exception):

    def __init__(self, message, *args, **kwargs):
        super(ConnectionError, self).__init__(message)
        for k, v in iteritems(kwargs):
            setattr(self, k, v)


class AuthenticationError(Exception):

    def __init__(self, message, *args, **kwargs):
        super(AuthenticationError, self).__init__(message)
        for k, v in iteritems(kwargs):
            setattr(self, k, v)


class DCNMUnauthorizedError(Exception):

    def __init__(self, message, *args, **kwargs):
        super(DCNMUnauthorizedError, self).__init__(message)
        for k, v in iteritems(kwargs):
            setattr(self, k, v)

class HttpApi:

    def __init__(self, device, *args, port=443, connection_timeout=30, read_timeout=60, verify=False,
                 total_retries=10, read_retries=3, connect_retries=3, status_retries=3, backoff_factor=0.3,
                 status_forcelist=(413, 429, 502, 503, 504), dryrun=False, **kwargs):
        self.headers = {
            'Content-Type': "application/json"
        }
        self.txt_headers = {
            'Content-Type': "text/plain"
        }

        self.physical = f"https://{device.strip()}:{port}"
        self.device = f"https://{device.strip()}:{port}/rest"

        self.retries = connect_retries
        retry = Retry(total=total_retries, read=read_retries, connect=connect_retries, status=status_retries,
                      backoff_factor=backoff_factor, status_forcelist=status_forcelist)
        adapter = HTTPAdapter(max_retries=retry)

        self.connection = requests.Session()

        self.connection.mount("http://", adapter)
        self.connection.mount("https://", adapter)

        self.login_expiration_time = 1000000000
        self._timeout = (connection_timeout, read_timeout)
        self.verify = verify
        self._auth = False
        logger.debug("dryrun set to : {}".format(dryrun))
        self.dryrun = dryrun

    def login(self, username=None, password=None):
        ''' DCNM Login Method.  This method is automatically called by the
            Ansible plugin architecture if an active Dcnm-Token is not already
            available.
        '''

        path = "/logon"
        data = "{'expirationTime': %s}" % self.login_expiration_time

        try:
            for _ in range(self.retries):
                info = {}

                if username is None:
                    print("Enter username: ", end=' ', flush=True)
                    username = sys.stdin.readline().strip()
                    print(username)
                if password is None:
                    password = getpass.getpass(
                        prompt="Enter password for user %s: " % username)

                auth = HTTPBasicAuth(username, password)
                response = self.connection.post(self.device+path, data, headers=self.headers, auth=auth,
                                                timeout=self.timeout, verify=self.verify)
                if response.status_code == 500:
                    print("Invalid credentials. Failed to perform logon.")
                    username = password = None
                    continue
                else:
                    break
            info = self._verify_response(response, "POST", path, [(400, "Invalid value supplied for expiration time"),
                                              (500, "Invalid credentials. Failed to perform logon.")])
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            stacktrace = traceback.extract_tb(exc_traceback)
            logger.debug(
                "login: response {}".format(info))
            logger.debug(sys.exc_info())
            logger.debug(stacktrace)
            msg = "Error on attempt to connect and authenticate with DCNM controller: {}".format(e)
            raise AuthenticationError(self._return_info(None, "POST", path, msg))
        self.headers["Dcnm-Token"] = info["DATA"]["Dcnm-Token"]
        self._auth = True

    def logout(self):
        method = "POST"
        path = "/logout"

        info = {}
        try:
            response = self.connection.post(self.device+path, headers=self.headers, timeout=self.timeout, verify=self.verify)
            info = self._verify_response(response, "POST", path, [(400, "Invalid value supplied for Dcnm-Token"),
                                                                  (401, "Unauthorized access to API"),
                                                                  (500,
                                                                   "Invalid token. Failed to perform logout.")],
                                         skip_authcheck=True)
            logger.debug("logout: response: {}".format(info))
            if self._auth: del(self.headers["Dcnm-Token"])
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            stacktrace = traceback.extract_tb(exc_traceback)
            logger.debug(
                "logout error: response {}".format(info))
            logger.debug(sys.exc_info())
            logger.debug(stacktrace)
            msg = "Error on attempt to logout from DCNM controller: {}".format(e)
            raise ConnectionError(self._return_info(None, method, path, msg))
        finally:
            # Clean up tokens
            self._auth = False

    def check_url_connection(self, headers):
        # Verify HTTPS request URL for DCNM controller is accessible
        info = {"msg" : " "}
        try:
            if not self._auth: raise AuthenticationError("You have not logged in and received a Token.")
            response = self.connection.head(self.physical, verify=False, timeout=self.timeout)
            if response.status_code == 401:
                self._auth = False
                del (self.headers["Dcnm-Token"])
                self.login()
                response = self.connection.head(self.physical, verify=False, timeout=self.timeout)
            info = self._verify_response(response, "HEAD", self.physical)
            logger.debug("check_url_connection: info: {}".format(info))
        except requests.exceptions.RequestException as e:
            msg = """
                  Please verify that the DCNM controller HTTPS URL ({}) is
                  reachable from the Ansible controller and try again
                  """.format(self.physical)
            logger.debug(str(e) + msg)
            raise
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            stacktrace = traceback.extract_tb(exc_traceback)
            logger.debug(
                "check_url_connection: response {}".format(info))
            logger.debug(sys.exc_info())
            logger.debug(stacktrace)
            msg = "Error checking URL on DCNM controller: {}".format(e)
            raise ConnectionError(self._return_info(None, "HEAD", self.physical, msg))

    def get(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('get', path, headers=headers, data=data, errors=errors, data_type=data_type, **kwargs)
        return info

    def post(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('post', path, headers=headers, data=data, errors=errors, **kwargs)
        return info

    def put(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('put', path, headers=headers, data=data, errors=errors, data_type=data_type, **kwargs)
        return info

    def delete(self, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        info = self.send_request('delete', path, headers=headers, data=data, errors=errors, data_type=data_type, **kwargs)
        return info

    def send_request(self, method, path, headers=None, data=None, errors=None, data_type="json", **kwargs):
        ''' This method handles all DCNM REST API requests other then login '''

        if data_type == "json" and data is None:
            data = {}
        elif data is None:
            data = ""

        if headers:
            local_headers = headers
            local_headers["Dcnm-Token"] = self.token
        else:
            local_headers = self.headers

        # Perform some very basic path input validation.
        path = str(path)
        if path[0] != "/":
            msg = "Value of <path> does not appear to be formatted properly"
            raise ConnectionError(self._return_info(None, method, path, msg))

        url = self.device+path
        logger.debug("send_request: method {}: url: {}, headers: {}, kwargs: {}".format(method, url, local_headers, kwargs))
        if self.dryrun and (method == 'post' or method == 'put' or method == 'delete'):
            logger.debug("Dryrun enabled. Returning OK code for this send_request")
            return {"RETURN_CODE": 200}
        self.check_url_connection(local_headers)
        info = {}

        try:
            for _ in range(2):
                logger.debug("send_request: data: {}".format(data))
                if data_type == "json":
                    response = self.connection.request(method, url, json=data,
                                                       headers=local_headers, timeout=self.timeout, verify=self.verify, **kwargs)
                else:
                    response = self.connection.request(method, url, data=data,
                                                       headers=local_headers, timeout=self.timeout, verify=self.verify, **kwargs)
                logger.debug(response)
                if response.status_code == 401:
                    self._auth = False
                    del (self.headers["Dcnm-Token"])
                    self.login()
                    if self.auth:
                        continue
                    else:
                        break
                else:
                    break
            info = self._verify_response(response, method, path, errors)
            logger.debug("send_request: returning info {}".format(info))
        except Exception as e:
            eargs = e.args[0]
            exc_type, exc_value, exc_traceback = sys.exc_info()
            stacktrace = traceback.extract_tb(exc_traceback)
            logger.debug(
                "send_request: response {}".format(eargs))
            logger.debug(sys.exc_info())
            logger.debug(stacktrace)
            if isinstance(eargs, dict) and eargs.get("METHOD"):
                return eargs
            raise ConnectionError(str(e))
        return info

    def _verify_response(self, response, method, path, errors=None, skip_authcheck=False):
        ''' Process the return code and response object from DCNM '''

        msg = response.text
        jrd = self._response_to_json(response)
        rc = response.status_code
        path = response.url

        if rc >= 200 and rc <= 299:
            return self._return_info(rc, method, path, msg, jrd)
        if rc >= 400:
            # Add future error code processing here
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
        raise ConnectionError(self._return_info(rc, method, path, msg, jrd))

    def _response_to_json(self, response):
        ''' Convert response_text to json format '''
        try:
            return response.json() if response.text else {}
        # JSONDecodeError only available on Python 3.5+
        except ValueError:
            return 'Invalid JSON response: {}'.format(response.text)

    def _return_info(self, rc, method, path, msg, json_respond_data=None):
        ''' Format success/error data and return with consistent format '''

        info = {}
        info['RETURN_CODE'] = rc
        info['METHOD'] = method
        info['REQUEST_PATH'] = path
        info['MESSAGE'] = msg
        info['DATA'] = json_respond_data

        return info

    # def handle_httperror(self, exc):
    #     """Overridable method for dealing with HTTP codes.
    #     This method will attempt to handle known cases of HTTP status codes.
    #     If your API uses status codes to convey information in a regular way,
    #     you can override this method to handle it appropriately.
    #     :returns:
    #         * True if the code has been handled in a way that the request
    #         may be resent without changes.
    #         * False if the error cannot be handled or recovered from by the
    #         plugin. This will result in the HTTPError being raised as an
    #         exception for the caller to deal with as appropriate (most likely
    #         by failing).
    #         * Any other value returned is taken as a valid response from the
    #         server without making another request. In many cases, this can just
    #         be the original exception.
    #         """
    #     if exc.code == 401:
    #         if self._auth:
    #             # Stored auth appears to be invalid, clear and retry
    #             self._auth = False
    #             self.login(self.connection.get_option('remote_user'), self.connection.get_option('password'))
    #             return True
    #         else:
    #             # Unauthorized and there's no token. Return an error
    #             return False
    #
    #     return exc

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


if __name__ == '__main__':
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
    dcnm = HttpApi("10.0.2.248")
    dcnm.login(username="admin", password="MVhHuBr3")
    info = dcnm.get("/control/fabrics/vxlan_cml_3/inventory")
    pprint(info)
