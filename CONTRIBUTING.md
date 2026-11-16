# Contributing

Thanks for helping improve Armoury Crate for Linux. Contributions are welcome
for supported hardware, documentation, packaging, accessibility, and bug fixes.

## Before you start

- Check existing issues and pull requests before starting a substantial change.
- For larger changes, open an issue first so the approach can be discussed.
- Keep pull requests focused and describe the user-visible behavior they change.
- Do not add ASUS Windows-package assets, proprietary firmware, private reverse-
  engineering inputs, or data copied from another project's restricted files.

## Development setup

Use a Linux desktop with Python 3, GTK 4, libadwaita, PyGObject, Pycairo, and
the ASUS utilities needed by the feature being changed. Follow the installation
instructions in the [README](README.md). Launch the checkout with:

```sh
./armoury-crate
```

## Checks

Before opening a pull request, run the checks relevant to your change:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q src/
bash -n install.sh install-armoury-crate.sh uninstall.sh packaging/build-packages.sh
git diff --check
```

Hardware-dependent behavior may not be testable on every machine. Say which
hardware and Linux interfaces you used, and identify any checks you could not
run. Do not report a sensor value as supported unless it comes from a real
system interface or a test fixture.

## Pull requests

Include the reason for the change, a short description of the implementation,
and the checks you ran. For UI changes, include screenshots at a useful window
size. For hardware changes, list the relevant laptop, kernel, driver, and
utility versions when available. Remove serial numbers, account names, and
other private details from screenshots and logs.

There is no required commit-message format. Please avoid combining unrelated
changes in one pull request.

## License

By submitting a contribution, you agree that it may be distributed under the
project's [MIT License](LICENSE). You retain copyright in your contribution.
