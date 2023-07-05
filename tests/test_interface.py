"""Test interface."""
from prefect.deployments import Deployment
from prefect.flows import flow, Flow

from perfect_deployer.interface import DeployableFlowBuilderInterface


def test_deployment_builder_returns_deployable_flow_when_wrapping_flow():
    """Test deployment builder returns deployable flow when wrapping flow."""

    class dummy(DeployableFlowBuilderInterface):
        """Dummy deployment builder."""

        def update_deployment(self, deployment: Deployment) -> Deployment:
            return deployment

    @dummy()
    @dummy()
    @flow()
    def add(x: int, y: int) -> int:
        return x + y

    assert isinstance(add, Flow)
    assert len(add.deployment_builders) == 2
    for builder in add.deployment_builders:
        assert isinstance(builder, dummy)

    deployment = add.build_deployment()
    assert isinstance(deployment, Deployment)
