"""Prefect kubernetes agent."""
from logging import INFO, StreamHandler, getLogger
from typing import cast, Dict, List
import prefect
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel


class PrefectKubernetesAgent(BaseModel):
    """A Prefect Kubernetes Agent."""

    name: str
    namespace: str
    image: str
    match_on_namespace: bool = True
    work_queue_names: List[str] = []
    cpu: float = 1
    memory_gb: float = 0.5

    @property
    def limits(self) -> Dict[str, str]:
        """Return the resource limits."""
        return {
            "cpu": str(self.cpu),
            "memory": f"{self.memory_gb}Gi",
        }

    @property
    def requests(self) -> Dict[str, str]:
        """Return the resource requests."""
        return {
            "cpu": str(self.cpu),
            "memory": f"{self.memory_gb}Gi",
        }

    @property
    def labels(self) -> Dict[str, str]:
        """Return the labels for the agent."""
        return {"app": self.name}

    @property
    def service_account_name(self) -> str:
        """Return the service account name."""
        return self.name

    def _build_command(self) -> List[str]:
        command = ["prefect", "agent", "start"]
        if self.match_on_namespace:
            command += ["--match", self.namespace]

        for work_queue in self.work_queue_names:
            command += ["--work-queue", work_queue]

        return command

    def _build_env_from_profile(self) -> List[Dict[str, str]]:
        profiles = prefect.settings.load_profiles()
        current_profile = prefect.context.get_settings_context().profile
        name = current_profile.name

        if name not in profiles:
            raise ValueError(f"Profile {name!r} not found.")

        profile = profiles[name]
        settings = profile.settings

        if not settings:
            raise ValueError(f"Profile {name!r} is empty.")

        env: List[Dict[str, str]] = [
            {
                "name": "PREFECT_KUBERNETES_CLUSTER_UID",
                "value": "1",
            },
        ]
        for setting in cast(Dict[prefect.settings.Setting[str], str], settings):
            env.append(
                {
                    "name": cast(str, setting.name),
                    "value": str(setting.value()),
                }
            )
        return env

    def _build_namespace(self) -> client.V1Namespace:
        return client.V1Namespace(
            api_version="v1",
            kind="Namespace",
            metadata=client.V1ObjectMeta(
                name=self.namespace,
            ),
        )

    def _build_deployment_spec(self) -> client.V1Deployment:
        return client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=self.name,
                namespace=self.namespace,
                labels=self.labels,
            ),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(
                    match_labels=self.labels,
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels=self.labels,
                    ),
                    spec=client.V1PodSpec(
                        service_account_name=self.service_account_name,
                        containers=[
                            client.V1Container(
                                name=self.name,
                                command=self._build_command(),
                                image=self.image,
                                env=self._build_env_from_profile(),
                                args=[],
                                resources=client.V1ResourceRequirements(
                                    limits=self.limits,
                                    requests=self.requests,
                                ),
                            )
                        ],
                    ),
                ),
            ),
        )

    def _build_service_account(self) -> client.V1ServiceAccount:
        return client.V1ServiceAccount(
            api_version="v1",
            kind="ServiceAccount",
            metadata=client.V1ObjectMeta(
                name=self.name,
                namespace=self.namespace,
            ),
        )

    def _build_role(self) -> client.V1Role:
        return client.V1Role(
            api_version="rbac.authorization.k8s.io/v1",
            kind="Role",
            metadata=client.V1ObjectMeta(
                name=self.name,
                namespace=self.namespace,
            ),
            rules=[
                client.V1PolicyRule(
                    api_groups=["*"],
                    resources=["namespaces", "pods", "pods/log", "pods/status"],
                    verbs=["get", "watch", "List"],
                ),
                client.V1PolicyRule(
                    api_groups=["*"],
                    resources=["jobs"],
                    verbs=[
                        "get",
                        "List",
                        "watch",
                        "create",
                        "update",
                        "patch",
                        "delete",
                    ],
                ),
            ],
        )

    def _build_role_binding(self) -> client.V1RoleBinding:
        return client.V1RoleBinding(
            api_version="rbac.authorization.k8s.io/v1",
            kind="RoleBinding",
            metadata=client.V1ObjectMeta(
                name=self.name,
                namespace=self.namespace,
            ),
            role_ref=client.V1RoleRef(
                api_group="rbac.authorization.k8s.io",
                kind="Role",
                name=self.name,
            ),
            subjects=[
                client.V1Subject(
                    kind="ServiceAccount",
                    name=self.name,
                    namespace=self.namespace,
                )
            ],
        )

    def _update_namespace(self) -> None:
        """Create or patch the namespace."""
        namespace = self._build_namespace()
        core_v1_api = client.CoreV1Api()
        try:
            core_v1_api.create_namespace(namespace)
        except ApiException as exc:
            if exc.status == 409:
                # Namespace already exists
                core_v1_api.patch_namespace(self.namespace, namespace)
            else:
                raise exc

    def _apply_service_account(self) -> None:
        service_account = self._build_service_account()
        core_v1_api = client.CoreV1Api()
        try:
            core_v1_api.create_namespaced_service_account(
                namespace=self.namespace,
                body=service_account,
            )
        except ApiException as exc:
            if exc.status == 409:
                # Service account already exists
                core_v1_api.patch_namespaced_service_account(
                    name=self.name,
                    namespace=self.namespace,
                    body=service_account,
                )
            else:
                raise exc

    def _apply_role(self) -> None:
        role = self._build_role()
        rbac_v1_api = client.RbacAuthorizationV1Api()
        try:
            rbac_v1_api.create_namespaced_role(
                namespace=self.namespace,
                body=role,
            )
        except ApiException as exc:
            if exc.status == 409:
                # Role already exists
                rbac_v1_api.patch_namespaced_role(
                    name=self.name,
                    namespace=self.namespace,
                    body=role,
                )
            else:
                raise exc

    def _apply_role_binding(self) -> None:
        role_binding = self._build_role_binding()
        rbac_v1_api = client.RbacAuthorizationV1Api()
        try:
            rbac_v1_api.create_namespaced_role_binding(
                namespace=self.namespace,
                body=role_binding,
            )
        except ApiException as exc:
            if exc.status == 409:
                # Role binding already exists
                rbac_v1_api.patch_namespaced_role_binding(
                    name=self.name,
                    namespace=self.namespace,
                    body=role_binding,
                )
            else:
                raise exc

    def _apply_deployment(self) -> None:
        deployment = self._build_deployment_spec()
        apps_v1_api = client.AppsV1Api()
        try:
            apps_v1_api.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment,
            )
        except ApiException as exc:
            if exc.status == 409:
                # Deployment already exists
                apps_v1_api.patch_namespaced_deployment(
                    name=self.name,
                    namespace=self.namespace,
                    body=deployment,
                )
            else:
                raise exc

    def deploy(self) -> None:
        """Deploy the agent."""
        try:
            config.load_kube_config()
        except config.config_exception.ConfigException:
            config.load_incluster_config()

        logger = getLogger()
        logger.setLevel(INFO)
        logger.addHandler(StreamHandler())

        self._update_namespace()
        logger.info(f"namespace/{self.namespace} updated")

        self._apply_service_account()
        logger.info(f"serviceaccount/{self.name} updated")

        self._apply_role()
        logger.info(f"role/{self.name} updated")

        self._apply_role_binding()
        logger.info(f"role-binding/{self.name} updated")

        self._apply_deployment()
        logger.info(f"deployment/{self.name} updated")


if __name__ == "__main__":
    agent = PrefectKubernetesAgent(
        namespace="default",
        name="prefect-agent",
        image="prefecthq/prefect:2-latest-kubernetes",
        cpu=0.2,
        memory_gb=0.2,
        # match_on_namespace=True,
        # work_queue_names=[],
    )
    agent.deploy()
