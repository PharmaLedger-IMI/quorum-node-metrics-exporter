"""Main program
"""
import logging
import signal
import sys
import threading

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import utils.config
from utils.kube_exec_metrics_collector import KubeExecMetricsCollector
from utils.rpc_metrics_collector import RpcMetricsCollector


def main() -> int:
    """Main

    Returns:
        int: Return code
    """
    logging.basicConfig(
        format='%(levelname)s: %(message)s', level=logging.INFO)

    # Load Config
    sleep_time = 10.0
    config = utils.config.load()
    if config is None:
        return 1

    # Init MetricsProviders and register CustomCollectors
    rpc_metrics_collector = RpcMetricsCollector(config)
    REGISTRY.register(rpc_metrics_collector)

    kube_exec_metrics_collector = KubeExecMetricsCollector(config)
    REGISTRY.register(kube_exec_metrics_collector)

    # Start up the server to expose the metrics.
    start_http_server(8000)

    # Graceful and fast shutdown
    quit_event = threading.Event()
    # https://stackoverflow.com/questions/862412/is-it-possible-to-have-multiple-statements-in-a-python-lambda-expression
    signal.signal(signal.SIGTERM,
                  lambda *_args: (logging.info("SIGTERM received") and False) or quit_event.set())
    while not quit_event.is_set():
        logging.info("Preparing metrics")
        rpc_metrics_collector.process()
        kube_exec_metrics_collector.process()
        logging.info("Done. Sleeping for %s seconds", sleep_time)
        quit_event.wait(timeout=sleep_time)

    logging.info("Leaving - quit_event.is_set()=%s", quit_event.is_set())
    return 0

if __name__ == '__main__':
    sys.exit(main())
