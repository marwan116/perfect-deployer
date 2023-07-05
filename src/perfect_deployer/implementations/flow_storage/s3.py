"""S3 Flow Storage Implementation."""
from perfect_deployer.interface import DeployableFlowBuilderInterface
from pydantic import BaseModel
from prefect.filesystems import S3
from prefect.deployments import Deployment


class s3(BaseModel, DeployableFlowBuilderInterface):
    """S3 infrastructure builder."""

    bucket: str
    key: str

    def update_deployment(self, deployment: Deployment) -> Deployment:
        """Update deployment."""
        deployment.storage = S3(bucket_path=f"{self.bucket}/{self.key}")
        deployment.path = None
        return deployment
