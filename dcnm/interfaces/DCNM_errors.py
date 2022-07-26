from dcnm_utils import iteritems


class DCNMInterfacesParameterError(Exception):
    pass


class DCNMSwitchesPoliciesParameterError(Exception):
    pass


class DCNMParameterError(Exception):
    pass


class DCNMSwitchStatusError(Exception):
    pass


class DCNMSwitchStatusParameterError(Exception):
    pass


class DCNMServerResponseError(Exception):
    pass


class DCNMPolicyDeployError(Exception):
    pass


class DCNMSwitchesSwitchesParameterError(Exception):
    pass


class DCNMFileError(Exception):
    pass


class DCNMValueError(Exception):
    pass


class DCNMConnectionError(Exception):

    def __init__(self, message, *args, **kwargs):
        super(DCNMConnectionError, self).__init__(message)
        for k, v in iteritems(kwargs):
            setattr(self, k, v)


class DCNMAuthenticationError(Exception):

    def __init__(self, message, *args, **kwargs):
        super(DCNMAuthenticationError, self).__init__(message)
        for k, v in iteritems(kwargs):
            setattr(self, k, v)


class DCNMUnauthorizedError(Exception):

    def __init__(self, message, *args, **kwargs):
        super(DCNMUnauthorizedError, self).__init__(message)
        for k, v in iteritems(kwargs):
            setattr(self, k, v)


class ExcelFileError(Exception):
    pass
