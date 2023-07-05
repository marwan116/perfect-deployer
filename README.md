# A flow builder for prefect 2

## Motivation
Simplify deployment of flows on prefect by using flow-builder.

Given most folks on a team are not prefect deployment experts, it is useful to have a simple way to deploy flows. 

This library makes use of the builder pattern to simplify the deployment of flows. It also provides a sample implementation of the flow builder for deploying flows to an EKS kubernetes cluster. This makes deployment of flows as simple as the interface provided by the flow builder avoid a relatively steep learning curve of prefect deployment concepts.

The flow builder also provides a simple CLI tool to deploy flows.

## How to setup

Using pip:

```bash
pip install perfect_deployer
```

## How to use

Create your custom flow builder by implementing the `FlowBuilderInterface` class, or use one of the implementations provided by the library.

For example to deploy flows:
- to an EKS cluster
- persist results to s3
- use a dask-kubernetes task runner
- infer deployment metadata from the flow

you can use the `EKSFlowBuilder` class.

```python
from perfect_deployer.implementations.infra import eks as kubernetes
from perfect_deployer.implementations.task_runner import dask_k8s as dask
from perfect_deployer.implementations.metadata import deployment_metadata_from_flow
from perfect_deployer.implementations.filesystem import S3Filesystem

@kubernetes(
    cpu=0.8,
    memory=1.5,
    image="my-image",
    service_account="my-service-account",
)
@dask(
    num_workers=5
)
@deployment_metadata_from_flow(environment="dev")
@flow(
    result_storage=S3Filesystem(
        type="s3",
        bucket="my-bucket",
        path="my-path",
    )
)
def simple_flow(x: int, y: int) -> int:
    """Add two numbers x and y."""
    return x + y

deployment = simple_flow.build_deployment()
deployment.apply()
```
