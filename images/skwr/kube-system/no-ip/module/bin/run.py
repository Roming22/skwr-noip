#!/usr/bin/env python3
import base64
import logging
import os
import sys
from pathlib import Path
from time import sleep, time
from typing import NamedTuple
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logging.basicConfig(
    datefmt="%Y/%m/%d %H:%M:%S",
    format="%(asctime)s\t%(levelname)s\t%(message)s",
    level=logging.INFO if os.environ.get("DEBUG", "0") == "0" else logging.DEBUG,
)


class Config(NamedTuple):
    email: str
    password: str
    domains: str
    response_file: Path

    @classmethod
    def get(cls) -> "Config":
        for var in ["NOIP_DOMAINS", "NOIP_EMAIL", "NOIP_PASSWORD", "RESPONSE_FILE"]:
            if var not in os.environ.keys():
                raise KeyError(f"{var} is missing from the environment")
        email = os.environ["NOIP_EMAIL"]
        password = os.environ["NOIP_PASSWORD"]
        domains = os.environ["NOIP_DOMAINS"]
        response_file = Path(os.environ.get("RESPONSE_FILE", "/tmp/noip.log"))

        return cls(email, password, domains, response_file)

    def get_credentials(self):
        credentials = f"{self.email}:{self.password}"
        credentials = base64.b64encode(credentials.encode("ascii")).decode("ascii")
        return credentials

    def get_request(self) -> Request:
        # c.f. https://www.noip.com/integrate/request
        url = self.get_url()
        credentials = self.get_credentials()

        request = Request(url)
        request.add_header("Authorization", f"Basic {credentials}")
        request.add_header("User-Agent", f"k8s.kube-system.no-ip {self.email}")

        logging.debug(
            'COMMAND: curl {} "{}"'.format(
                " ".join(
                    ['-H "{}: {}"'.format(k, v) for k, v in request.headers.items()]
                ),
                url,
            )
        )
        return request

    def get_url(self) -> str:
        url = f"https://dynupdate.no-ip.com/nic/update?hostname={self.domains}"
        return url


def update() -> None:
    cfg = Config.get()
    request = cfg.get_request()

    logging.debug(f"REQUEST: {request}")
    try:
        response = urlopen(request)
        duration = handle_response(response, cfg)
    except HTTPError as ex:
        duration = handle_http_error(ex)
    sys.exit(0)

def handle_response(response, cfg) -> None:
    # c.f. https://www.noip.com/integrate/response
    content = [l.decode("ascii").strip() for l in response.readlines()]
    logging.debug("RESPONSE: {}".format("\n".join(content)))
    cfg.response_file.write_text("\n".join(content))
    result = content[0].split(" ")[0]

    if result in ["good", "nochg"]:
        logging.info(f"No-IP successfully called. Result was '{result}'.")
    elif result == "911":
        logging.warning(
            f"No-IP returned '911'. Waiting for 30 minutes before trying again."
        )
        sleep(1800)
        sys.exit(1)
    else:
        logging.critical(f"No-IP returned '{result}'. Check your settings")
        logging.info(
            "For an explanation of error codes, see http://www.noip.com/integrate/response"
        )
        sys.exit(1)

def handle_http_error(error) -> int:
    # c.f. https://www.noip.com/integrate/response
    logging.critical(f"HTTP Error: {error.code} {error.msg}")
    if error.code == 500:
        logging.info("Fatal error during no-ip processing, retrying in 30m")
        sleep(1800)
        sys.exit(1)
    else:
        if error.code == 401:
            logging.critical(
                "Invalid credentials. Check the value of NOIP_EMAIL and NOIP_PASSWORD."
            )
        sys.exit(1)


if __name__ == "__main__":
    update()
