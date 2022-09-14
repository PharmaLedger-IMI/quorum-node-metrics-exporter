import logging
import signal
import sys
import threading

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import utils.config
from utils.common import CustomCollector
from utils.kube_exec_metrics_provider import KubeExecMetricsProvider
from utils.rpc_metrics_provider import RpcMetricsProvider

if __name__ == '__main__':
    logging.basicConfig(
        format='%(levelname)s: %(message)s', level=logging.INFO)

    # Load Config
    SLEEP_TIME = 10.0
    config = utils.config.load()
    if config is None:
        sys.exit(1)

    # Init MetricsProviders and register CustomCollectors
    rpc_metrics_provider = RpcMetricsProvider(config)
    rpc_custom_collector = CustomCollector(rpc_metrics_provider)
    REGISTRY.register(rpc_custom_collector)

    kube_exec_metrics_provider = KubeExecMetricsProvider(config)
    kube_exec_custom_collector = CustomCollector(kube_exec_metrics_provider)
    REGISTRY.register(kube_exec_custom_collector)

    # Start up the server to expose the metrics.
    start_http_server(8000)

    # Graceful and fast shutdown
    quit_event = threading.Event()
    # https://stackoverflow.com/questions/862412/is-it-possible-to-have-multiple-statements-in-a-python-lambda-expression
    signal.signal(signal.SIGTERM,
                  lambda *_args: (logging.info("SIGTERM received") and False) or quit_event.set())
    while not quit_event.is_set():
        logging.info("Preparing metrics")
        rpc_metrics_provider.process()
        kube_exec_metrics_provider.process()
        logging.info("Done. Sleeping for %s seconds", SLEEP_TIME)
        quit_event.wait(timeout=SLEEP_TIME)

    logging.info("Leaving - quit_event.is_set()=%s", quit_event.is_set())
