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
tox run -e lint          # static analysis (code style, type checking, etc.)
tox run -e unit          # unit tests
tox                      # runs 'lint' and 'unit' environments
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

The openstack exporter dashboard is a shared file managed by the upstream repository which is
hosted in the [Sunbeam](https://opendev.org/openstack/sunbeam-charms). To check if a new version of
the dashboard is available you can run the make target:

```shell
make check-dashboard-updates
```

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```
