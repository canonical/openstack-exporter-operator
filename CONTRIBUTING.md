# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

You can create an environment for development with `tox`:

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

This project also uses `make` for managing charm related operations. You can use the following make
targets to perform charming tasks:

```shell
make                            # show help texts
make update-charm-libs          # update charm's libraries
make check-dashboard-updates    # check if there's a new dashboard from the upstream
```

## Fetching libraries

Charm libraries are managed with charmcraft and recorded in `./scripts/update-charm-libs.sh`.

To update the libraries included, run

```shell
make update-charm-libs
```

If you need to include more charm libraries, you can run:

```shell
charmcraft fetch-lib <operator-libs>
```

And add the corresponding command to `./scripts/update-charm-libs.sh`.

## Checking for dashboard updates

The openstack exporter dashboards are shared files managed
in the [upstream repository (sunbeam-charms)](https://opendev.org/openstack/sunbeam-charms).
To check if a new version of the dashboards are available you can run the make target:

```shell
make check-dashboard-updates
```

If it reports updates, you can update them by running:

```shell
make sync-dashboards
```

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```
