"""Prometheus metrics collector provided by executing commands in the Quorum pod via "kubectl exec"
"""
import logging
from typing import Iterable

import kubernetes
from kubernetes.client.api import core_v1_api, apps_v1_api
from kubernetes.stream import stream
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector

from .config import Config, PeerConfig  # pylint: disable=E0402
from .helper import Helper  # pylint: disable=E0402


class KubeExecMetricsCollector(Collector):
    """Executes commands via "kubectl exec" in remote pod and provides metrics
    """

    def __init__(self, config: Config):
        # The current metrics to be reported on a Prometheus scrape.
        # We cannot use "default" Gauge as the values remain even if the peer does not exist anymore
        # Therefore we set fresh metrics every time we collect peers information.
        self._current_metrics = []
        self._config = config
        self._helper = Helper()

    def collect(self) -> Iterable[Metric]:
        """Get the current metrics. Implementation of the Collector

        Returns:
            Iterable[Metric]: The current metrics
        """
        return self._current_metrics

    def _lookup_pod_name(self) -> str:
        """Looks up for the pod by configuration settings,
            e.g. by  deployment name and namespace.

        Returns:
            str: pod name
        """
        apps_v1 = apps_v1_api.AppsV1Api()
        core_v1 = core_v1_api.CoreV1Api()

        # Determine Deployment and get labels selectors
        # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1Deployment.md
        logging.debug("%s >> Getting deployment - name=%s, namespace=%s",
                      type(self).__name__, self._config.deployment, self._config.namespace)
        deployment = apps_v1.read_namespaced_deployment(
            name=self._config.deployment, namespace=self._config.namespace, _request_timeout=(1, 2))
        if deployment is None:
            logging.error("%s >> Deployment not found - name=%s, namespace=%s",
                          type(self).__name__, self._config.deployment, self._config.namespace)
            return (None, None)

        # Format Label Selectors into key1=value1,key2=value2,... format
        deployment_label_selector = deployment.spec.selector
        label_selector_string = ','.join(map(
            lambda key: f'{key}={deployment_label_selector.match_labels[key]}',
            deployment_label_selector.match_labels.keys()))
        logging.debug("%s >> Deployment found - label_selector_string=%s",
                      type(self).__name__, label_selector_string)

        # Get pods by selector
        pod_list = core_v1.list_namespaced_pod(namespace=self._config.namespace,
                                               label_selector=label_selector_string,
                                               watch=False, _request_timeout=(1, 2))

        if pod_list is None or len(pod_list.items) == 0:
            logging.warning("%s >> No pods found - label_selector=%s, namespace=%s",
                            type(self).__name__, label_selector_string, self._config.namespace)
            return (None, None)

        if len(pod_list.items) > 1:
            logging.warning("%s >> More than one pod found - label_selector=%s, namespace=%s",
                            type(self).__name__, label_selector_string, self._config.namespace)
            for each_pod in pod_list.items:
                logging.info("%s >> Pod found - name=%s",
                             type(self).__name__, each_pod.metadata.name)
            return (None, None)

        #return (pod_list.items[0].metadata.name, pod_list.items[0].status.pod_ip)
        return pod_list.items[0].metadata.name

    def _kube_exec_check_connectivity(self, pod_name: str, peer: PeerConfig):
        """Checks the connectivity from within the pod to the peer

        Returns:
            _type_: True if connection could be established else False
        """
        shell_command = f'nc -z -w 1 {peer.address} {peer.port};echo -n $?'
        logging.debug("%s >> shell_command=%s",
                      type(self).__name__, shell_command)
        exec_command = [
            '/bin/sh',
            '-c',
            shell_command]

        core_v1 = core_v1_api.CoreV1Api()
        resp = stream(core_v1.connect_get_namespaced_pod_exec,
                      name=pod_name,
                      namespace=self._config.namespace,
                      command=exec_command,
                      stderr=True, stdin=False,
                      stdout=True, tty=False,
                      _request_timeout=3)
        # do not use a tuple for _request_timeout, otherwise:
        # kubernetes.client.exceptions.ApiException:
        # (0) Reason: '<' not supported between instances of 'float' and 'tuple'

        connection_successful = resp == '0'  # either '0' or '1'
        logging.debug("%s >> %s %s (%s:%s) ", type(self).__name__,
                      'OK:  Connected to' if connection_successful else 'CANNOT connect to',
                      peer.name, peer.address, peer.port)

        return connection_successful

    def create_current_metrics(self, instance_name: str, pod_name: str):
        """Creates the current metrics

        Args:
            instance_name (str): A pretty instance name
            pod_name (str): The pod name
        """
        logging.info("%s >> Creating metrics for %s peers - instance_name=%s, pod_name=%s, namespace=%s",
                     type(self).__name__, len(self._config.peers.keys()),
                     instance_name, pod_name, self._config.namespace)

        metrics = GaugeMetricFamily('quorum_tcp_egress_connectivity',
                                    'Quorum TCP egress connectivity to other nodes by enode. (0) for no connectivity, (1) for connectivity can be established',
                                    labels=['instance_name', 'enode', 'enode_short', 'name'])

        for each_config_peer in self._config.peers.values():
            connection_successful = self._kube_exec_check_connectivity(
                pod_name=pod_name, peer=each_config_peer)
            metrics.add_metric([instance_name, each_config_peer.enode,
                                each_config_peer.enode[0:20], each_config_peer.name],
                               1 if connection_successful else 0)

        # Set current metrics to be reported by CustomCollector in a single atomic operation
        self._current_metrics = [metrics]

    def process(self):
        """Processes getting information and preparing metrics

        """
        # Use Incluster Config
        kubernetes.config.load_incluster_config()

        # Get DNS name and use it as "pretty" instance name
        instance_name = self._helper.get_host_name(url=self._config.rpc_url)
        # Retrieve pods name and ip
        pod_name = self._lookup_pod_name()

        if pod_name is not None:
            self.create_current_metrics(instance_name, pod_name)
        else:
            logging.warning("%s >> Cannot create metrics as pod_name None - pod_name=%s",
                            type(self).__name__, pod_name)
