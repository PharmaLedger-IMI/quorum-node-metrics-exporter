import logging
import signal
import sys
import threading
from utils.ConfigLoader import ConfigLoader
from utils.CustomCollector import CustomCollector
from utils.MetricsProvider import MetricsProvider
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

    # Load Config
    sleep_time = 10.0
    config = ConfigLoader.load()
    if not config:
        sys.exit(1)

    # Init MetricsProvider and register CustomCollector 
    metrics_provider = MetricsProvider(config=config)
    custom_collector = CustomCollector(metrics_provider=metrics_provider)
    REGISTRY.register(custom_collector)

    # Start up the server to expose the metrics.
    start_http_server(8000)

    # Graceful and fast shutdown
    quit_event = threading.Event()
    # https://stackoverflow.com/questions/862412/is-it-possible-to-have-multiple-statements-in-a-python-lambda-expression
    signal.signal(signal.SIGTERM, lambda *_args: (logging.info("SIGTERM received") and False) or quit_event.set())
    while not quit_event.is_set():
        logging.info("Preparing metrics - rpc_url=%s", config.rpc_url)
        metrics_provider.process()
        logging.info("Done. Sleeping for %s seconds", sleep_time)
        quit_event.wait(timeout=sleep_time)

    logging.info("Leaving - quit_event.is_set()=%s", quit_event.is_set())
