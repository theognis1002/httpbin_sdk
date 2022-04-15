from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Response:
    api_url: str
    status_code: int
    headers: Union[dict, None]
    data: Union[dict, bytes]

    def validate(self):
        """Check if the response from Fraud Framework was successful.

        Returns:
            (Response)
                This method returns it's own object. e.g. 'self'

        Raises:
            Exception: The request to the Fraud Framework API failed.
        """
        if self.status_code == 200 and self.data and (isinstance(self.data, bytes) or self.data.get("ok", False)):
            return self
        msg = f"The request to the HttpBin API failed. (url: {self.api_url})"
        raise Exception(message=msg, response=self)
