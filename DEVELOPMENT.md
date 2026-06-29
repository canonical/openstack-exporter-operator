# Development

## Setup environment

You can create a virtual python environment for development with `uv`:

```shell
uv sync --group unit
source .venv/bin/activate
```

## Testing

This project uses [`just`](https://just.systems) for running development tasks. Install it with:

```shell
sudo snap install --classic just
```

Run `just` or `just help` to see the pre-configured recipes for linting, formatting, and testing.

Unit and functional tests support filtering and other pytest flags via extra arguments:

```shell
just unit -k test_charm                      # filter by test name
just unit tests/unit/test_charm.py           # run a specific file
just unit -x                                 # stop on first failure
just func -k test_charm --keep-models        # filter by test name
```

All recipes can be invoked from any subdirectory of the project; `just` will
find the `Justfile` at the project root automatically.

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

Charmcraft v3 is required to build this charm:

```
sudo snap install charmcraft --channel 3.x/stable --classic
```

Build the charm in this git repository using:

```shell
charmcraft -v pack
```

To start with a clean environment, run this first:

```shell
charmcraft clean
```
