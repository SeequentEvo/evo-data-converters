def build_portal_url(object_metadata):
    """
    Build and display a link to view the geoscience object in the Evo Portal.

    Args:
        object_metadata: The metadata object returned after creating the geoscience object.

    Returns:
        None. Displays an HTML link to the Evo Portal for the created object.
    """

    hub_url = object_metadata.environment.hub_url
    hub_name = hub_url.split("://")[1].split(".")[0]
    org_id = object_metadata.environment.org_id
    workspace_id = object_metadata.environment.workspace_id

    url = f"https://evo.seequent.com/{org_id}/workspaces/{hub_name}/{workspace_id}/overview"

    return url
