"""EKS infrastructure builder."""
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from prefect.deployments import Deployment
from prefect.infrastructure import KubernetesJob
from pydantic import BaseModel, Field

from perfect_deployer.interface import DeployableFlowBuilderInterface


class eks(BaseModel, DeployableFlowBuilderInterface):
    """EKS infrastructure builder."""

    image: str = Field(
        description="Docker image used to run flow.",
        env="IMAGE",
        default="prefecthq/prefect:2-latest-kubernetes",
    )

    namespace: Optional[str] = Field(
        description=(
            "Kubernetes namespace to deploy flow to. "
            "If not specified, will infer namespace from "
            "deployment project name and environment."
        ),
        default=None,
    )

    cpu: float = Field(
        description="Number of virtual CPU cores to allocate to flow.",
        gt=0,
        le=64,
    )

    memory_gb: float = Field(
        description="Amount of memory to allocate to flow in GB.",
        gt=0,
        le=256,
    )

    def _resolve_namespace(self, deployment: Deployment) -> str:
        """Resolve namespace from deployment project name and environment."""
        if self.namespace is None:
            # project_name = deployment.project_name
            # environment = deployment.environment
            # self.namespace = f"{project_name}-{environment}"
            self.namespace = deployment.name
        return self.namespace

    def _ensure_namespace_exists(self, namespace: str) -> None:
        """Ensure namespace exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            namespace_file_path = Path(tmpdir) / "namespace.yaml"
            with open(namespace_file_path, "w") as namespace_file:
                subprocess.run(
                    [
                        "kubectl",
                        "create",
                        "namespace",
                        namespace,
                        "--dry-run=client",
                        "-o",
                        "yaml",
                    ],
                    stdout=namespace_file,
                    check=True,
                    cwd=tmpdir,
                )
                subprocess.run(
                    [
                        "kubectl",
                        "apply",
                        "-f",
                        namespace_file_path,
                        "--wait",
                    ],
                    check=True,
                )

    def update_deployment(self, deployment: Deployment) -> Deployment:
        """Update a deployment by building kubernetes Job and setting infra block."""
        namespace = self._resolve_namespace(deployment)
        self._ensure_namespace_exists(namespace)
        infra_block = KubernetesJob(
            image=self.image,
            namespace=namespace,
            job_watch_timeout_seconds=10 * 60,  # 10 minutes
            finished_job_ttl=10 * 60,  # 10 minutes
            job={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "namespace": namespace,
                    "labels": {
                        "prefect.io/flow-run-id": "${{flow_run_id}}",
                    },
                },
                "spec": {
                    "template": {
                        "spec": {
                            "completions": 1,
                            "parallelism": 1,
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "env": [
                                        {
                                            "name": "PREFECT_LOGGING_LEVEL",
                                            "value": "DEBUG",
                                        },
                                        {
                                            "name": "PREFECT_KUBERNETES_CLUSTER_UID",
                                            "value": "1",
                                        },
                                        {
                                            "name": "EXTRA_PIP_PACKAGES",
                                            "value": "s3fs",
                                        },
                                    ],
                                    "resources": {
                                        "requests": {
                                            "cpu": self.cpu,
                                            "memory": f"{self.memory_gb}Gi",
                                        },
                                        "limits": {
                                            "cpu": self.cpu,
                                            "memory": f"{self.memory_gb}Gi",
                                        },
                                    },
                                }
                            ],
                        }
                    },
                },
            },
        )

        deployment.infrastructure = infra_block
        return deployment
