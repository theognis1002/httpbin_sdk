"""Errors that can be raised by this SDK"""


class HttpBinClientError(Exception):
    """Base class for Client errors"""


class HttpBinRequestError(HttpBinClientError):
    """Error raised when there's a problem with the request that's being submitted."""


class HttpBinApiError(HttpBinClientError):
    """Error raised when HttpBin does not send the expected response.

    Attributes:
        response (HttpBinResponse): The HttpBinResponse object containing all of the data sent back from the API.

    Note:
        The message (str) passed into the exception is used when
        a user converts the exception to a str.
        i.e. str(HttpBinApiError("This text will be sent as a string."))
    """

    def __init__(self, message, response):
        msg = f"{message}\nThe server responded with: {response}"
        self.response = response
        super().__init__(msg)
