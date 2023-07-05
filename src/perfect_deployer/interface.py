"""deployer interface."""
from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

from prefect.deployments import Deployment
from prefect.flows import Flow, P, R
from prefect.utilities.asyncutils import sync_compatible
from wrapt import CallableObjectProxy

if TYPE_CHECKING:

    class DeployableFlow(Flow[P, R]):
        """Deployable flow mypy-friendly stub."""

        @property
        def deployment_builders(self) -> List["DeployableFlowBuilderInterface"]:
            ...

        @deployment_builders.setter
        def deployment_builders(
            self, deployment_builders: List["DeployableFlowBuilderInterface"]
        ) -> None:
            ...

        @sync_compatible
        async def build_deployment(self) -> Deployment:
            ...

    class DeployableFlowBuilderInterface(ABC):
        """Deployable-deployer mypy-friendly stub."""

        @abstractmethod
        def update_deployment(self, deployment: Deployment) -> Deployment:
            ...

        def __call__(self, flow: Flow[P, R]) -> DeployableFlow[P, R]:
            ...

else:

    class DeployableFlow(CallableObjectProxy):
        """Deployable Flow is a prefect flow that can deploy itself."""

        def __init__(self, flow: Flow[P, R]) -> None:
            super().__init__(flow)

            if not hasattr(self, "deployment_builders"):
                self._deployment_builders: List["DeployableFlowBuilderInterface"] = []

        @property
        def deployment_builders(self) -> List["DeployableFlowBuilderInterface"]:
            return self._deployment_builders

        @deployment_builders.setter
        def deployment_builders(
            self, deployment_builders: List["DeployableFlowBuilderInterface"]
        ) -> None:
            self._deployment_builders = deployment_builders

        @sync_compatible
        async def build_deployment(self) -> Deployment:
            """Build a deployment."""
            deployment = await Deployment.build_from_flow(
                flow=self, name=self.name, load_existing=False
            )
            for deployment_builder in self.deployment_builders:
                deployment = deployment_builder.update_deployment(deployment)
            return deployment

    class DeployableFlowBuilderInterface(ABC):
        """Interface for a deployable-deployer."""

        @abstractmethod
        def update_deployment(self, deployment: Deployment) -> Deployment:
            ...

        def __call__(self, flow: Flow[P, R]) -> DeployableFlow:
            deployable_flow = DeployableFlow(flow)
            deployable_flow.deployment_builders.append(self)
            return deployable_flow
