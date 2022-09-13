import logging
import signal
import sys
import threading
from utils.ConfigLoader import ConfigLoader
from utils.CustomCollector import CustomCollector
from utils.KubeExecMetricsProvider import KubeExecMetricsProvider
from utils.RpcMetricsProvider import RpcMetricsProvider
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

    # Load Config
    sleep_time = 10.0
    config = ConfigLoader.load()
    if not config:
        sys.exit(1)

    # Init MetricsProviders and register CustomCollectors
    rpc_metrics_provider = RpcMetricsProvider(config=config)
    rpc_custom_collector = CustomCollector(metrics_provider=rpc_metrics_provider)
    REGISTRY.register(rpc_custom_collector)

    kube_exec_metrics_provider = KubeExecMetricsProvider(config=config)
    kube_exec_custom_collector = CustomCollector(metrics_provider=kube_exec_metrics_provider)
    REGISTRY.register(kube_exec_custom_collector)

    # Start up the server to expose the metrics.
    start_http_server(8000)

    # Graceful and fast shutdown
    quit_event = threading.Event()
    # https://stackoverflow.com/questions/862412/is-it-possible-to-have-multiple-statements-in-a-python-lambda-expression
    signal.signal(signal.SIGTERM, lambda *_args: (logging.info("SIGTERM received") and False) or quit_event.set())
    while not quit_event.is_set():
        logging.info("Preparing metrics - rpc_url=%s", config.rpc_url)
        rpc_metrics_provider.process()
        kube_exec_metrics_provider.process()
        logging.info("Done. Sleeping for %s seconds", sleep_time)
        quit_event.wait(timeout=sleep_time)

    logging.info("Leaving - quit_event.is_set()=%s", quit_event.is_set())
