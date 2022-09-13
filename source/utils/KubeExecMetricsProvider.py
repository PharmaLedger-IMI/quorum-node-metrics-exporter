import logging

from .Config import Config, PeerConfig
from .Helper import Helper
from .IMetricsProvider import IMetricsProvider
from kubernetes import config
from kubernetes.client.api import core_v1_api, apps_v1_api
from kubernetes.stream import stream
from prometheus_client.core import GaugeMetricFamily

class KubeExecMetricsProvider(IMetricsProvider):
    """Executes commands via "kubectl exec" in remote pod and provides metrics
    """
    def __init__(self, config:Config):
        # The current metrics to be reported on a Prometheus scrape.
        # Note: We cannot use "default" Gauge as the values remain even if the peer does not exists anymore.
        # Therefore we set fresh metrics every time we collect peers information.
        self._current_metrics = []
        self._config = config
        self._helper = Helper()

    def getCurrentMetrics(self) -> list:
        """Get the current metrics. Implementation of the IMetricsProvider

        Returns:
            list: The current metrics
        """
        return self._current_metrics

    def lookup_pod_name_and_ip(self) -> tuple:
        """Looks up for the pod and its ip address by the deployment name and namespace from configuration

        Returns:
            tuple: pod name and ip address
        """
        apps_v1 = apps_v1_api.AppsV1Api()
        core_v1 = core_v1_api.CoreV1Api()

        # Determine Deployment and get labels selectors
        # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1Deployment.md
        logging.debug("%s >> Getting deployment - name=%s, namespace=%s", type(self).__name__, self._config.deployment, self._config.namespace)
        deployment = apps_v1.read_namespaced_deployment(name=self._config.deployment, namespace=self._config.namespace, _request_timeout=(1,2))
        if deployment is None:
            logging.error("%s >> Deployment not found - name=%s, namespace=%s", type(self).__name__, self._config.deployment, self._config.namespace)
            return (None, None)

        # Format Label Selectors into key1=value1,key2=value2,... format
        deployment_label_selector = deployment.spec.selector
        label_selector_string = ','.join(map(lambda key: "{0}={1}".format(key, deployment_label_selector.match_labels[key]), deployment_label_selector.match_labels.keys()))
        logging.debug("%s >> Deployment found - label_selector_string=%s", type(self).__name__, label_selector_string)

        # Get pods by selector
        pod_list = core_v1.list_namespaced_pod(namespace=self._config.namespace, label_selector=label_selector_string, watch=False, _request_timeout=(1,2))
        if pod_list is None or len(pod_list.items) == 0:
            logging.warning("%s >> No pods found - label_selector=%s, namespace=%s", type(self).__name__, label_selector_string, self._config.namespace)
            return (None, None)

        if len(pod_list.items) > 1:
            logging.warning("%s >> More than one pod found - label_selector=%s, namespace=%s", type(self).__name__, label_selector_string, self._config.namespace)
            for each_pod in pod_list.items:
                logging.info("%s >> Pod found - name=%s", type(self).__name__, each_pod.metadata.name)
            return (None, None)

        return (pod_list.items[0].metadata.name, pod_list.items[0].status.pod_ip)

    def kube_exec_check_connectivity(self, pod_name:str, peer:PeerConfig):
        """Checks the connectivity from within the pod to the peer

        Returns:
            _type_: True if connection could be established else False
        """
        shell_command = 'nc -z -w 1 {0} {1};echo -n $?'.format(peer.address, peer.port)
        logging.debug("%s >> shell_command=%s", type(self).__name__, shell_command)
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
                    _request_timeout=3) # do not use a tuple here, otherwise: kubernetes.client.exceptions.ApiException: (0) Reason: '<' not supported between instances of 'float' and 'tuple'

        connection_successful = resp == '0'
        logging.debug("%s >> %s %s (%s:%s) ", type(self).__name__, 'OK:  Connected to' if connection_successful else 'CANNOT connect to', peer.name, peer.address, peer.port)
        return connection_successful

    def createCurrentMetrics(self, instance: str, instance_name: str, pod_name: str):
        """Creates the current metrics 

        Args:
            instance (str): The instance name
            instance_name (str): A pretty instance name
            pod_name (str): The pod name
        """
        logging.info("%s >> Creating metrics for %s peers - instance=%s, instance_name=%s, pod_name=%s, namespace=%s", type(self).__name__, len(self._config.peers.keys()), instance, instance_name, pod_name, self._config.namespace)

        metrics = GaugeMetricFamily('quorum_tcp_egress_connectivity', 'Quorum TCP egress connectivity to other nodes by enode. (0) for no connectivity, (1) for connectivity can be established', labels=['instance', 'instance_name', 'enode', 'enode_short', 'name'])
        for each_config_peer in self._config.peers.values():
            connection_successful = self.kube_exec_check_connectivity(pod_name=pod_name, peer=each_config_peer)
            metrics.add_metric([instance, instance_name, each_config_peer.enode, each_config_peer.enode[0:20], each_config_peer.name], (1 if connection_successful else 0))

        # Set current metrics to be reported by CustomCollector in a single atomic operation
        self._current_metrics = [metrics]

    def process(self):
        """Processes getting information and preparing metrics

        """
        # 1. Use Incluster Config
        config.load_incluster_config()

        # Get DNS name and IP address of current instance by taking a deeper look at the rpc_url
        instance_dns_name = self._helper.getHostName(url=self._config.rpc_url)

        # We do not use the IP address of the RPC Endpoint as this may be the clusterIp of the service if it is not a headless service.
        # Therefore we determine the instance from network.localAddress
        # instance_ip = resolveIpAddress(dns_name=instance_dns_name) + ':9545' # default metrics also add port
        pod_name, pod_ip = self.lookup_pod_name_and_ip()

        if pod_name is not None and pod_ip is not None:
            self.createCurrentMetrics(instance="{0}:9545".format(pod_ip), instance_name=instance_dns_name, pod_name=pod_name)
        else:
            logging.warn("%s >> Cannot create metrics as pod_name or pod_ip is None - pod_name=%s, pod_ip=%s", type(self).__name__, pod_name, pod_ip)
    