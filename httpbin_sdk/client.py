import copy
import io
import json
import logging
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urljoin

import errors as err
import requests

from .internal_utils import _build_req_args, _build_unexpected_body_error_message
from .response import Response


class BaseClient:
    BASE_URL = "https://www.httpbin.com/"

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = BASE_URL,
        timeout: int = 30,
        # ssl: Optional[SSLContext] = None,
        proxy: Optional[str] = None,
        headers: Optional[dict] = None,
        user_agent_prefix: Optional[str] = None,
        user_agent_suffix: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.token = None if token is None else token.strip()
        self.base_url = base_url
        self.timeout = timeout
        # self.ssl = ssl
        self.proxy = proxy
        self.headers = headers or {}

        self.default_params = {}
        self._logger = logger if logger is not None else logging.getLogger(__name__)

    def api_call(  # skipcq: PYL-R1710
        self,
        api_method: str,
        *,
        http_method: str = "POST",
        files: Optional[dict] = None,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Optional[dict] = None,  # skipcq: PYL-W0621
        headers: Optional[dict] = None,
        auth: Optional[dict] = None,
    ) -> Response:
        """Create a request and execute the API call to HttpBin.

        Args:
            api_method (str): The target HttpBin API method.
                e.g. 'chat.postMessage'
            http_method (str): HTTP Verb. e.g. 'POST'
            files (dict): Files to multipart upload.
                e.g. {image OR file: file_object OR file_path}
            data: The body to attach to the request. If a dictionary is
                provided, form-encoding will take place.
                e.g. {'key1': 'value1', 'key2': 'value2'}
            params (dict): The URL parameters to append to the URL.
                e.g. {'key1': 'value1', 'key2': 'value2'}
            json (dict): JSON for the body to attach to the request
                (if files or data is not specified).
                e.g. {'key1': 'value1', 'key2': 'value2'}
            headers (dict): Additional request headers
            auth (dict): A dictionary that consists of client_id and client_secret

        Returns:
            (HttpBinResponse)
                The server's response to an HTTP request. Data
                from the response can be accessed like a dict.
                If the response included 'next_cursor' it can
                be iterated on to execute subsequent requests.

        Raises:
            HttpBinApiError: The following HttpBin API call failed:
                'chat.postMessage'.
            HttpBinRequestError: Json data can only be submitted as
                POST requests.
        """

        api_url = urljoin(self.base_url, api_method)
        headers = headers or {}
        headers.update(self.headers)
        req_args = _build_req_args(
            token=self.token,
            http_method=http_method,
            files=files,
            data=data,
            default_params=self.default_params,
            params=params,
            json=json,  # skipcq: PYL-W0621
            headers=headers,
            auth=auth,
            # ssl=self.ssl,
            proxy=self.proxy,
        )

        return self._sync_send(api_url=api_url, req_args=req_args)

    def _build_urllib_request_headers(
        self, token: str, has_json: bool, has_files: bool, additional_headers: dict
    ) -> Dict[str, str]:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        headers.update(self.headers)
        if token:
            headers.update({"Authorization": "Bearer {}".format(token)})
        if additional_headers:
            headers.update(additional_headers)
        if has_json:
            headers.update({"Content-Type": "application/json;charset=utf-8"})
        if has_files:
            # will be set afterwards
            headers.pop("Content-Type", None)
        return headers

    def _urllib_api_call(
        self,
        *,
        token: Optional[str] = None,
        url: str,
        query_params: Dict[str, str],
        json_body: Dict,
        body_params: Dict[str, str],
        files: Dict[str, io.BytesIO],
        additional_headers: Dict[str, str],
    ) -> Response:
        """Performs a HttpBin API request and returns the result.

        Args:
            token: HttpBin API Token (either bot token or user token)
            url: Complete URL (e.g., https://www.HttpBin.com/api/chat.postMessage)
            query_params: Query string
            json_body: JSON data structure (it's still a dict at this point),
                if you give this argument, body_params and files will be skipped
            body_params: Form body params
            files: Files to upload
            additional_headers: Request headers to append

        Returns:
            API response
        """

        if self._logger.level <= logging.DEBUG:

            def convert_params(values: dict) -> dict:
                if not values or not isinstance(values, dict):
                    return {}
                return {
                    k: ("(bytes)" if isinstance(v, bytes) else v)
                    for k, v in values.items()
                }

            headers = {
                k: "(redacted)" if k.lower() == "authorization" else v
                for k, v in additional_headers.items()
            }
            self._logger.debug(
                f"Sending a request - url: {url}, "
                f"query_params: {convert_params(query_params)}, "
                f"body_params: {convert_params(body_params)}, "
                f"files: {convert_params(files)}, "
                f"json_body: {json_body}, "
                f"headers: {headers}"
            )

        request_data = {}

        request_headers = self._build_urllib_request_headers(
            token=token or self.token,
            has_json=json is not None,
            has_files=files is not None,
            additional_headers=additional_headers,
        )
        request_args = {
            "headers": request_headers,
            "data": request_data,
            "params": body_params,
            "files": files,
            "json": json_body,
        }
        if query_params:
            q = urlencode(query_params)
            url = f"{url}&{q}" if "?" in url else f"{url}?{q}"

        response = self._perform_urllib_http_request(url=url, args=request_args)
        response_body = response.get("body", None)  # skipcq: PTC-W0039
        response_body_data: Optional[Union[dict, bytes]] = response_body
        if response_body is not None and not isinstance(response_body, bytes):
            try:
                response_body_data = json.loads(response["body"])
            except json.decoder.JSONDecodeError:
                message = _build_unexpected_body_error_message(response.get("body", ""))
                raise err.HttpBinApiError(message, response)

        all_params: Dict[str, Any] = (
            copy.copy(body_params) if body_params is not None else {}
        )
        if query_params:
            all_params.update(query_params)
        request_args["params"] = all_params  # for backward-compatibility

        return Response(
            client=self,
            http_verb="POST",  # you can use POST method for all the Web APIs
            api_url=url,
            req_args=request_args,
            data=response_body_data,
            headers=dict(response["headers"]),
            status_code=response["status"],
        ).validate()
