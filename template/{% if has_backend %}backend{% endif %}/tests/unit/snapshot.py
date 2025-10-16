import json
from typing import override

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import SingleFileSnapshotExtension
from syrupy.extensions.single_file import WriteMode
from syrupy.types import PropertyFilter
from syrupy.types import PropertyMatcher
from syrupy.types import SerializableData
from syrupy.types import SerializedData


class SingleTextFileSnapshot(SingleFileSnapshotExtension):
    _write_mode = (
        WriteMode.TEXT
    )  # for some reason the default is binary, but it should be text to make diffs easier to read


class SingleFileJsonSnapshot(SingleTextFileSnapshot):
    file_extension = "json"

    @override
    def serialize(
        self,
        data: SerializableData,
        *,
        exclude: PropertyFilter | None = None,
        include: PropertyFilter | None = None,
        matcher: PropertyMatcher | None = None,
    ) -> SerializedData:
        # TODO: consider a way to apply the exclude/include/matcher filters to the data before dumping to pretty-format JSON
        pretty_data = json.dumps(data, indent=2) + "\n"
        return super().serialize(
            pretty_data,
            exclude=exclude,
            include=include,
            matcher=matcher,
        )


@pytest.fixture
def snapshot_json(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(SingleFileJsonSnapshot)
