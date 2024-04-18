"""Setup configure functions."""

from zaza import model


def setup_export_ssl_ca_config():
    """Get ca from vault and provide to exporter config."""
    output = model.run_action_on_leader("vault", "get-root-ca")
    cacert = output.data["results"]["output"]
    model.set_application_config("openstack-exporter", {"ssl_ca": cacert})
    model.block_until_file_has_contents(
        "openstack-exporter",
        "/var/snap/golang-openstack-exporter/common/clouds.yaml",
        "-----BEGIN CERTIFICATE-----",
    )
