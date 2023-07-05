from perfect_deployer.implementations.infra.eks import eks as kubernetes_execution
from perfect_deployer.implementations.flow_storage.s3 import s3 as flow_storage_s3
from prefect import flow


@kubernetes_execution(
    namespace="default",
    cpu=0.2,
    memory_gb=0.3,
    image="prefecthq/prefect:2-latest-kubernetes",
)
@flow_storage_s3(bucket="aws-parquet-testing", key="my-flow")
@flow(name="my_flow")
def my_flow(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


deployment = my_flow.build_deployment()
deployment.apply(upload=True)

# create an aws pod to check s3 access
