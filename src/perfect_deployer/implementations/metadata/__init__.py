class FlowMetadata(BaseModel):
    """Flow metadata."""

    name: Optional[str] = None
    version: Optional[str] = None
    flow_run_name: Optional[Union[Callable[[], str], str]] = None
    description: Optional[str] = None

    def build_tags(self) -> List[str]:
        """Build flow tags."""
        tags = []
        if self.name:
            tags.append(self.name)
        if self.version:
            tags.append(self.version)
        return tags
