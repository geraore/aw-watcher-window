import argparse
import logging
import traceback
import sys
import os
from time import sleep
from datetime import datetime, timezone

from aw_core.models import Event
from aw_core.log import setup_logging
from aw_client import ActivityWatchClient

from .lib import get_current_window
from .config import watcher_config

logger = logging.getLogger("aw.watchers.window")


def get_labels_for(window, exclude_title=False):
    labels = []
    labels.append("title:" + window["title"] if not exclude_title else "title:excluded")
    labels.append("appname:" + window["appname"])
    return labels


def main():
    """ Verify python version >= 3.5 """
    # req_version is 3.5 due to usage of subprocess.run
    # It would be nice to be able to use 3.4 as well since it's still common as of May 2016
    req_version = (3, 5)
    cur_version = sys.version_info
    if not cur_version >= req_version:
        logger.error("Your Python version is too old, 3.5 or higher is required")
        exit(1)

    """ Read settings from config """
    config = watcher_config["aw-watcher-window"]

    """ Parse arguments """
    parser = argparse.ArgumentParser("A cross platform window watcher for Linux, macOS and Windows.")
    parser.add_argument("--testing", dest="testing", action="store_true")
    parser.add_argument("--exclude-title", dest="exclude_title", action="store_true")
    parser.add_argument("--verbose", dest="verbose", action="store_true")
    parser.add_argument("--poll-time", type=float, default=config.getfloat("poll_time"))
    args = parser.parse_args()

    setup_logging(name="aw-watcher-window", testing=args.testing, verbose=args.verbose,
                  log_stderr=True, log_file=True)

    logging.info("Running watcher with poll time {} seconds".format(args.poll_time))

    if sys.platform.startswith("linux") and ("DISPLAY" not in os.environ or not os.environ["DISPLAY"]):
        raise Exception("DISPLAY environment variable not set")

    client = ActivityWatchClient("aw-watcher-window", testing=args.testing)

    bucketname = "{}_{}".format(client.client_name, client.client_hostname)
    eventtype = "currentwindow"
    client.setup_bucket(bucketname, eventtype)
    client.connect()

    while True:
        try:
            current_window = get_current_window()
            logger.debug(current_window)
        except Exception as e:
            logger.error("Exception thrown while trying to get active window: {}".format(e))
            traceback.print_exc(e)
            continue

        now = datetime.now(timezone.utc)
        if current_window is None:
            logger.debug('Unable to fetch window, trying again on next poll')
        else:
            # Create current_window event
            labels = get_labels_for(current_window, exclude_title=args.exclude_title)
            current_window_event = Event(label=labels, timestamp=now)

            # Set pulsetime to 1 second more than the poll_time
            # This since the loop takes more time than poll_time
            # due to sleep(poll_time).
            client.heartbeat(bucketname, current_window_event,
                             pulsetime=args.poll_time + 1.0)

        sleep(args.poll_time)
