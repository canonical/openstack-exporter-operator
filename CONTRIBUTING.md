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

## Fetching library

If you need to include more library, you can run:

```shell
charmcraft fetch-lib <operator-libs>
```

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

