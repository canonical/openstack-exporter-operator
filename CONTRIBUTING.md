# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

You can create a virtual python environment for development with `tox`:

```shell
tox devenv -e unit
source venv/bin/activate
```

## Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox run -e format        # update your code according to linting rules
tox run -e lint          # run static analysis (code style, type checking, etc.)
tox run -e unit          # run unit tests
tox run -e integration   # run integration tests
tox                      # run 'lint' and 'unit' environments
```


## Fetching libraries

Charm libraries are managed with charmcraft and recorded in `./scripts/update-charm-libs.sh`.

To update the libraries included, run

```shell
./scripts/update-charm-libs.sh
```

If you need to include more charm libraries, you can run:

```shell
charmcraft fetch-lib <operator-libs>
```

And add the corresponding command to `./scripts/update-charm-libs.sh`.

## Checking for dashboard and alert rule updates

The openstack exporter dashboards and alert rules are managed
in the [sunbeam-charms](https://opendev.org/openstack/sunbeam-charms) repository.
They are shared between this project for Charmed OpenStack,
and openstack-exporter-k8s in sunbeam-charms for Microstack (Sunbeam).
The files located in src/grafana_dashboards and src/prometheus_alert_rules are synchronized using the script located at ./scripts/sync-from-sunbeam.sh. To update these files, execute the following command:

```shell
./scripts/sync-from-sunbeam.sh
```

This script is also executed periodically as part of a GitHub Actions workflow to automatically synchronize the files and create a pull request.

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft -v pack
```

To start with a clean environment, run this first:

```shell
charmcraft clean
```
