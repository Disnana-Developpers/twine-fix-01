import logging
import os

import pytest

from tests import helpers
from twine import commands
from twine import exceptions


def test_ensure_wheel_files_uploaded_first():
    files = commands._group_wheel_files_first(
        ["twine/foo.py", "twine/first.whl", "twine/bar.py", "twine/second.whl"]
    )
    expected = [
        "twine/first.whl",
        "twine/second.whl",
        "twine/foo.py",
        "twine/bar.py",
    ]
    assert expected == files


def test_ensure_if_no_wheel_files():
    files = commands._group_wheel_files_first(["twine/foo.py", "twine/bar.py"])
    expected = ["twine/foo.py", "twine/bar.py"]
    assert expected == files


def test_find_dists_expands_globs():
    files = sorted(commands._find_dists(["twine/__*.py"]))
    expected = [
        os.path.join("twine", "__init__.py"),
        os.path.join("twine", "__main__.py"),
    ]
    assert expected == files


def test_find_dists_errors_on_invalid_globs():
    with pytest.raises(exceptions.InvalidDistribution):
        commands._find_dists(["twine/*.rb"])


def test_find_dists_handles_real_files():
    expected = [
        "twine/__init__.py",
        "twine/__main__.py",
        "twine/cli.py",
        "twine/utils.py",
        "twine/wheel.py",
    ]
    files = commands._find_dists(expected)
    assert expected == files


def test_split_inputs():
    """Split inputs into dists, signatures, and attestations."""
    inputs = [
        helpers.WHEEL_FIXTURE,
        helpers.WHEEL_FIXTURE + ".asc",
        helpers.WHEEL_FIXTURE + ".build.attestation",
        helpers.WHEEL_FIXTURE + ".publish.attestation",
        helpers.SDIST_FIXTURE,
        helpers.SDIST_FIXTURE + ".asc",
        helpers.NEW_WHEEL_FIXTURE,
        helpers.NEW_WHEEL_FIXTURE + ".frob.attestation",
        helpers.NEW_SDIST_FIXTURE,
    ]

    inputs = commands._split_inputs(inputs)

    assert inputs.dists == [
        helpers.WHEEL_FIXTURE,
        helpers.SDIST_FIXTURE,
        helpers.NEW_WHEEL_FIXTURE,
        helpers.NEW_SDIST_FIXTURE,
    ]

    expected_signatures = {
        os.path.basename(dist) + ".asc": dist + ".asc"
        for dist in [helpers.WHEEL_FIXTURE, helpers.SDIST_FIXTURE]
    }
    assert inputs.signatures == expected_signatures

    assert inputs.attestations_by_dist == {
        helpers.WHEEL_FIXTURE: [
            helpers.WHEEL_FIXTURE + ".build.attestation",
            helpers.WHEEL_FIXTURE + ".publish.attestation",
        ],
        helpers.SDIST_FIXTURE: [],
        helpers.NEW_WHEEL_FIXTURE: [helpers.NEW_WHEEL_FIXTURE + ".frob.attestation"],
        helpers.NEW_SDIST_FIXTURE: [],
    }


def test_split_inputs_attestations_require_filename_boundary():
    dist = "dist/pkg-1.0.tar.gz"
    inputs = [
        dist,
        f"{dist}.build.attestation",
        f"{dist}2.build.attestation",
    ]

    inputs = commands._split_inputs(inputs)

    assert inputs.attestations_by_dist == {
        dist: [f"{dist}.build.attestation"],
    }


def test_split_inputs_warns_on_identical_duplicate_signature_basenames(
    tmp_path, caplog
):
    first_signature = tmp_path / "a" / "pkg-1.whl.asc"
    second_signature = tmp_path / "b" / "pkg-1.whl.asc"
    first_signature.parent.mkdir()
    second_signature.parent.mkdir()
    first_signature.write_bytes(b"signature")
    second_signature.write_bytes(b"signature")

    with caplog.at_level(logging.WARNING, logger="twine.commands"):
        inputs = commands._split_inputs(
            [
                str(tmp_path / "a" / "pkg-1.whl"),
                str(tmp_path / "b" / "pkg-1.whl"),
                str(first_signature),
                str(second_signature),
            ]
        )

    assert inputs.signatures == {"pkg-1.whl.asc": str(first_signature)}
    assert inputs.dists == [
        str(tmp_path / "a" / "pkg-1.whl"),
        str(tmp_path / "b" / "pkg-1.whl"),
    ]
    assert caplog.record_tuples == [
        (
            "twine.commands",
            logging.WARNING,
            "Multiple signature files have the same name and identical "
            f"contents; using {first_signature} and ignoring {second_signature}",
        ),
    ]


def test_split_inputs_errors_on_conflicting_duplicate_signature_basenames(tmp_path):
    first_signature = tmp_path / "a" / "pkg-1.whl.asc"
    second_signature = tmp_path / "b" / "pkg-1.whl.asc"
    first_signature.parent.mkdir()
    second_signature.parent.mkdir()
    first_signature.write_bytes(b"first signature")
    second_signature.write_bytes(b"second signature")

    with pytest.raises(
        exceptions.InvalidDistribution,
        match="Multiple signature files have the same name but different contents",
    ):
        commands._split_inputs(
            [
                str(tmp_path / "a" / "pkg-1.whl"),
                str(tmp_path / "b" / "pkg-1.whl"),
                str(first_signature),
                str(second_signature),
            ]
        )
