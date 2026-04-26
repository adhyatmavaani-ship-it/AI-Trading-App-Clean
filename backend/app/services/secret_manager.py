from __future__ import annotations

class SecretManagerService:
    """Loads live credentials from Google Secret Manager when configured."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = None
        if not project_id:
            return
        try:
            from google.cloud import secretmanager
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "google-cloud-secret-manager is required when SECRET_MANAGER_PROJECT_ID is configured"
            ) from exc
        self.client = secretmanager.SecretManagerServiceClient()

    def access_secret(self, secret_name: str, version: str = "latest") -> str | None:
        if self.client is None:
            return None
        resource_name = (
            f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
        )
        response = self.client.access_secret_version(request={"name": resource_name})
        return response.payload.data.decode("utf-8")
