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
    interval: int
    response_file: Path

    @classmethod
    def get(cls) -> "Config":
        for var in ["NOIP_DOMAINS", "NOIP_EMAIL", "NOIP_PASSWORD", "RESPONSE_FILE"]:
            if var not in os.environ.keys():
                raise KeyError(f"{var} is missing from the environment")
        email = os.environ["NOIP_EMAIL"]
        password = os.environ["NOIP_PASSWORD"]
        domains = os.environ["NOIP_DOMAINS"]
        response_file = Path(os.environ["RESPONSE_FILE"])
        interval = os.environ.get("INTERVAL", "1h")
        duration = int(interval[:-1])
        unit = interval[-1:]
        if unit == "d":
            duration *= 24
            unit = "h"
        if unit == "h":
            duration *= 60
            unit = "m"
        if unit == "m":
            duration *= 60
            unit = "s"
        if unit != "s":
            raise ValueError(
                f"Unknown time unit: {unit}. Supported units are s, m, h, d."
            )
        logging.info(f"Polling interval: {duration}s")
        if duration < 300:
            raise ValueError(f"Minimum interval is 5m")

        return cls(email, password, domains, duration, response_file)

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
        request.add_header("User-Agent", f"k8s.www.no-ip {self.email}")

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

    while True:
        logging.debug(f"REQUEST: {request}")
        try:
            response = urlopen(request)
            duration = handle_response(response, cfg)
        except HTTPError as ex:
            duration = handle_http_error(ex)

        logging.debug(f"Sleeping for {duration}s")
        sleep(duration)


def handle_response(response, cfg) -> int:
    # c.f. https://www.noip.com/integrate/response
    content = [l.decode("ascii").strip() for l in response.readlines()]
    logging.debug("RESPONSE: {}".format("\n".join(content)))
    cfg.response_file.write_text("\n".join(content))
    result = content[0].split(" ")[0]

    if result in ["good", "nochg"]:
        logging.info(f"No-IP successfully called. Result was '{result}'.")

        # Try to prevent clock skew
        now = time()
        duration = cfg.interval - (now % cfg.interval)
    elif result == "911":
        logging.warning(
            f"No-IP returned '911'. Waiting for 30 minutes before trying again."
        )
        duration = 1800
    else:
        logging.critical(f"No-IP returned '{result}'. Check your settings")
        logging.info(
            "For an explanation of error codes, see http://www.noip.com/integrate/response"
        )
        sys.exit(2)
    return duration


def handle_http_error(error) -> int:
    # c.f. https://www.noip.com/integrate/response
    logging.critical(f"HTTP Error: {error.code} {error.msg}")
    if error.code == 500:
        logging.info("Fatal error during no-ip processing, retrying in 30m")
        duration = 1800
    else:
        if error.code == 401:
            logging.critical(
                "Invalid credentials. Check the value of NOIP_EMAIL and NOIP_PASSWORD."
            )
        sys.exit(1)
    return duration


if __name__ == "__main__":
    update()
